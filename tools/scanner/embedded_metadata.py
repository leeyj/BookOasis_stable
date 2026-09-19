# -*- coding: utf-8 -*-
"""
embedded_metadata.py – 파일 안에 들어 있는 메타데이터(CBZ/ZIP의 ComicInfo.xml, EPUB의 OPF)를 읽는다.

사용자가 직접 누른 "즉시 스캔"(services/book_scan_service.py::scan_single_book)에서만 호출하며,
DB의 빈 칸을 채우는 용도다(덮어쓰지 않음 - repositories의 fill_empty_book_metadata 참고).
일반/예약 라이브러리 스캔은 이 모듈을 쓰지 않는다: 이미 스캔된 수십만 개 파일을 원격 마운트에서
다시 여는 부하를 만들지 않기 위해서다.

⚠️ tools/scanner/metadata/ 폴더는 사이드카 파서 로더가 통째로 임포트하는 위치라 이 파일을 거기에 두지 않는다.
PDF는 파서가 세그폴트/OOM을 일으킬 수 있고 Info 사전의 작가 값이 프로그램 이름인 경우가 흔해서 다루지 않는다.
"""
import os
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

from tools.scanner.metadata import clean_html_tags, parse_comicinfo_from_cbz

# ComicInfo.xml → 일반 스캔이 신규 CBZ에 채우는 필드와 같은 집합 (docs/guide_scanner_parser.md 매핑 표)
COMICINFO_FIELDS = (
    'author', 'cover_artist', 'teams', 'locations', 'characters', 'books_lv',
    'publisher', 'summary', 'release_date', 'genre', 'tags',
)
# EPUB은 장르(dc:subject)가 분류 문자열이라 잡음이 많아 제외한다.
EPUB_FIELDS = ('author', 'publisher', 'summary', 'release_date', 'isbn')

# 비신뢰 파일이라 읽는 XML 크기를 제한한다.
_MAX_CONTAINER_BYTES = 256 * 1024
_MAX_OPF_BYTES = 2 * 1024 * 1024

_CONTAINER_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'
_DC_NS = 'http://purl.org/dc/elements/1.1/'
_OPF_NS = 'http://www.idpf.org/2007/opf'
_AUTHOR_ROLES = ('aut', 'author', 'cre')
_ARTIST_ROLES = ('art', 'ill', 'cov')


def _local_name(tag):
    return tag.rsplit('}', 1)[-1].lower()


def _text(element):
    return ''.join(element.itertext()).strip() if element is not None else ''


def _unique_join(values):
    result, seen = [], set()
    for value in values:
        value = re.sub(r'\s+', ' ', str(value or '')).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return ', '.join(result)


def _normalize_date(value):
    match = re.match(r'^\s*(\d{4})(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?', value or '')
    if not match:
        return ''
    year, month, day = match.groups()
    month, day = int(month or 1), int(day or 1)
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return ''
    return f'{year}-{month:02d}-{day:02d}'


def _valid_isbn(compact):
    if len(compact) == 10:
        return sum((10 - i) * (10 if char == 'X' else int(char))
                   for i, char in enumerate(compact)) % 11 == 0
    if len(compact) == 13 and compact.isdigit():
        check = sum(int(char) * (1 if i % 2 == 0 else 3) for i, char in enumerate(compact[:12]))
        return (10 - check % 10) % 10 == int(compact[-1])
    return False


def _isbn_from_identifier(value, explicitly_isbn):
    value = str(value or '').strip()
    match = re.search(r'(?:urn:isbn:|isbn(?:-1[03])?\s*:?\s*)([0-9Xx -]+)', value, re.IGNORECASE)
    if match:
        candidate = match.group(1)
    elif re.fullmatch(r'[0-9Xx -]+', value) or explicitly_isbn:
        candidate = value
    else:
        return ''
    compact = re.sub(r'[^0-9X]', '', candidate.upper())
    return compact if _valid_isbn(compact) else ''


def parse_epub_opf(opf):
    """이미 파싱된 EPUB 패키지 문서(OPF)에서 작가/출판사/줄거리/출간일/ISBN을 추출한다."""
    metadata = {}
    package = next((e for e in opf.iter() if _local_name(e.tag) == 'metadata'), None)
    if package is None:
        return metadata

    def dc_values(name):
        return [_text(e) for e in package.iter() if e.tag == f'{{{_DC_NS}}}{name}' and _text(e)]

    role_by_id, identifier_types = {}, set()
    for element in package.iter():
        if _local_name(element.tag) != 'meta':
            continue
        prop = element.get('property', '').lower()
        refines = element.get('refines', '').lstrip('#')
        if prop == 'role' and refines:
            role_by_id[refines] = _text(element).lower()
        elif prop == 'identifier-type' and refines:
            identifier_types.add(refines)

    # 작가: 역할이 표시된 경우 글 작가(aut)만, 역할이 하나도 없으면 전부 작가로 본다(그림 작가는 제외).
    authors, unclassified, has_roles = [], [], False
    for creator in (e for e in package.iter() if e.tag == f'{{{_DC_NS}}}creator' and _text(e)):
        role = (creator.get(f'{{{_OPF_NS}}}role') or creator.get('role')
                or role_by_id.get(creator.get('id', ''), '')).lower()
        if role:
            has_roles = True
        if role in _AUTHOR_ROLES:
            authors.append(_text(creator))
        elif not role:
            unclassified.append(_text(creator))
    if authors:
        metadata['author'] = _unique_join(authors)
    elif not has_roles and unclassified:
        metadata['author'] = _unique_join(unclassified)

    publishers = dc_values('publisher')
    if publishers:
        metadata['publisher'] = _unique_join(publishers)
    descriptions = dc_values('description')
    if descriptions:
        summary = clean_html_tags('\n'.join(descriptions))
        if summary:
            metadata['summary'] = summary

    for value in dc_values('date'):
        release_date = _normalize_date(value)
        if release_date:
            metadata['release_date'] = release_date
            break

    for identifier in (e for e in package.iter() if e.tag == f'{{{_DC_NS}}}identifier'):
        scheme = identifier.get(f'{{{_OPF_NS}}}scheme', '').lower()
        explicitly_isbn = 'isbn' in scheme or identifier.get('id', '') in identifier_types
        isbn = _isbn_from_identifier(_text(identifier), explicitly_isbn)
        if isbn:
            metadata['isbn'] = isbn
            break
    return metadata


def _read_member(archive, name, max_bytes):
    """ZIP 멤버를 크기 제한 안에서만 읽는다(넘으면 None)."""
    try:
        info = archive.getinfo(name)
    except KeyError:
        return None
    if info.file_size > max_bytes:
        return None
    return archive.read(info)


def parse_epub_metadata(file_path):
    with zipfile.ZipFile(file_path, 'r') as epub:
        container_bytes = _read_member(epub, 'META-INF/container.xml', _MAX_CONTAINER_BYTES)
        if container_bytes is None:
            return {}
        container = ET.fromstring(container_bytes)
        rootfile = container.find(f'.//{{{_CONTAINER_NS}}}rootfile')
        if rootfile is None:
            rootfile = next((e for e in container.iter() if _local_name(e.tag) == 'rootfile'), None)
        opf_path = posixpath.normpath((rootfile.get('full-path') if rootfile is not None else '').lstrip('/'))
        # 경로 탈출/빈 경로 거부 - OPF는 아카이브 안의 파일이어야 한다.
        if not opf_path or opf_path in ('.', '..') or opf_path.startswith('../'):
            return {}
        opf_bytes = _read_member(epub, opf_path, _MAX_OPF_BYTES)
        if opf_bytes is None:
            return {}
        return parse_epub_opf(ET.fromstring(opf_bytes))


def read_embedded_metadata(file_path, file_format=None):
    """파일 형식에 맞는 내장 메타데이터를 {필드: 값}으로 반환한다. 읽을 수 없으면 빈 dict(예외 없음)."""
    fmt = (file_format or os.path.splitext(str(file_path or ''))[1].lstrip('.')).lower()
    try:
        if fmt in ('cbz', 'zip'):
            raw = parse_comicinfo_from_cbz(file_path) or {}
            fields = COMICINFO_FIELDS
        elif fmt == 'epub':
            raw = parse_epub_metadata(file_path) or {}
            fields = EPUB_FIELDS
        else:
            return {}
    except Exception as error:
        print(f"[EmbeddedMetadata] 내장 메타데이터 읽기 실패(무시): {os.path.basename(str(file_path))}: {error}")
        return {}
    return {field: str(raw[field]).strip() for field in fields if raw.get(field) and str(raw[field]).strip()}
