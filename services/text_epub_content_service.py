# -*- coding: utf-8 -*-
import os
import re


class TextEpubContentService:
    @staticmethod
    def get_txt_content(file_path):
        """TXT 소설 파일의 자동 인코딩 디코딩 처리 (CP949/EUC-KR 깨진 바이트 자비 허용)"""
        if not os.path.exists(file_path):
            return None, 'File not found'

        # ─── Redis 캐시 조회 ───
        import hashlib
        path_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
        redis_cache_key = f"cache:txt:file:{path_hash}"
        try:
            from utils.redis_helper import redis_get
            redis_data = redis_get(redis_cache_key)
            if redis_data:
                return redis_data, None
        except Exception as r_err:
            print(f"[Redis Cache Get ERROR] {r_err}")

        def save_and_return(text):
            try:
                from utils.redis_helper import redis_set
                redis_set(redis_cache_key, text, ex=43200)  # 12시간 캐시 유지
            except Exception as r_err:
                print(f"[Redis Cache Put ERROR] {r_err}")
            return text, None

        # 1. UTF-8 인코딩은 엄격하게 검증하여 시도
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return save_and_return(content)
        except UnicodeDecodeError:
            pass

        # 2. UTF-8이 아닌 경우 한글 완성형 인코딩인 CP949/EUC-KR strict 모드 시도
        for enc in ('cp949', 'euc-kr'):
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                return save_and_return(content)
            except UnicodeDecodeError:
                continue

        # 3. 완벽한 디코딩에 실패한 경우, 일부 깨진 바이트를 보정(replace)하며 cp949 강제 로딩
        try:
            with open(file_path, 'r', encoding='cp949', errors='replace') as f:
                content = f.read()
            return save_and_return(content)
        except Exception:
            pass

        # 4. 최종 Fallback
        try:
            with open(file_path, 'rb') as f:
                content = f.read().decode('utf-8', errors='ignore')
            return save_and_return(content)
        except Exception as e:
            return None, f"Failed to decode file: {e}"

    @staticmethod
    def get_epub_meta(file_path, book_id, db_type):
        """EPUB 메타데이터(제목, 목차 TOC, Spine 챕터 목록)만 50ms 내 고속 추출"""
        import zipfile
        import xml.etree.ElementTree as ET
        import urllib.parse
        import posixpath

        if not os.path.exists(file_path):
            return None, 'File not found'

        redis_cache_key = f"cache:epub:meta:book:{book_id}" if book_id else None
        if redis_cache_key:
            try:
                from utils.redis_helper import redis_get
                redis_data = redis_get(redis_cache_key)
                if redis_data:
                    import json
                    return json.loads(redis_data), None
            except Exception as r_err:
                print(f"[Redis Cache Get ERROR] {r_err}")

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                container_data = zf.read('META-INF/container.xml')
                root = ET.fromstring(container_data)
                ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                rootfile = root.find('.//ns:rootfile', ns)
                if rootfile is None:
                    rootfile = root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
                if rootfile is None:
                    return None, 'Invalid container.xml'

                opf_path = rootfile.attrib.get('full-path')
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
                    import warnings
                    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
                    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

                    def resolve_toc_item(src, base_href):
                        if not src:
                            return -1, ''
                        parts = src.split('#')
                        clean_src = urllib.parse.unquote(parts[0])
                        anchor = parts[1] if len(parts) > 1 else ''
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
                        try:
                            soup = BeautifulSoup(nav_data, 'xml')
                        except Exception:
                            soup = BeautifulSoup(nav_data, 'html.parser')
                        for nav in soup.find_all('nav'):
                            if nav.get('epub:type') == 'toc' or nav.get('type') == 'toc' or not toc_list:
                                for a in nav.find_all('a'):
                                    href = a.get('href')
                                    text = a.get_text().strip()
                                    idx, anchor = resolve_toc_item(href, nav_href)
                                    toc_list.append({
                                        'title': text,
                                        'chapter_idx': idx,
                                        'anchor': anchor,
                                        'level': 1
                                    })
                    elif ncx_href:
                        ncx_full_path = posixpath.join(opf_dir, ncx_href) if opf_dir else ncx_href
                        ncx_data = zf.read(ncx_full_path).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(ncx_data, 'xml')
                        navmap = soup.find('navMap')
                        if navmap:
                            def parse_navpoint(element, level):
                                for np in element.find_all('navPoint', recursive=False):
                                    navlabel = np.find('navLabel')
                                    text_elem = navlabel.find('text') if navlabel else None
                                    title = text_elem.get_text().strip() if text_elem else 'Chapter'
                                    content_elem = np.find('content')
                                    src = content_elem.get('src') if content_elem else None
                                    idx, anchor = resolve_toc_item(src, ncx_href)
                                    toc_list.append({
                                        'title': title,
                                        'chapter_idx': idx,
                                        'anchor': anchor,
                                        'level': level,
                                    })
                                    parse_navpoint(np, level + 1)
                            parse_navpoint(navmap, 1)
                except Exception as e:
                    import logging
                    logging.error(f"Failed to parse TOC: {e}")

                chapter_headers = []
                for idx, rel_href in enumerate(spine_itemrefs):
                    chapter_headers.append({
                        'idx': idx,
                        'href': rel_href
                    })

                result = {
                    'title': title,
                    'total_chapters': len(spine_itemrefs),
                    'toc': toc_list,
                    'spine_itemrefs': spine_itemrefs
                }

                if redis_cache_key:
                    try:
                        from utils.redis_helper import redis_set
                        import json
                        redis_set(redis_cache_key, json.dumps(result, ensure_ascii=False), ex=86400)
                    except Exception as r_err:
                        print(f"[Redis Cache Put ERROR] {r_err}")

                return result, None
        except Exception as e:
            return None, f"EPUB meta parsing failed: {e}"

    @staticmethod
    def get_epub_chapter(file_path, book_id, db_type, chapter_idx):
        """요청된 특정 챕터(chapter_idx)만 0.01초 내 단독 추출 및 변환"""
        import zipfile
        from html.parser import HTMLParser
        import xml.etree.ElementTree as ET
        import urllib.parse
        import posixpath

        chapter_idx = int(chapter_idx)
        if not os.path.exists(file_path):
            return None, 'File not found'

        redis_cache_key = f"cache:epub:ch:book:{book_id}:{chapter_idx}" if book_id else None
        if redis_cache_key:
            try:
                from utils.redis_helper import redis_get
                redis_data = redis_get(redis_cache_key)
                if redis_data:
                    import json
                    return json.loads(redis_data), None
            except Exception as r_err:
                print(f"[Redis Cache Get ERROR] {r_err}")

        class EPUBHTMLParser(HTMLParser):
            def __init__(self, xhtml_path, book_id, db_type):
                super().__init__()
                self.recording = False
                self.output = []
                self.allowed_tags = {
                    'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    'div', 'blockquote', 'ul', 'ol', 'li',
                    'strong', 'em', 'b', 'i', 'u', 's', 'sup', 'sub',
                    'ruby', 'rt', 'rp', 'img',
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
                            self.output.append(
                                f'<img src="{api_src}" style="max-width: 100%; max-height: 75vh; object-fit: contain; height: auto; display: block; margin: 1.5rem auto; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"/>'
                            )
                    else:
                        attrs_dict = dict(attrs)
                        elem_id = attrs_dict.get('id')
                        if elem_id:
                            import html
                            safe_id = html.escape(str(elem_id), quote=True)
                            self.output.append(f'<{tag_lower} id="{safe_id}">')
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
                return ''.join(self.output)

        try:
            meta, err = TextEpubContentService.get_epub_meta(file_path, book_id, db_type)
            if err or not meta or 'spine_itemrefs' not in meta:
                return None, f"EPUB metadata load failed: {err}"

            spine_itemrefs = meta['spine_itemrefs']
            if chapter_idx < 0 or chapter_idx >= len(spine_itemrefs):
                return None, 'Chapter index out of range'

            rel_href = spine_itemrefs[chapter_idx]
            clean_rel_href = urllib.parse.unquote(rel_href.split('#')[0])

            with zipfile.ZipFile(file_path, 'r') as zf:
                container_data = zf.read('META-INF/container.xml')
                root = ET.fromstring(container_data)
                ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                rootfile = root.find('.//ns:rootfile', ns)
                if rootfile is None:
                    rootfile = root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
                opf_path = rootfile.attrib.get('full-path')
                opf_dir = os.path.dirname(opf_path)

                if opf_dir:
                    full_href = posixpath.join(opf_dir, clean_rel_href).replace('\\', '/')
                else:
                    full_href = clean_rel_href

                try:
                    html_bytes = zf.read(full_href)
                except KeyError:
                    found_name = None
                    for name in zf.namelist():
                        if name.lower() == full_href.lower():
                            found_name = name
                            break
                    if not found_name:
                        return None, f"Chapter file not found: {full_href}"
                    html_bytes = zf.read(found_name)

                html_str = html_bytes.decode('utf-8', errors='ignore')
                parser = EPUBHTMLParser(full_href, book_id, db_type)
                parser.feed(html_str)
                chapter_content = parser.get_content()

                h_match = re.search(r'<h[1-6]>(.*?)</h[1-6]>', chapter_content, re.IGNORECASE)
                if h_match:
                    import html
                    ch_title = html.unescape(re.sub('<[^<]+?>', '', h_match.group(1))).strip()
                else:
                    ch_title = f"Chapter {chapter_idx + 1}"

                result = {
                    'chapter_idx': chapter_idx,
                    'title': ch_title,
                    'content': chapter_content,
                    'total_chapters': len(spine_itemrefs)
                }

                if redis_cache_key:
                    try:
                        from utils.redis_helper import redis_set
                        import json
                        redis_set(redis_cache_key, json.dumps(result, ensure_ascii=False), ex=86400)
                    except Exception as r_err:
                        print(f"[Redis Cache Put ERROR] {r_err}")

                return result, None
        except Exception as e:
            return None, f"EPUB chapter parsing failed: {e}"

    @staticmethod
    def get_epub_content(file_path, book_id, db_type):
        """하위 호환성 유지: 메타데이터 및 전체 챕터를 병렬/순차 결합하여 반환"""
        meta, err = TextEpubContentService.get_epub_meta(file_path, book_id, db_type)
        if err or not meta:
            return None, err

        total_chapters = meta.get('total_chapters', 0)
        chapters = []
        for idx in range(total_chapters):
            ch_data, ch_err = TextEpubContentService.get_epub_chapter(file_path, book_id, db_type, idx)
            if ch_data:
                chapters.append({'title': ch_data['title'], 'content': ch_data['content']})

        result = {
            'title': meta.get('title', 'Untitled'),
            'chapters': chapters,
            'toc': meta.get('toc', [])
        }
        return result, None

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
