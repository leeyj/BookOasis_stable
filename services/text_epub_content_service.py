# -*- coding: utf-8 -*-
import os
import re


class TextEpubContentService:
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
                    'img',
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
                                        toc_list.append(
                                            {
                                                'title': a_tag.get_text(strip=True),
                                                'chapter_idx': idx,
                                                'anchor': anchor,
                                                'level': level,
                                            }
                                        )
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
                                    toc_list.append(
                                        {
                                            'title': title,
                                            'chapter_idx': idx,
                                            'anchor': anchor,
                                            'level': level,
                                        }
                                    )
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

                        chapters.append({'title': ch_title, 'content': chapter_content})
                    except KeyError:
                        continue

                return {
                    'title': title,
                    'chapters': chapters,
                    'toc': toc_list,
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
