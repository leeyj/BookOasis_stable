# -*- coding: utf-8 -*-
"""EPUB → e-paper 최적화 EPUB (프로필 v1).

구조 보존 규칙 (kosync 위치 /body/DocFragment[N]/body/p[M] 가 원본과 같아야 한다):
- spine 항목의 수와 순서를 바꾸지 않는다. 챕터를 나누거나 합치지 않는다.
- XHTML의 요소를 더하거나 빼지 않는다. 속성(style, 그림 경로)과 <head> 안의 <style> 내용만 바꾼다.
- 깨진 XHTML은 libxml2 복구 결과를 쓰고 보고서에 남긴다(KOReader crengine 복구 결과와 다를 수 있다).

바꾸는 것: 그림(화면 크기·2색 디더링 PNG), CSS(css.py 허용 목록), 폰트 삭제, 인코딩 UTF-8 통일,
빠진 목차(ncx/nav) 생성, OPF에 프로필 표식. 같은 입력이면 같은 바이트가 나온다.
"""
import html.entities
import posixpath
import re
from urllib.parse import quote, unquote

from lxml import etree

from services.epaper import css as css_filter
from services.epaper import images, profile, text, zipio

NS_OPF = 'http://www.idpf.org/2007/opf'
NS_DC = 'http://purl.org/dc/elements/1.1/'
NS_CONTAINER = 'urn:oasis:names:tc:opendocument:xmlns:container'
NS_NCX = 'http://www.daisy.org/z3986/2005/ncx/'
NS_XHTML = 'http://www.w3.org/1999/xhtml'
NS_EPUB = 'http://www.idpf.org/2007/ops'
NS_XLINK = 'http://www.w3.org/1999/xlink'

FONT_OBFUSCATION = ('http://www.idpf.org/2008/embedding', 'http://ns.adobe.com/pdf/enc#RC')
FONT_EXTS = ('.ttf', '.otf', '.woff', '.woff2', '.eot', '.ttc', '.fon')
IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp')
XHTML_TYPES = ('application/xhtml+xml', 'text/html')
NCX_TYPE = 'application/x-dtbncx+xml'

_XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=True,
                              remove_blank_text=False, strip_cdata=False)
_RECOVER_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=True,
                                  remove_blank_text=False, recover=True)
_XML_DECL = re.compile(r'^\s*<\?xml[^>]*\?>', re.S)
_ENCODING_DECL = re.compile(rb'^\s*<\?xml[^>]*encoding=["\']([A-Za-z0-9._-]+)["\']', re.S)
_ENTITY = re.compile(r'&([A-Za-z][A-Za-z0-9]*);')
_XML_BUILTIN_ENTITIES = {'amp', 'lt', 'gt', 'quot', 'apos'}


class UnsupportedEpub(ValueError):
    """변환할 수 없는 EPUB (DRM, OPF 없음 등)."""


# ---- 공용 도우미 ----

def _decode_markup(data):
    """XML/XHTML 바이트 → str (선언된 인코딩 → UTF-8 → CP949 순)."""
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    elif data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16', errors='replace')
    m = _ENCODING_DECL.match(data)
    candidates = []
    if m:
        candidates.append(m.group(1).decode('ascii').lower())
    candidates += ['utf-8', 'cp949']
    for enc in candidates:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode('utf-8', errors='replace')


def _html_entities_to_chars(s):
    def repl(m):
        name = m.group(1)
        if name in _XML_BUILTIN_ENTITIES:
            return m.group(0)
        cp = html.entities.name2codepoint.get(name)
        return f'&#{cp};' if cp is not None else m.group(0)
    return _ENTITY.sub(repl, s)


def parse_markup(data):
    """bytes → (ElementTree, repaired: bool). 실패하면 복구 파서를 쓴다."""
    s = _decode_markup(data)
    s = _XML_DECL.sub('', s, count=1)
    s = text.strip_xml_invalid(_html_entities_to_chars(s))
    raw = s.encode('utf-8')
    try:
        return etree.ElementTree(etree.fromstring(raw, _XML_PARSER)), False
    except etree.XMLSyntaxError:
        root = etree.fromstring(raw, _RECOVER_PARSER)
        if root is None:
            raise UnsupportedEpub('unparseable document')
        return etree.ElementTree(root), True


def serialize(tree):
    return etree.tostring(tree, encoding='utf-8', xml_declaration=True)


def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _resolve(base_dir, href):
    href = unquote(href.split('#', 1)[0])
    return posixpath.normpath(posixpath.join(base_dir, href)) if base_dir else posixpath.normpath(href)


def _relative(from_dir, target):
    rel = posixpath.relpath(target, from_dir or '.')
    return quote(rel, safe='/-_.~')


def element_signature(tree):
    """구조 비교용: body 안 요소 태그의 문서 순서 목록."""
    root = tree.getroot()
    body = None
    for el in root.iter():
        if _local(el.tag) == 'body':
            body = el
            break
    if body is None:
        return []
    return [_local(el.tag) for el in body.iter() if isinstance(el.tag, str)]


# ---- 본체 ----

def optimize_epub(src_path, dst_path):
    """src EPUB → dst EPUB. 보고서 dict를 돌려준다."""
    entries = zipio.read_entries(src_path)
    report = {
        'profile': profile.PROFILE_VERSION, 'source_format': 'epub', 'spine_count': 0,
        'images_converted': 0, 'images_kept': 0, 'fonts_removed': 0, 'css_filtered': 0,
        'repaired_documents': [], 'generated_toc': [], 'warnings': [],
    }
    _check_drm(entries)
    entries.pop('META-INF/encryption.xml', None)

    opf_path = _find_opf(entries)
    opf_dir = posixpath.dirname(opf_path)
    opf_tree, opf_repaired = parse_markup(entries[opf_path])
    if opf_repaired:
        report['warnings'].append('opf repaired')
    opf_root = opf_tree.getroot()
    manifest = _child(opf_root, 'manifest')
    spine = _child(opf_root, 'spine')
    metadata = _child(opf_root, 'metadata')
    if manifest is None or spine is None or metadata is None:
        raise UnsupportedEpub('opf without manifest/spine/metadata')
    version = (opf_root.get('version') or '2.0').strip()

    items = {}
    for item in manifest:
        if _local(item.tag) != 'item' or not item.get('href'):
            continue
        items[item.get('id')] = item
    spine_ids = [ref.get('idref') for ref in spine if _local(ref.tag) == 'itemref']
    report['spine_count'] = len(spine_ids)

    # 1) 폰트 삭제
    for item_id, item in list(items.items()):
        path = _resolve(opf_dir, item.get('href'))
        media = (item.get('media-type') or '').lower()
        if media.startswith('font/') or 'font' in media or path.lower().endswith(FONT_EXTS):
            entries.pop(path, None)
            manifest.remove(item)
            del items[item_id]
            report['fonts_removed'] += 1
    for name in [n for n in entries if n.lower().endswith(FONT_EXTS)]:
        del entries[name]
        report['fonts_removed'] += 1

    # 2) 그림 변환 (이름이 바뀌면 renames에 기록)
    renames = {}
    taken = set(entries)
    for item_id in sorted(items):
        item = items[item_id]
        media = (item.get('media-type') or '').lower()
        if media not in IMAGE_TYPES:
            continue
        path = _resolve(opf_dir, item.get('href'))
        data = entries.get(path)
        if data is None:
            continue
        try:
            png, _size = images.to_epaper_png(data)
        except Exception as e:
            report['images_kept'] += 1
            report['warnings'].append(f'image kept as-is: {path} ({type(e).__name__})')
            continue
        new_path = path
        if not path.lower().endswith('.png'):
            stem = posixpath.splitext(path)[0]
            new_path = stem + '.png'
            n = 1
            while new_path in taken and new_path != path:
                new_path = f'{stem}_{n}.png'
                n += 1
            taken.add(new_path)
            del entries[path]
            renames[path] = new_path
            item.set('href', _relative(opf_dir, new_path))
        entries[new_path] = png
        item.set('media-type', 'image/png')
        report['images_converted'] += 1

    # 3) CSS
    for item_id in sorted(items):
        item = items[item_id]
        if (item.get('media-type') or '').lower() != 'text/css':
            continue
        path = _resolve(opf_dir, item.get('href'))
        if path in entries:
            entries[path] = css_filter.filter_stylesheet(_decode_markup(entries[path])).encode('utf-8')
            report['css_filtered'] += 1

    # 4) XHTML (spine + nav 등 manifest의 모든 문서)
    glyph_texts = []
    spine_set = set(spine_ids)
    for item_id in sorted(items):
        item = items[item_id]
        if (item.get('media-type') or '').lower() not in XHTML_TYPES:
            continue
        path = _resolve(opf_dir, item.get('href'))
        if path not in entries:
            continue
        tree, repaired = parse_markup(entries[path])
        if repaired:
            report['repaired_documents'].append(path)
        _rewrite_document(tree, posixpath.dirname(path), renames)
        if item_id in spine_set:
            glyph_texts.append(_body_text(tree))
        entries[path] = serialize(tree)

    # 5) 목차: 없으면 만든다
    ncx_item = _find_ncx(items, spine)
    nav_item = next((it for it in items.values() if 'nav' in (it.get('properties') or '').split()), None)
    toc = None
    if ncx_item is None or (version.startswith('3') and nav_item is None):
        toc = _collect_toc(entries, opf_dir, items, spine_ids, nav_item, ncx_item)
    if ncx_item is None:
        ncx_path = _unique_path(posixpath.join(opf_dir, 'toc.ncx') if opf_dir else 'toc.ncx', entries)
        entries[ncx_path] = _build_ncx(toc, _identifier(metadata), _title(metadata), posixpath.dirname(ncx_path))
        _add_item(manifest, items, 'mediaserver-ncx', _relative(opf_dir, ncx_path), NCX_TYPE)
        spine.set('toc', 'mediaserver-ncx')
        report['generated_toc'].append('ncx')
    if version.startswith('3') and nav_item is None:
        nav_path = _unique_path(posixpath.join(opf_dir, 'nav.xhtml') if opf_dir else 'nav.xhtml', entries)
        entries[nav_path] = _build_nav(toc, _title(metadata), posixpath.dirname(nav_path))
        _add_item(manifest, items, 'mediaserver-nav', _relative(opf_dir, nav_path), 'application/xhtml+xml', 'nav')
        report['generated_toc'].append('nav')

    # 6) OPF 표식 + modified
    _mark_profile(metadata, version)
    entries[opf_path] = serialize(opf_tree)

    report['glyphs'] = text.glyph_report(glyph_texts)
    _glyph_warning(report)
    zipio.write_epub(dst_path, entries)
    return report


def _glyph_warning(report):
    g = report['glyphs']
    if g['total_chars'] and (g['missing_chars'] / g['total_chars'] > profile.MISSING_GLYPH_RATIO_WARN
                             or g['missing_distinct'] >= profile.MISSING_GLYPH_DISTINCT_WARN):
        report['warnings'].append(
            f"glyphs missing from device font: {g['missing_chars']} chars, {g['missing_distinct']} kinds ({g['missing_sample']})")


def _check_drm(entries):
    data = entries.get('META-INF/encryption.xml')
    if not data:
        if 'META-INF/rights.xml' in entries:
            raise UnsupportedEpub('DRM protected (rights.xml)')
        return
    tree, _ = parse_markup(data)
    for el in tree.getroot().iter():
        if _local(el.tag) == 'EncryptionMethod' and el.get('Algorithm') not in FONT_OBFUSCATION:
            raise UnsupportedEpub('DRM protected (encryption.xml)')


def _find_opf(entries):
    data = entries.get('META-INF/container.xml')
    if data:
        tree, _ = parse_markup(data)
        for el in tree.getroot().iter():
            if _local(el.tag) == 'rootfile' and el.get('full-path'):
                path = posixpath.normpath(el.get('full-path'))
                if path in entries:
                    return path
    candidates = sorted(n for n in entries if n.lower().endswith('.opf'))
    if not candidates:
        raise UnsupportedEpub('no OPF')
    return candidates[0]


def _child(parent, name):
    for el in parent:
        if _local(el.tag) == name:
            return el
    return None


def _identifier(metadata):
    for el in metadata:
        if _local(el.tag) == 'identifier' and (el.text or '').strip():
            return el.text.strip()
    return 'urn:mediaserver:unknown'


def _title(metadata):
    for el in metadata:
        if _local(el.tag) == 'title' and (el.text or '').strip():
            return el.text.strip()
    return 'Untitled'


def _rewrite_document(tree, doc_dir, renames):
    """요소는 그대로 두고 속성과 <style> 내용만 바꾼다."""
    for el in tree.getroot().iter():
        if not isinstance(el.tag, str):
            continue
        name = _local(el.tag)
        style = el.get('style')
        if style is not None:
            cleaned = css_filter.filter_inline_style(style)
            if cleaned:
                el.set('style', cleaned)
            else:
                del el.attrib['style']
        if name == 'style' and el.text:
            el.text = css_filter.filter_stylesheet(el.text)
        if renames:
            for attr in ('src', 'href', f'{{{NS_XLINK}}}href', 'poster', 'data'):
                value = el.get(attr)
                if not value or value.startswith(('http:', 'https:', 'data:', '#', 'mailto:')):
                    continue
                target = _resolve(doc_dir, value)
                if target in renames:
                    frag = '#' + value.split('#', 1)[1] if '#' in value else ''
                    el.set(attr, _relative(doc_dir, renames[target]) + frag)


def _body_text(tree):
    for el in tree.getroot().iter():
        if _local(el.tag) == 'body':
            return ''.join(el.itertext())
    return ''


def _find_ncx(items, spine):
    toc_id = spine.get('toc')
    if toc_id and toc_id in items:
        return items[toc_id]
    for item_id in sorted(items):
        if (items[item_id].get('media-type') or '').lower() == NCX_TYPE:
            spine.set('toc', item_id)
            return items[item_id]
    return None


def _unique_path(path, entries):
    if path not in entries:
        return path
    stem, ext = posixpath.splitext(path)
    n = 1
    while f'{stem}_{n}{ext}' in entries:
        n += 1
    return f'{stem}_{n}{ext}'


def _add_item(manifest, items, item_id, href, media_type, properties=None):
    while item_id in items:
        item_id += '_'
    item = etree.SubElement(manifest, f'{{{NS_OPF}}}item')
    item.set('id', item_id)
    item.set('href', href)
    item.set('media-type', media_type)
    if properties:
        item.set('properties', properties)
    items[item_id] = item
    return item


# ---- 목차 수집 / 생성 ----

def _collect_toc(entries, opf_dir, items, spine_ids, nav_item, ncx_item):
    """[(제목, 대상 경로#조각)] - 기존 nav/ncx에서, 없으면 spine 문서 제목에서."""
    if ncx_item is not None:
        path = _resolve(opf_dir, ncx_item.get('href'))
        toc = _toc_from_ncx(entries.get(path), posixpath.dirname(path))
        if toc:
            return toc
    if nav_item is not None:
        path = _resolve(opf_dir, nav_item.get('href'))
        toc = _toc_from_nav(entries.get(path), posixpath.dirname(path))
        if toc:
            return toc
    toc = []
    for n, item_id in enumerate(spine_ids, 1):
        item = items.get(item_id)
        if item is None:
            continue
        path = _resolve(opf_dir, item.get('href'))
        data = entries.get(path)
        label = None
        if data:
            try:
                tree, _ = parse_markup(data)
                label = _document_heading(tree)
            except Exception:
                label = None
        toc.append((label or f'{n}', path))
    return toc


def _document_heading(tree):
    for level in ('h1', 'h2', 'h3', 'title'):
        for el in tree.getroot().iter():
            if _local(el.tag) == level:
                label = ' '.join(''.join(el.itertext()).split())
                if label:
                    return label[:120]
    return None


def _toc_from_ncx(data, base_dir):
    if not data:
        return []
    try:
        tree, _ = parse_markup(data)
    except Exception:
        return []
    toc = []
    for point in tree.getroot().iter():
        if _local(point.tag) != 'navPoint':
            continue
        label, src = None, None
        for el in point:
            if _local(el.tag) == 'navLabel':
                label = ' '.join(''.join(el.itertext()).split())
            elif _local(el.tag) == 'content':
                src = el.get('src')
        if label and src:
            frag = '#' + src.split('#', 1)[1] if '#' in src else ''
            toc.append((label, _resolve(base_dir, src) + frag))
    return toc


def _toc_from_nav(data, base_dir):
    if not data:
        return []
    try:
        tree, _ = parse_markup(data)
    except Exception:
        return []
    toc = []
    for nav in tree.getroot().iter():
        if _local(nav.tag) != 'nav' or nav.get(f'{{{NS_EPUB}}}type', nav.get('type', 'toc')) != 'toc':
            continue
        for a in nav.iter():
            if _local(a.tag) == 'a' and a.get('href'):
                label = ' '.join(''.join(a.itertext()).split())
                if label:
                    href = a.get('href')
                    frag = '#' + href.split('#', 1)[1] if '#' in href else ''
                    toc.append((label, _resolve(base_dir, href) + frag))
        break
    return toc


def _split_target(target):
    path, _, frag = target.partition('#')
    return path, ('#' + frag if frag else '')


def build_ncx_bytes(toc, identifier, title, base_dir):
    return _build_ncx(toc, identifier, title, base_dir)


def _build_ncx(toc, identifier, title, base_dir):
    root = etree.Element(f'{{{NS_NCX}}}ncx', nsmap={None: NS_NCX}, version='2005-1')
    head = etree.SubElement(root, f'{{{NS_NCX}}}head')
    for name, content in (('dtb:uid', identifier), ('dtb:depth', '1'),
                          ('dtb:totalPageCount', '0'), ('dtb:maxPageNumber', '0')):
        etree.SubElement(head, f'{{{NS_NCX}}}meta', name=name, content=content)
    doc_title = etree.SubElement(root, f'{{{NS_NCX}}}docTitle')
    etree.SubElement(doc_title, f'{{{NS_NCX}}}text').text = title
    nav_map = etree.SubElement(root, f'{{{NS_NCX}}}navMap')
    for n, (label, target) in enumerate(toc or [], 1):
        path, frag = _split_target(target)
        point = etree.SubElement(nav_map, f'{{{NS_NCX}}}navPoint', id=f'np{n}', playOrder=str(n))
        nav_label = etree.SubElement(point, f'{{{NS_NCX}}}navLabel')
        etree.SubElement(nav_label, f'{{{NS_NCX}}}text').text = label
        etree.SubElement(point, f'{{{NS_NCX}}}content', src=_relative(base_dir, path) + frag)
    return etree.tostring(root, encoding='utf-8', xml_declaration=True, pretty_print=True)


def build_nav_bytes(toc, title, base_dir):
    return _build_nav(toc, title, base_dir)


def _build_nav(toc, title, base_dir):
    root = etree.Element(f'{{{NS_XHTML}}}html', nsmap={None: NS_XHTML, 'epub': NS_EPUB})
    head = etree.SubElement(root, f'{{{NS_XHTML}}}head')
    etree.SubElement(head, f'{{{NS_XHTML}}}title').text = title
    body = etree.SubElement(root, f'{{{NS_XHTML}}}body')
    nav = etree.SubElement(body, f'{{{NS_XHTML}}}nav')
    nav.set(f'{{{NS_EPUB}}}type', 'toc')
    ol = etree.SubElement(nav, f'{{{NS_XHTML}}}ol')
    for label, target in toc or []:
        path, frag = _split_target(target)
        li = etree.SubElement(ol, f'{{{NS_XHTML}}}li')
        a = etree.SubElement(li, f'{{{NS_XHTML}}}a', href=_relative(base_dir, path) + frag)
        a.text = label
    if not len(ol):
        etree.SubElement(etree.SubElement(ol, f'{{{NS_XHTML}}}li'), f'{{{NS_XHTML}}}span').text = title
    return b'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n' + etree.tostring(root, encoding='utf-8', pretty_print=True)


def _mark_profile(metadata, version):
    nsmap_opf = f'{{{NS_OPF}}}'
    for el in list(metadata):
        if _local(el.tag) == 'meta' and el.get('name') == profile.PROFILE_META_NAME:
            metadata.remove(el)
    meta = etree.SubElement(metadata, f'{nsmap_opf}meta')
    meta.set('name', profile.PROFILE_META_NAME)
    meta.set('content', profile.PROFILE_VERSION)
    if version.startswith('3'):
        has_modified = any(_local(el.tag) == 'meta' and el.get('property') == 'dcterms:modified' for el in metadata)
        if not has_modified:
            mod = etree.SubElement(metadata, f'{nsmap_opf}meta')
            mod.set('property', 'dcterms:modified')
            mod.text = profile.FIXED_MODIFIED
