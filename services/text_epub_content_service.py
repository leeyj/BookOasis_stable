# -*- coding: utf-8 -*-
import os
import re
import html
import posixpath
import urllib.parse
from html.parser import HTMLParser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPUB_IMAGE_CACHE_DIR = os.path.join(BASE_DIR, 'cache', 'epub_images')
EPUB_IMAGE_MAX_SIDE = 1600  # 뷰어 실제 표시 폭(2페이지 모드 최대 1600px)을 넘는 원본은 리사이즈


class _EPUBBodyHTMLParser(HTMLParser):
    """EPUB 챕터 XHTML의 <body> 내용을 허용된 태그만 남겨 정제된 HTML 문자열로 변환.
    단일/배치 챕터 추출 경로 둘 다 재사용하도록 모듈 최상위로 분리(예전엔 get_epub_chapter
    내부에 매 호출마다 새로 정의되는 중첩 클래스였음)."""

    ALLOWED_TAGS = {
        'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'div', 'blockquote', 'ul', 'ol', 'li',
        'strong', 'em', 'b', 'i', 'u', 's', 'sup', 'sub',
        'ruby', 'rt', 'rp', 'img',
    }

    def __init__(self, xhtml_path, book_id, db_type):
        super().__init__()
        self.recording = False
        self.output = []
        self.xhtml_path = xhtml_path
        self.book_id = book_id
        self.db_type = db_type

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower == 'body':
            self.recording = True
        elif self.recording and tag_lower in self.ALLOWED_TAGS:
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
                    safe_id = html.escape(str(elem_id), quote=True)
                    self.output.append(f'<{tag_lower} id="{safe_id}">')
                else:
                    self.output.append(f'<{tag_lower}>')

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == 'body':
            self.recording = False
        elif self.recording and tag_lower in self.ALLOWED_TAGS:
            if tag_lower not in ('br', 'hr', 'img'):
                self.output.append(f'</{tag_lower}>')

    def handle_data(self, data):
        if self.recording:
            self.output.append(html.escape(data))

    def get_content(self):
        return ''.join(self.output)


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

        redis_cache_key = f"cache:epub:meta:book:{db_type}:{book_id}" if book_id else None
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

                # 비표준 EPUB 대응: ncx나 nav가 manifest 속성에 명시되지 않은 경우 확장자 및 파일명 fallback 감지
                if not ncx_href and not nav_href:
                    for item_id, href in manifest_items.items():
                        lower_href = href.lower()
                        if lower_href.endswith('.ncx') or 'toc' in lower_href:
                            ncx_href = href
                            break
                        elif 'nav' in lower_href and (lower_href.endswith('.xhtml') or lower_href.endswith('.html')):
                            nav_href = href

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
                                    fallback_num = (idx + 1) if idx >= 0 else (len(toc_list) + 1)
                                    title_text = text if text else f"{fallback_num}장"
                                    toc_list.append({
                                        'title': title_text,
                                        'chapter_idx': idx,
                                        'anchor': anchor,
                                        'level': 1
                                    })
                    if not toc_list and ncx_href:
                        ncx_full_path = posixpath.join(opf_dir, ncx_href) if opf_dir else ncx_href
                        ncx_data = zf.read(ncx_full_path).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(ncx_data, 'xml')
                        navmap = soup.find(re.compile(r'navmap', re.I))
                        if navmap:
                            def parse_navpoint(element, level):
                                for np in element.find_all(re.compile(r'navpoint', re.I), recursive=False):
                                    navlabel = np.find(re.compile(r'navlabel', re.I))
                                    text_elem = navlabel.find(re.compile(r'text', re.I)) if navlabel else None
                                    title = text_elem.get_text().strip() if text_elem else ''
                                    content_elem = np.find(re.compile(r'content', re.I))
                                    src = content_elem.get('src') if content_elem else None
                                    idx, anchor = resolve_toc_item(src, ncx_href)
                                    fallback_num = (idx + 1) if idx >= 0 else (len(toc_list) + 1)
                                    title_text = title if title else f"{fallback_num}장"
                                    toc_list.append({
                                        'title': title_text,
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
                        # 챕터 조회(get_epub_chapter)는 spine_itemrefs 목록 하나만 필요한데,
                        # 매 챕터 요청마다 TOC까지 포함된 전체 메타(잠재적으로 수백 챕터의 목차 텍스트)를
                        # Redis에서 통째로 가져와 역직렬화하는 건 낭비이므로 가벼운 spine 전용 캐시를 별도로 둔다.
                        TextEpubContentService._set_cached_spine(db_type, book_id, spine_itemrefs)
                    except Exception as r_err:
                        print(f"[Redis Cache Put ERROR] {r_err}")

                return result, None
        except Exception as e:
            return None, f"EPUB meta parsing failed: {e}"

    @staticmethod
    def _spine_cache_key(db_type, book_id):
        return f"cache:epub:spine:book:{db_type}:{book_id}" if book_id else None

    @staticmethod
    def _set_cached_spine(db_type, book_id, spine_itemrefs):
        cache_key = TextEpubContentService._spine_cache_key(db_type, book_id)
        if not cache_key:
            return
        import json
        from utils.redis_helper import redis_set
        redis_set(cache_key, json.dumps(spine_itemrefs, ensure_ascii=False), ex=86400)

    @staticmethod
    def _get_spine_itemrefs(file_path, book_id, db_type):
        """챕터 콘텐츠 추출에 필요한 spine_itemrefs만 최소 비용으로 조회.
        (전체 메타는 TOC까지 포함해 무거우므로, 챕터 요청마다 반복 조회하는 용도로는
        가벼운 spine 전용 캐시를 우선 사용하고, 없을 때만 전체 메타 파싱으로 폴백한다.)"""
        cache_key = TextEpubContentService._spine_cache_key(db_type, book_id)
        if cache_key:
            try:
                import json
                from utils.redis_helper import redis_get
                cached = redis_get(cache_key)
                if cached:
                    return json.loads(cached), None
            except Exception as r_err:
                print(f"[Redis Cache Get ERROR] {r_err}")

        meta, err = TextEpubContentService.get_epub_meta(file_path, book_id, db_type)
        if err or not meta or 'spine_itemrefs' not in meta:
            return None, err or 'EPUB metadata load failed'
        return meta['spine_itemrefs'], None

    @staticmethod
    def _chapter_cache_key(db_type, book_id, chapter_idx):
        return f"cache:epub:ch:book:{db_type}:{book_id}:{chapter_idx}" if book_id else None

    @staticmethod
    def _get_cached_chapter(db_type, book_id, chapter_idx):
        cache_key = TextEpubContentService._chapter_cache_key(db_type, book_id, chapter_idx)
        if not cache_key:
            return None
        try:
            import json
            from utils.redis_helper import redis_get
            cached = redis_get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as r_err:
            print(f"[Redis Cache Get ERROR] {r_err}")
        return None

    @staticmethod
    def _resolve_opf_dir(zf):
        """열려 있는 zip에서 META-INF/container.xml을 읽어 OPF 파일이 위치한 디렉터리를 반환.
        배치 추출 시 챕터 개수만큼 반복하지 않고 한 번만 호출하기 위해 분리."""
        import xml.etree.ElementTree as ET

        container_data = zf.read('META-INF/container.xml')
        root = ET.fromstring(container_data)
        ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
        rootfile = root.find('.//ns:rootfile', ns)
        if rootfile is None:
            rootfile = root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
        opf_path = rootfile.attrib.get('full-path')
        return os.path.dirname(opf_path)

    @staticmethod
    def _extract_and_cache_chapter(zf, opf_dir, spine_itemrefs, chapter_idx, book_id, db_type):
        """이미 열려 있는 zip(zf)에서 챕터 하나를 추출/정제하고 개별 Redis 캐시에 저장.
        단일 조회(get_epub_chapter)와 배치 조회(get_epub_chapters_batch)가 공유하는 핵심 로직."""
        rel_href = spine_itemrefs[chapter_idx]
        clean_rel_href = urllib.parse.unquote(rel_href.split('#')[0])
        full_href = posixpath.join(opf_dir, clean_rel_href).replace('\\', '/') if opf_dir else clean_rel_href

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
        parser = _EPUBBodyHTMLParser(full_href, book_id, db_type)
        parser.feed(html_str)
        chapter_content = parser.get_content()
        # 연속된 빈 줄(여러 개의 <br/> 또는 빈 <p></p>)이 원본에 많으면
        # 행간 설정과 무관하게 문단 사이 공백이 과도하게 넓어 보이므로 1개로 축소
        chapter_content = re.sub(r'(?:\s*<br/>\s*){2,}', '<br/>', chapter_content)
        chapter_content = re.sub(r'(?:<p(?: id="[^"]*")?>\s*</p>\s*){2,}', lambda m: m.group(0).split('</p>')[0] + '</p>', chapter_content)

        h_match = re.search(r'<h[1-6]>(.*?)</h[1-6]>', chapter_content, re.IGNORECASE)
        if h_match:
            ch_title = html.unescape(re.sub('<[^<]+?>', '', h_match.group(1))).strip()
        else:
            ch_title = f"Chapter {chapter_idx + 1}"

        result = {
            'chapter_idx': chapter_idx,
            'title': ch_title,
            'content': chapter_content,
            'total_chapters': len(spine_itemrefs)
        }

        cache_key = TextEpubContentService._chapter_cache_key(db_type, book_id, chapter_idx)
        if cache_key:
            try:
                import json
                from utils.redis_helper import redis_set
                redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=86400)
            except Exception as r_err:
                print(f"[Redis Cache Put ERROR] {r_err}")

        return result, None

    @staticmethod
    def get_epub_chapter(file_path, book_id, db_type, chapter_idx):
        """요청된 특정 챕터(chapter_idx)만 0.01초 내 단독 추출 및 변환"""
        import zipfile

        chapter_idx = int(chapter_idx)
        if not os.path.exists(file_path):
            return None, 'File not found'

        cached = TextEpubContentService._get_cached_chapter(db_type, book_id, chapter_idx)
        if cached:
            return cached, None

        try:
            spine_itemrefs, err = TextEpubContentService._get_spine_itemrefs(file_path, book_id, db_type)
            if err or spine_itemrefs is None:
                return None, f"EPUB metadata load failed: {err}"

            if chapter_idx < 0 or chapter_idx >= len(spine_itemrefs):
                return None, 'Chapter index out of range'

            with zipfile.ZipFile(file_path, 'r') as zf:
                opf_dir = TextEpubContentService._resolve_opf_dir(zf)
                result, err = TextEpubContentService._extract_and_cache_chapter(
                    zf, opf_dir, spine_itemrefs, chapter_idx, book_id, db_type
                )
                if err:
                    return None, err
                return result, None
        except Exception as e:
            return None, f"EPUB chapter parsing failed: {e}"

    @staticmethod
    def get_epub_chapters_batch(file_path, book_id, db_type, chapter_indices):
        """여러 챕터를 한 번의 zip open으로 묶어서 추출 (프리페치 시 챕터 수만큼 zip을
        반복해서 여는 것을 방지하기 위한 배치 진입점). 개별 챕터 실패는 건너뛰고 나머지는
        정상 반환하며, 실패한 챕터는 프론트의 기존 개별 재시도 로직에 맡긴다."""
        import zipfile

        if not os.path.exists(file_path):
            return None, 'File not found'

        try:
            requested = sorted({int(i) for i in chapter_indices})
        except (TypeError, ValueError):
            return None, 'Invalid chapter_idx list'
        if not requested:
            return [], None

        spine_itemrefs, err = TextEpubContentService._get_spine_itemrefs(file_path, book_id, db_type)
        if err or spine_itemrefs is None:
            return None, f"EPUB metadata load failed: {err}"

        valid_indices = [i for i in requested if 0 <= i < len(spine_itemrefs)]
        if not valid_indices:
            return [], None

        results = {}
        missing = []
        for idx in valid_indices:
            cached = TextEpubContentService._get_cached_chapter(db_type, book_id, idx)
            if cached:
                results[idx] = cached
            else:
                missing.append(idx)

        if missing:
            try:
                with zipfile.ZipFile(file_path, 'r') as zf:
                    opf_dir = TextEpubContentService._resolve_opf_dir(zf)
                    for idx in missing:
                        chapter_result, chapter_err = TextEpubContentService._extract_and_cache_chapter(
                            zf, opf_dir, spine_itemrefs, idx, book_id, db_type
                        )
                        if chapter_result:
                            results[idx] = chapter_result
                        # 챕터 하나가 실패해도(chapter_err) 배치 전체를 실패시키지 않고 건너뜀
            except Exception as e:
                # zip 자체를 못 열었으면 이미 캐시로 채운 결과라도 반환 (완전 실패는 아님)
                print(f"[EPUB Batch] zip open failed for {file_path}: {e}")

        return [results[idx] for idx in valid_indices if idx in results], None

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
        """EPUB 내 특정 상대경로 리소스(이미지 등)를 (data, mime, error)로 반환.

        기존에는 요청마다 zip 파일을 새로 열고 원본 해상도를 그대로 서빙해,
        원격(GDrive 등) 경로거나 이미지가 큰 EPUB에서 체감 로딩이 느렸다.
        - zip 파일 오픈은 utils.cache_helper.get_zip_file_hybrid로 재사용(원격 경로는
          로컬 디스크 캐시/시크 최적화까지 자동 적용됨, 코믹 뷰어와 동일 인프라).
        - 추출한 이미지는 뷰어 실제 표시 폭 기준으로 리사이즈해 디스크에 WebP로
          캐시해두고, 다음 요청부터는 zip을 열 필요 없이 캐시 파일만 서빙한다.
        """
        import hashlib
        from utils.cache_helper import get_zip_file_hybrid, get_zip_read_lock

        normalized_path = resource_path.replace('\\', '/')
        cache_key = hashlib.md5(f"{file_path}::{normalized_path}".encode('utf-8')).hexdigest()
        os.makedirs(EPUB_IMAGE_CACHE_DIR, exist_ok=True)
        cache_path_webp = os.path.join(EPUB_IMAGE_CACHE_DIR, f"{cache_key}.webp")
        cache_path_orig = os.path.join(EPUB_IMAGE_CACHE_DIR, f"{cache_key}.orig")

        def _read_cached():
            if os.path.exists(cache_path_webp) and os.path.getsize(cache_path_webp) > 0:
                with open(cache_path_webp, 'rb') as f:
                    return f.read(), 'image/webp'
            if os.path.exists(cache_path_orig) and os.path.getsize(cache_path_orig) > 0:
                import mimetypes
                mime, _ = mimetypes.guess_type(normalized_path)
                with open(cache_path_orig, 'rb') as f:
                    return f.read(), (mime or 'image/jpeg')
            return None, None

        cached_data, cached_mime = _read_cached()
        if cached_data is not None:
            return cached_data, cached_mime, None

        with get_zip_read_lock(file_path):
            # 락 대기 중 다른 요청이 이미 캐시를 만들어뒀을 수 있으므로 재확인
            cached_data, cached_mime = _read_cached()
            if cached_data is not None:
                return cached_data, cached_mime, None

            zf = get_zip_file_hybrid(file_path)
            if zf is None:
                return None, None, 'File not found'

            try:
                raw_data = zf.read(normalized_path)
            except KeyError:
                raw_data = None
                for name in zf.namelist():
                    if name.lower() == normalized_path.lower():
                        raw_data = zf.read(name)
                        break
                if raw_data is None:
                    return None, None, 'Resource not found'
            except Exception as e:
                return None, None, str(e)

            try:
                import io
                from PIL import Image
                with Image.open(io.BytesIO(raw_data)) as img:
                    img = img.convert('RGBA' if img.mode in ('RGBA', 'LA', 'P') else 'RGB')
                    if max(img.size) > EPUB_IMAGE_MAX_SIDE:
                        ratio = EPUB_IMAGE_MAX_SIDE / max(img.size)
                        new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
                        img = img.resize(new_size, Image.LANCZOS)
                    img.save(cache_path_webp, 'WEBP', quality=85, method=4)
                with open(cache_path_webp, 'rb') as f:
                    return f.read(), 'image/webp', None
            except Exception as e:
                # PIL이 못 여는 포맷(svg 등)은 원본 그대로 캐시/서빙
                print(f"[EPUB-Image] Resize failed, caching original instead ({normalized_path}): {e}")
                try:
                    with open(cache_path_orig, 'wb') as f:
                        f.write(raw_data)
                except Exception as cache_err:
                    print(f"[EPUB-Image] Original cache write failed: {cache_err}")
                import mimetypes
                mime, _ = mimetypes.guess_type(normalized_path)
                return raw_data, (mime or 'image/jpeg'), None
