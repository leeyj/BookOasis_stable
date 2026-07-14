# -*- coding: utf-8 -*-
import os
import re
import mimetypes
from datetime import datetime
from api.cache import namelist_cache, image_cache
from utils.cache_helper import get_zip_file_hybrid, get_zip_read_lock
import database

IMG_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')

def get_img_files(file_path: str, zf) -> list:
    """ZIP 내 이미지 목록을 캐시에서 가져오거나 계산하여 캐시 저장"""
    from api.cache import disk_cache_manager
    local_path = disk_cache_manager.get_local_path(file_path)
    done_file = local_path + '.done'
    is_cached = os.path.exists(local_path) and os.path.exists(done_file)
    lookup_key = local_path if is_cached else file_path

    cached = namelist_cache.get(lookup_key)
    if cached is not None:
        return cached
    from utils.sort_helper import natural_sort_key
    img_files = sorted(
        [n for n in zf.namelist() if n.lower().endswith(IMG_EXT)],
        key=natural_sort_key
    )
    namelist_cache.put(lookup_key, img_files)
    return img_files


def get_imgdir_files(folder_path: str) -> list:
    """이미지 폴더(imgdir) 내 정렬된 이미지 파일 절대경로 목록 반환"""
    if not folder_path or not os.path.isdir(folder_path):
        return []

    cache_key = f"imgdir:{folder_path}"
    cached = namelist_cache.get(cache_key)
    if cached is not None:
        return cached

    from utils.sort_helper import natural_sort_key
    files = sorted(
        [
            os.path.join(folder_path, n)
            for n in os.listdir(folder_path)
            if n.lower().endswith(IMG_EXT)
        ],
        key=natural_sort_key
    )
    namelist_cache.put(cache_key, files)
    return files

class StreamService:
    @staticmethod
    def get_book_file_info(db_type, book_id):
        conn = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT file_path, file_format FROM books WHERE id=?", (book_id,))
            row = cursor.fetchone()
            if not row:
                return None, None
            return row['file_path'], (row['file_format'] or '').lower()
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_total_pages_for_book(db_type, book_id, file_path=None, file_format=None):
        if file_path is None or file_format is None:
            file_path, file_format = StreamService.get_book_file_info(db_type, book_id)
        if not file_path:
            return 0

        try:
            if file_format in ('zip', 'cbz'):
                zf = get_zip_file_hybrid(file_path)
                if zf:
                    return len(get_img_files(file_path, zf))
            elif file_format == 'imgdir' or file_path.lower().endswith('.imgdir'):
                folder_path = os.path.dirname(file_path)
                return len(get_imgdir_files(folder_path))
        except Exception as e:
            print(f"[StreamService] total_pages calculation failed ({book_id}): {e}")

        return 0

    @staticmethod
    def extract_page(file_path: str, page_idx: int, db_type: str = 'general', book_id = None):
        """단일 페이지를 (img_data, mime_type)으로 반환 (Zip 오프셋 최적화 및 Fallback 지원)"""
        cache_key = (file_path, page_idx)
        cached = image_cache.get(cache_key)
        if cached is not None:
            return cached

        with get_zip_read_lock(file_path):
            cached = image_cache.get(cache_key)
            if cached is not None:
                return cached

            # ── [IMGDIR Path] 폴더 이미지 직접 스트리밍 ──
            if file_path.lower().endswith('.imgdir'):
                folder_path = os.path.dirname(file_path)
                img_files = get_imgdir_files(folder_path)
                if page_idx < 0 or page_idx >= len(img_files):
                    return None

                target = img_files[page_idx]
                try:
                    with open(target, 'rb') as f:
                        data = f.read()
                    mime, _ = mimetypes.guess_type(target)
                    mime = mime or 'image/jpeg'
                    result = (data, mime)
                    image_cache.put(cache_key, result, len(data))
                    return result
                except Exception as e:
                    print(f"[StreamService] IMGDIR page extract fail [{target}]: {e}")
                    return None

            # ── [Fast Path] Zip 오프셋 기반 부분 스트리밍 가속 기동 ──
            if book_id is not None:
                conn = None
                try:
                    conn = database.get_connection(db_type)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT filename, local_header_offset, compress_size, file_size, compress_type
                        FROM book_offsets
                        WHERE book_id = ? AND page_idx = ?
                    """, (book_id, page_idx))
                    row = cursor.fetchone()

                    if row and os.path.exists(file_path):
                        local_header_offset = row['local_header_offset']
                        compress_size = row['compress_size']
                        file_size = row['file_size']
                        compress_type = row['compress_type']
                        target_filename = row['filename']

                        with open(file_path, 'rb') as f:
                            # 1) 로컬 파일 헤더 분석
                            f.seek(local_header_offset)
                            header = f.read(30)
                            if len(header) == 30:
                                fn_len = int.from_bytes(header[26:28], 'little')
                                extra_len = int.from_bytes(header[28:30], 'little')
                                data_offset = local_header_offset + 30 + fn_len + extra_len

                                # 2) 실제 데이터 조각 Seek & Read
                                f.seek(data_offset)
                                raw_bytes = f.read(compress_size)

                                img_data = None
                                if compress_type == 0:  # ZIP_STORED (압축 해제 불필요)
                                    img_data = raw_bytes
                                    # print(f"[Offset-SpeedRun] STORED Serving: {target_filename} ({compress_size} bytes)")
                                elif compress_type == 8:  # ZIP_DEFLATED (압축 적용)
                                    import zlib
                                    img_data = zlib.decompress(raw_bytes, -zlib.MAX_WBITS)
                                    # print(f"[Offset-SpeedRun] DEFLATED Serving: {target_filename} (Original: {file_size} bytes)")

                                if img_data is not None:
                                    mime, _ = mimetypes.guess_type(target_filename)
                                    mime = mime or 'image/jpeg'
                                    result = (img_data, mime)
                                    image_cache.put(cache_key, result, len(img_data))
                                    return result
                except Exception as ex_offset:
                    print(f"[Offset-SpeedRun FAIL] {os.path.basename(file_path)} [{page_idx}]: {ex_offset} (Fallback executed)")
                finally:
                    if conn:
                        conn.close()

            # ── [Fallback Path] 오프셋 조회 불가 또는 실패 시 기존 전체 복사/Seek 캐시 엔진 사용 ──
            # print(f"[Offset-Fallback] Legacy loader executed: {os.path.basename(file_path)}")
            zf = get_zip_file_hybrid(file_path)
            if zf is None:
                return None

            img_files = get_img_files(file_path, zf)
            if page_idx < 0 or page_idx >= len(img_files):
                return None

            try:
                target = img_files[page_idx]
                data = zf.read(target)
                mime, _ = mimetypes.guess_type(target)
                mime = mime or 'image/jpeg'
                result = (data, mime)
                
                image_cache.put(cache_key, result, len(data))
                return result
            except Exception as e:
                print(f"[StreamService] Page extract fail [{file_path}:{page_idx}]: {e}")
                return None

    @staticmethod
    def record_progress(db_type: str, book_id, page_idx: int, total_pages: int, user_id=1, epub_session=None):
        """독서 진행률 및 활동 로그 기록 (EPUB 및 TXT도 실제 챕터 단위를 그대로 사용)"""
        conn   = database.get_connection(db_type)
        cursor = conn.cursor()

        cursor.execute("SELECT file_format, total_pages FROM books WHERE id = ?", (book_id,))
        book_row = cursor.fetchone()

        try:
            page_idx = int(page_idx)
        except Exception:
            page_idx = 0

        try:
            total_pages = int(total_pages)
        except Exception:
            total_pages = 0
        
        # 실제 프론트엔드에서 전달된 총 페이지(챕터) 수를 기반으로 DB 업데이트
        if total_pages > 0 and book_row and book_row['total_pages'] != total_pages:
            cursor.execute("UPDATE books SET total_pages = ? WHERE id = ?", (total_pages, book_id))
                
        cursor.execute("SELECT pages_read, is_completed FROM user_progress WHERE book_id = ? AND user_id = ?", (book_id, user_id))
        row = cursor.fetchone()

        pages_read   = page_idx + 1
        is_completed = 0
        if total_pages > 0:
            if (pages_read / total_pages) >= 0.95 or pages_read >= total_pages:
                is_completed = 1

        # [완독 리셋 방지 방어 코드] 이미 이전에 완독한 기록(is_completed = 1)이 있다면 완독 상태를 강제 보존합니다.
        if row and row['is_completed'] == 1:
            is_completed = 1
        
        now_str      = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        epub_session = epub_session or {}
        last_epub_cfi = epub_session.get('cfi')
        last_epub_href = epub_session.get('href')
        last_epub_spine_index = epub_session.get('index')
        last_epub_percent = epub_session.get('percent')
        last_epub_updated_at = now_str if (last_epub_cfi or last_epub_href) else None

        if not row:
            # 1. 경쟁 상태 대비: INSERT OR IGNORE 로 레코드 선삽입
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_progress (
                    book_id, user_id, pages_read, is_completed, last_read_at,
                    last_epub_cfi, last_epub_href, last_epub_spine_index,
                    last_epub_percent, last_epub_updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    book_id,
                    user_id,
                    0,
                    0,
                    now_str,
                    None,
                    None,
                    None,
                    0,
                    None
                )
            )
            delta = pages_read
        else:
            old_pages = row['pages_read']
            delta     = max(0, pages_read - old_pages)

        # 2. 레코드가 확실히 존재하므로 일괄 UPDATE 수행하여 최종 상태 저장
        if last_epub_cfi or last_epub_href:
            cursor.execute(
                """
                UPDATE user_progress
                SET pages_read=?, is_completed=?, last_read_at=?,
                    last_epub_cfi=?, last_epub_href=?, last_epub_spine_index=?,
                    last_epub_percent=?, last_epub_updated_at=?
                WHERE book_id=? AND user_id=?
                """,
                (
                    pages_read,
                    is_completed,
                    now_str,
                    last_epub_cfi,
                    last_epub_href,
                    last_epub_spine_index,
                    last_epub_percent,
                    last_epub_updated_at,
                    book_id,
                    user_id,
                )
            )
        else:
            cursor.execute(
                "UPDATE user_progress SET pages_read=?, is_completed=?, last_read_at=? WHERE book_id=? AND user_id=?",
                (pages_read, is_completed, now_str, book_id, user_id)
            )

        if delta > 0:
            today_str = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT id FROM user_reading_log WHERE book_id=? AND user_id=? AND read_date=?", (book_id, user_id, today_str))
            log_row = cursor.fetchone()
            if log_row:
                cursor.execute("UPDATE user_reading_log SET pages_read_delta=pages_read_delta+? WHERE id=?", (delta, log_row['id']))
            else:
                cursor.execute(
                    "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (?,?,?,60,?)",
                    (book_id, user_id, delta, today_str)
                )

        conn.commit()
        conn.close()

    @staticmethod
    def get_progress_state(db_type: str, book_id, user_id=1):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                b.file_format,
                b.total_pages,
                p.pages_read,
                p.last_read_at,
                p.last_epub_cfi,
                p.last_epub_href,
                p.last_epub_spine_index,
                p.last_epub_percent,
                p.last_epub_updated_at
            FROM books b
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
            WHERE b.id = ?
            """,
            (user_id, book_id)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        file_format = (row['file_format'] or '').lower()
        total_pages = row['total_pages'] if row['total_pages'] is not None else 0
        pages_read = row['pages_read'] if row['pages_read'] is not None else 0
        last_epub_percent = row['last_epub_percent'] if row['last_epub_percent'] is not None else 0

        # 로드 시점에는 DB를 변경하지 않고, 응답 값만 비파괴 정규화합니다.
        # 운영 중 대규모 데이터 보정은 별도 마이그레이션 도구로 수행합니다.
        if file_format == 'epub':
            normalized_total = 100
            normalized_pages = pages_read

            if last_epub_percent:
                normalized_pages = last_epub_percent

            try:
                normalized_pages = int(normalized_pages)
            except Exception:
                normalized_pages = 0

            normalized_pages = max(0, min(100, normalized_pages))

            total_pages = normalized_total
            pages_read = normalized_pages

        conn.close()

        return {
            'total_pages': total_pages,
            'pages_read': pages_read,
            'last_read_at': row['last_read_at'],
            'epub_session': {
                'cfi': row['last_epub_cfi'],
                'href': row['last_epub_href'],
                'index': row['last_epub_spine_index'],
                'percent': last_epub_percent,
                'updatedAt': row['last_epub_updated_at']
            }
        }

    @staticmethod
    def get_txt_content(file_path):
        """TXT 소설 파일의 자동 인코딩 디코딩 처리 (CP949/EUC-KR 깨진 바이트 자비 허용)"""
        if not os.path.exists(file_path):
            return None, 'File not found'

        # 1. UTF-8 인코딩은 엄격하게 검증하여 시도
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content, None
        except UnicodeDecodeError:
            pass

        # 2. UTF-8이 아닌 경우 한글 완성형 인코딩인 CP949/EUC-KR strict 모드 시도
        for enc in ('cp949', 'euc-kr'):
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                return content, None
            except UnicodeDecodeError:
                continue

        # 3. 완벽한 디코딩에 실패한 경우, 일부 깨진 바이트를 보정(replace)하며 cp949 강제 로딩
        try:
            with open(file_path, 'r', encoding='cp949', errors='replace') as f:
                content = f.read()
            return content, None
        except Exception:
            pass

        # 4. 최종 Fallback
        try:
            with open(file_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='ignore')
            return content, None
        except Exception as e:
            return None, f"Failed to decode file: {e}"

    @staticmethod
    def get_file_path(db_type, book_id):
        conn = None
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM books WHERE id=?", (book_id,))
            row = cursor.fetchone()
            return row['file_path'] if row else None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_epub_content(file_path, book_id, db_type):
        """EPUB 파일을 열고, OPF 및 Spine 구조를 따라 정제된 텍스트 및 마크업 데이터 추출 (이미지 주소 매핑 포함)"""
        import zipfile
        from html.parser import HTMLParser
        import xml.etree.ElementTree as ET
        import urllib.parse
        import posixpath

        if not os.path.exists(file_path):
            return None, 'File not found'

        class EPUBHTMLParser(HTMLParser):
            def __init__(self, xhtml_path, book_id, db_type):
                super().__init__()
                self.recording = False
                self.output = []
                # Keep a conservative allowlist for safe, readability-focused EPUB rendering.
                self.allowed_tags = {
                    'p', 'br', 'hr',
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    'div', 'blockquote',
                    'ul', 'ol', 'li',
                    'strong', 'em', 'b', 'i', 'u', 's',
                    'sup', 'sub',
                    'ruby', 'rt', 'rp',
                    'img'
                }
                self.xhtml_path = xhtml_path
                self.book_id = book_id
                self.db_type = db_type

            def handle_starttag(self, tag, attrs):
                tag_lower = tag.lower()
                if tag_lower == 'body':
                    self.recording = True
                elif self.recording and tag_lower in self.allowed_tags:
                    if tag_lower == 'br':
                        self.output.append('<br/>')
                    elif tag_lower == 'hr':
                        self.output.append('<hr/>')
                    elif tag_lower == 'img':
                        attrs_dict = dict(attrs)
                        src_val = attrs_dict.get('src')
                        if src_val:
                            xhtml_dir = posixpath.dirname(self.xhtml_path)
                            clean_src = urllib.parse.unquote(src_val.split('#')[0])
                            resolved_path = posixpath.normpath(posixpath.join(xhtml_dir, clean_src)).replace('\\', '/')
                            
                            encoded_path = urllib.parse.quote(resolved_path)
                            api_src = f"/api/media/epub-image?book_id={self.book_id}&db_type={self.db_type}&path={encoded_path}"
                            
                            self.output.append(f'<img src="{api_src}" style="max-width: 100%; max-height: 75vh; object-fit: contain; height: auto; display: block; margin: 1.5rem auto; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"/>')
                    else:
                        self.output.append(f'<{tag_lower}>')

            def handle_endtag(self, tag):
                tag_lower = tag.lower()
                if tag_lower == 'body':
                    self.recording = False
                elif self.recording and tag_lower in self.allowed_tags:
                    if tag_lower not in ('br', 'hr', 'img'):
                        self.output.append(f'</{tag_lower}>')

            def handle_data(self, data):
                if self.recording:
                    import html
                    self.output.append(html.escape(data))

            def get_content(self):
                return "".join(self.output)

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # 1. META-INF/container.xml 파싱
                container_data = zf.read('META-INF/container.xml')
                root = ET.fromstring(container_data)
                ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                rootfile = root.find('.//ns:rootfile', ns)
                if rootfile is None:
                    rootfile = root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
                if rootfile is None:
                    return None, 'Invalid container.xml'
                
                opf_path = rootfile.attrib.get('full-path')
                if not opf_path:
                    return None, 'OPF file path not found in container.xml'

                opf_dir = os.path.dirname(opf_path)
                opf_data = zf.read(opf_path)
                
                opf_str = opf_data.decode('utf-8', errors='ignore')
                opf_str_cleaned = re.sub(r'\sxmlns="[^"]+"', '', opf_str, count=1)
                opf_root = ET.fromstring(opf_str_cleaned.encode('utf-8'))

                title_elem = opf_root.find('.//title')
                title = title_elem.text if title_elem is not None else 'Untitled'

                manifest_items = {}
                ncx_href = None
                nav_href = None
                for item in opf_root.findall('.//manifest/item'):
                    item_id = item.attrib.get('id')
                    href = item.attrib.get('href')
                    media_type = item.attrib.get('media-type', '')
                    properties = item.attrib.get('properties', '')
                    
                    if item_id and href:
                        manifest_items[item_id] = href
                    if media_type == 'application/x-dtbncx+xml':
                        ncx_href = href
                    if 'nav' in properties.split():
                        nav_href = href

                spine = opf_root.find('.//spine')
                if not ncx_href and spine is not None:
                    toc_id = spine.attrib.get('toc')
                    if toc_id and toc_id in manifest_items:
                        ncx_href = manifest_items[toc_id]

                spine_itemrefs = []
                if spine is not None:
                    for itemref in spine.findall('./itemref'):
                        idref = itemref.attrib.get('idref')
                        if idref in manifest_items:
                            spine_itemrefs.append(manifest_items[idref])

                toc_list = []
                try:
                    from bs4 import BeautifulSoup
                    import urllib.parse
                    import posixpath

                    def resolve_toc_item(src, base_href):
                        if not src:
                            return -1, ""
                        parts = src.split('#')
                        clean_src = urllib.parse.unquote(parts[0])
                        anchor = parts[1] if len(parts) > 1 else ""
                        base_dir = posixpath.dirname(base_href)
                        src_rel_to_opf = posixpath.normpath(posixpath.join(base_dir, clean_src))
                        if src_rel_to_opf.startswith('./'):
                            src_rel_to_opf = src_rel_to_opf[2:]
                        elif src_rel_to_opf == '.':
                            src_rel_to_opf = ''
                            
                        idx = -1
                        for i, spine_ref in enumerate(spine_itemrefs):
                            if spine_ref == src_rel_to_opf or urllib.parse.unquote(spine_ref) == src_rel_to_opf:
                                idx = i
                                break
                        return idx, anchor

                    if nav_href:
                        nav_full_path = posixpath.join(opf_dir, nav_href) if opf_dir else nav_href
                        nav_data = zf.read(nav_full_path).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(nav_data, 'html.parser')
                        nav_elem = soup.find('nav', attrs={'epub:type': 'toc'})
                        if not nav_elem:
                            nav_elem = soup.find('nav', attrs={'role': 'doc-toc'})
                        if nav_elem:
                            def parse_nav_ol(ol_elem, level=1):
                                for li in ol_elem.find_all('li', recursive=False):
                                    a_tag = li.find('a')
                                    if a_tag and a_tag.get('href'):
                                        idx, anchor = resolve_toc_item(a_tag.get('href'), nav_href)
                                        toc_list.append({
                                            'title': a_tag.get_text(strip=True),
                                            'chapter_idx': idx,
                                            'anchor': anchor,
                                            'level': level
                                        })
                                    child_ol = li.find('ol')
                                    if child_ol:
                                        parse_nav_ol(child_ol, level + 1)
                            root_ol = nav_elem.find('ol')
                            if root_ol:
                                parse_nav_ol(root_ol, 1)

                    if not toc_list and ncx_href:
                        ncx_full_path = posixpath.join(opf_dir, ncx_href) if opf_dir else ncx_href
                        ncx_data = zf.read(ncx_full_path).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(ncx_data, 'html.parser')
                        navmap = soup.find('navmap')
                        if navmap:
                            def parse_navpoint(np_elem, level=1):
                                for np in np_elem.find_all('navpoint', recursive=False):
                                    label_elem = np.find('navlabel')
                                    text_elem = label_elem.find('text') if label_elem else None
                                    title = text_elem.get_text(strip=True) if text_elem else 'Untitled'
                                    
                                    content_elem = np.find('content')
                                    src = content_elem.get('src') if content_elem else None
                                    
                                    idx, anchor = resolve_toc_item(src, ncx_href)
                                    toc_list.append({
                                        'title': title,
                                        'chapter_idx': idx,
                                        'anchor': anchor,
                                        'level': level
                                    })
                                    parse_navpoint(np, level + 1)
                            parse_navpoint(navmap, 1)
                except Exception as e:
                    import logging
                    logging.error(f"Failed to parse TOC: {e}")

                chapters = []
                for idx, rel_href in enumerate(spine_itemrefs):
                    clean_rel_href = rel_href.split('#')[0]
                    import urllib.parse
                    clean_rel_href = urllib.parse.unquote(clean_rel_href)
                    
                    if opf_dir:
                        full_href = os.path.join(opf_dir, clean_rel_href).replace('\\', '/')
                    else:
                        full_href = clean_rel_href
                    
                    try:
                        html_bytes = zf.read(full_href)
                        html_str = html_bytes.decode('utf-8', errors='ignore')
                        
                        parser = EPUBHTMLParser(full_href, book_id, db_type)
                        parser.feed(html_str)
                        chapter_content = parser.get_content()
                        
                        h_match = re.search(r'<h[1-6]>(.*?)</h[1-6]>', chapter_content, re.IGNORECASE)
                        if h_match:
                            import html
                            ch_title = html.unescape(re.sub('<[^<]+?>', '', h_match.group(1))).strip()
                        else:
                            ch_title = f"Chapter {idx + 1}"
                        
                        if not ch_title:
                            ch_title = f"Chapter {idx + 1}"

                        chapters.append({
                            'title': ch_title,
                            'content': chapter_content
                        })
                    except KeyError:
                        continue

                return {
                    'title': title,
                    'chapters': chapters,
                    'toc': toc_list
                }, None

        except Exception as e:
            return None, f"EPUB parsing failed: {e}"

    @staticmethod
    def extract_epub_resource(file_path, resource_path):
        """EPUB 내 특정 상대경로 리소스(이미지 등)를 바이너리로 반환"""
        import zipfile
        if not os.path.exists(file_path):
            return None, 'File not found'
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                normalized_path = resource_path.replace('\\', '/')
                try:
                    data = zf.read(normalized_path)
                    return data, None
                except KeyError:
                    # 대소문자 매핑 실패 대비 전체 검색
                    for name in zf.namelist():
                        if name.lower() == normalized_path.lower():
                            return zf.read(name), None
                    return None, 'Resource not found'
        except Exception as e:
            return None, str(e)

