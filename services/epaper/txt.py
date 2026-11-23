# -*- coding: utf-8 -*-
"""TXT → EPUB3 (기기 프로필과 무관, 표식은 늘 v1). 인코딩을 감지해 UTF-8로 바꾸고 챕터를 나눈다.

챕터: '제1장', '1화', 'Chapter 1', '프롤로그' 같은 짧은 줄을 제목으로 본다.
- 본문 앞 목차처럼 제목끼리 TXT_HEADING_MIN_GAP 글자보다 가까우면 제목으로 쓰지 않는다.
- 번호가 있는 제목은 번호가 앞 제목보다 커야 한다(본문 중간의 '1화' 오탐 방지).
- 제목을 2개 미만 찾았거나 한 챕터가 너무 길면 공통 조각 길이(profile.TXT_SECTION_CHARS) 안팎에서 문단 경계로 나눈다.
결정적: 식별자는 원본 SHA-256에서 만들고 시각·UUID를 쓰지 않는다.
"""
import hashlib
import re
from xml.sax.saxutils import escape

from services.epaper import epub as epub_mod
from services.epaper import profile, text, zipio

_HEADING = re.compile(
    r'^(?:'
    r'(?:제\s*)?(\d{1,4})\s*(?:화|장|편|부|권|회|章|話)(?=$|[\s.:：\-–—()\[\]]).*'
    r'|chapter\s+(\d{1,4})\b.*'
    r'|第\s*(\d{1,4})\s*[章回話].*'
    r'|(?:프롤로그|에필로그|서막|서장|종장|終章|序章|외전|후기|작가\s*후기|prologue|epilogue)(?=$|[\s.:：\-–—()\[\]\d]).*'
    r')$', re.I)
_DIALOGUE = re.compile(r'["“”‘’「」『』?!？！]')

_CSS = ('body { text-align: justify; }\n'
        'p { text-indent: 1em; margin: 0; }\n'
        'h2 { text-align: center; font-weight: bold; page-break-before: always; }\n')


def _heading_number(line):
    m = _HEADING.match(line)
    if not m:
        return None, False
    num = next((g for g in m.groups() if g), None)
    return (int(num) if num else None), True


def _find_headings(lines):
    """lines: [str] → 제목 줄 인덱스 목록."""
    candidates = []
    offset = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s and len(s) <= profile.TXT_HEADING_MAX_LEN and not _DIALOGUE.search(s):
            num, ok = _heading_number(s)
            if ok:
                candidates.append((i, offset, num))
        offset += len(line) + 1
    # 다음 제목까지 너무 가까우면(목차) 뺀다
    spaced = []
    for k, cand in enumerate(candidates):
        nxt = candidates[k + 1][1] if k + 1 < len(candidates) else offset
        if nxt - cand[1] >= profile.TXT_HEADING_MIN_GAP:
            spaced.append(cand)
    # 번호 있는 제목은 최장 증가 수열만 쓴다 (목차·본문 속 '1화' 오탐 제거). 번호 없는 제목은 그대로 둔다.
    numbered = [(k, c[2]) for k, c in enumerate(spaced) if c[2] is not None]
    keep = set(_longest_increasing(numbered))
    result = [c[0] for k, c in enumerate(spaced) if c[2] is None or k in keep]
    return result


def _longest_increasing(pairs):
    """[(위치, 번호)] → 번호가 순증가하는 가장 긴 부분열의 위치 목록 (같은 길이면 앞쪽)."""
    n = len(pairs)
    best = [1] * n
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if pairs[j][1] < pairs[i][1] and best[j] + 1 > best[i]:
                best[i], prev[i] = best[j] + 1, j
    if not n:
        return []
    i = max(range(n), key=lambda k: (best[k], -k))
    out = []
    while i >= 0:
        out.append(pairs[i][0])
        i = prev[i]
    return out[::-1]


def _chunk(paragraphs, limit):
    """문단 목록을 limit 글자 안팎으로 나눈다."""
    chunks, cur, size = [], [], 0
    for p in paragraphs:
        if cur and size + len(p) > limit:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += len(p)
    if cur:
        chunks.append(cur)
    return chunks


def split_sections(body, title, section_chars=None):
    """본문 → [(제목, [문단])]. section_chars를 안 주면 공통 값(TXT_SECTION_CHARS)."""
    section_chars = section_chars or profile.TXT_SECTION_CHARS
    lines = body.split('\n')
    heads = _find_headings(lines)
    sections = []
    if len(heads) >= 2:
        bounds = heads + [len(lines)]
        pre = [l.strip() for l in lines[:heads[0]] if l.strip()]
        if pre:
            sections.append((title, pre))
        for k, start in enumerate(heads):
            paras = [l.strip() for l in lines[start + 1:bounds[k + 1]] if l.strip()]
            label = lines[start].strip()
            parts = _chunk(paras, section_chars) or [[]]
            for n, part in enumerate(parts):
                sections.append((label if n == 0 else f'{label} ({n + 1})', part))
    else:
        paras = [l.strip() for l in lines if l.strip()]
        parts = _chunk(paras, section_chars) or [[]]
        for n, part in enumerate(parts, 1):
            sections.append((title if len(parts) == 1 else f'{title} ({n})', part))
    return sections, len(heads) >= 2


def _xhtml(label, paras, show_heading):
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<!DOCTYPE html>',
           '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ko" xml:lang="ko">',
           f'<head><title>{escape(label)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>',
           '<body>']
    if show_heading:
        out.append(f'<h2>{escape(label)}</h2>')
    out += [f'<p>{escape(p)}</p>' for p in paras]
    out += ['</body>', '</html>', '']
    return '\n'.join(out).encode('utf-8')


def convert_txt(src_path, dst_path, title, author=''):
    """TXT → EPUB. 기기 프로필과 무관하게 늘 같은 바이트(조각 길이 TXT_SECTION_CHARS, 표식 TXT_PROFILE_ID)."""
    with open(src_path, 'rb') as f:
        data = f.read()
    body, encoding = text.decode_text(data)
    body = text.strip_xml_invalid(body.replace('\r\n', '\n').replace('\r', '\n'))
    # 프로필 공통 결과라 모든 기기에 적용된다. 줄 뒤집힘(RLM류)·이체자 선택자(IVS)는 다른 리더에서 지워도 잃는 것이 거의 없다
    body, invisible_removed = text.strip_invisible_lines(body)
    title = ' '.join(str(title or 'Untitled').split())[:200]
    author = ' '.join(str(author or '').split())[:200]
    sections, detected = split_sections(body, title, profile.TXT_SECTION_CHARS)

    identifier = 'urn:sha256:' + hashlib.sha256(data).hexdigest()
    entries = {
        'META-INF/container.xml': (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            '</rootfiles></container>\n').encode('utf-8'),
        'OEBPS/style.css': _CSS.encode('utf-8'),
    }
    manifest, spine, toc = [], [], []
    for n, (label, paras) in enumerate(sections, 1):
        name = f'c{n:04d}.xhtml'
        entries[f'OEBPS/{name}'] = _xhtml(label, paras, detected)
        manifest.append(f'<item id="c{n:04d}" href="{name}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{n:04d}"/>')
        toc.append((label, f'OEBPS/{name}'))
    entries['OEBPS/toc.ncx'] = epub_mod.build_ncx_bytes(toc, identifier, title, 'OEBPS')
    entries['OEBPS/nav.xhtml'] = epub_mod.build_nav_bytes(toc, title, 'OEBPS')
    creator = f'<dc:creator>{escape(author)}</dc:creator>' if author else ''
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="ko">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="bookid">{escape(identifier)}</dc:identifier>'
        f'<dc:title>{escape(title)}</dc:title>{creator}<dc:language>ko</dc:language>'
        f'<meta property="dcterms:modified">{profile.FIXED_MODIFIED}</meta>'
        f'<meta name="{profile.PROFILE_META_NAME}" content="{escape(profile.TXT_PROFILE_ID)}"/>'
        '</metadata>\n<manifest>'
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        '<item id="css" href="style.css" media-type="text/css"/>'
        + ''.join(manifest) +
        '</manifest>\n<spine toc="ncx">' + ''.join(spine) + '</spine>\n</package>\n')
    entries['OEBPS/content.opf'] = opf.encode('utf-8')
    zipio.write_epub(dst_path, entries)

    report = {
        'profile': profile.TXT_PROFILE_ID, 'source_format': 'txt', 'encoding': encoding,
        'chapters_detected': detected, 'spine_count': len(sections), 'warnings': [],
        'invisible_removed': invisible_removed,
        # TXT는 한 벌을 모든 기기가 받으므로 늘 낸다(BookOasis 펌웨어 폰트 기준). 보여 줄지는 받는 기기를 아는 쪽이 정한다
        'glyphs': text.glyph_report((label, p) for label, paras in sections for p in paras),
    }
    if encoding == 'cp949-replace':
        report['warnings'].append('text had undecodable bytes (replaced)')
    epub_mod._glyph_warning(report)
    return report
