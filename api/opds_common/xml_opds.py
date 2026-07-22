# -*- coding: utf-8 -*-
"""표준 OPDS (Moon+ Reader, Chunky, Calibre 등) 전용 XML 빌더 모듈"""

import mimetypes
from datetime import datetime
from api.opds_common.xml import (
    escape_xml,
    get_external_base_url,
    build_external_request_url,
)


def build_opds_standard_xml(request, title: str, entries: list, start_path: str, search_path: str, next_link: str = None) -> str:
    """Moon+ Reader 등 표준 OPDS 앱 전용 XML (Acquisition 다운로드 중심)"""
    base_url = get_external_base_url(request)
    current_url = build_external_request_url(request)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">',
        f'  <id>{escape_xml(current_url)}</id>',
        f'  <title>{escape_xml(title)}</title>',
        f'  <updated>{now}</updated>',
        f'  <link rel="self" href="{escape_xml(current_url)}" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>',
        f'  <link rel="start" href="{escape_xml(base_url + start_path)}" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>',
        f'  <link rel="search" href="{escape_xml(base_url + search_path)}" type="application/opensearchdescription+xml" title="Search Books"/>',
        f'  <link rel="search" href="{escape_xml(base_url + search_path)}?q={{searchTerms}}" type="application/atom+xml" title="Search Books"/>',
    ]
    if next_link:
        lines.append(
            f'  <link rel="next" href="{escape_xml(next_link)}" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>'
        )

    for entry in entries:
        lines += [
            '  <entry>',
            f'    <title>{escape_xml(entry["title"])}</title>',
            f'    <id>{escape_xml(entry["id"])}</id>',
            f'    <updated>{now}</updated>',
        ]
        if entry.get('summary'):
            lines.append(f'    <summary>{escape_xml(entry["summary"])}</summary>')

        href = f"{base_url}{entry['href']}"
        if entry['type'] == 'navigation':
            lines.append(
                f'    <link rel="subsection" href="{escape_xml(href)}" '
                f'type="application/atom+xml;profile=opds-catalog;kind=navigation"/>'
            )
            cover_url = None
            cover_mime = entry.get('cover_mime')
            if entry.get('cover_url'):
                cover_url = f"{base_url}{entry['cover_url']}"
            elif entry.get('cover'):
                cover_url = f"{base_url}/covers/{escape_xml(entry['cover'])}"
                cover_mime = cover_mime or mimetypes.guess_type(entry['cover'])[0] or 'image/png'
            if cover_url:
                cover_mime = cover_mime or 'image/png'
                lines.append(f'    <link rel="http://opds-spec.org/image" href="{escape_xml(cover_url)}" type="{escape_xml(cover_mime)}"/>')
                lines.append(f'    <link rel="http://opds-spec.org/image/thumbnail" href="{escape_xml(cover_url)}" type="{escape_xml(cover_mime)}"/>')
        elif entry['type'] == 'acquisition':
            # Moon+ Reader: open-book rel이 있어야 내장 뷰어로 직접 열림 (없으면 다운로드 창 뜸)
            lines.append(
                f'    <link rel="http://opds-spec.org/acquisition/open-book" '
                f'href="{escape_xml(href)}" type="{escape_xml(entry["mime"])}"/>'
            )
            # 표준 OPDS Acquisition (fallback - Chunky, Calibre 등 호환)
            lines.append(
                f'    <link rel="http://opds-spec.org/acquisition" '
                f'href="{escape_xml(href)}" type="{escape_xml(entry["mime"])}"/>'
            )
            cover_url = None
            cover_mime = entry.get('cover_mime')
            if entry.get('cover_url'):
                cover_url = f"{base_url}{entry['cover_url']}"
            elif entry.get('cover'):
                cover_url = f"{base_url}/covers/{escape_xml(entry['cover'])}"
                cover_mime = cover_mime or mimetypes.guess_type(entry['cover'])[0] or 'image/png'
            if cover_url:
                cover_mime = cover_mime or 'image/png'
                lines.append(f'    <link rel="http://opds-spec.org/image" href="{escape_xml(cover_url)}" type="{escape_xml(cover_mime)}"/>')
                lines.append(f'    <link rel="http://opds-spec.org/image/thumbnail" href="{escape_xml(cover_url)}" type="{escape_xml(cover_mime)}"/>')
        lines.append('  </entry>')

    lines.append('</feed>')
    return '\n'.join(lines)
