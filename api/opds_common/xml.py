# -*- coding: utf-8 -*-
"""Shared XML and paging helpers for OPDS style feeds."""

import html
import mimetypes
from datetime import datetime
from urllib.parse import urlencode

from flask import Response


def escape_xml(text: str) -> str:
    return html.escape(str(text), quote=True)


def _get_forwarded_header(request, name: str) -> str:
    raw = (request.headers.get(name) or '').strip()
    if not raw:
        return ''
    return raw.split(',')[0].strip()


def _normalize_prefix(prefix: str) -> str:
    prefix = (prefix or '').strip()
    if not prefix:
        return ''
    if not prefix.startswith('/'):
        prefix = f'/{prefix}'
    return prefix.rstrip('/')


def get_external_base_url(request) -> str:
    scheme = _get_forwarded_header(request, 'X-Forwarded-Proto') or request.scheme
    host = _get_forwarded_header(request, 'X-Forwarded-Host') or request.host
    forwarded_port = _get_forwarded_header(request, 'X-Forwarded-Port')
    prefix = _normalize_prefix(_get_forwarded_header(request, 'X-Forwarded-Prefix'))

    if forwarded_port and ':' not in host:
        is_default_port = (scheme == 'http' and forwarded_port == '80') or (scheme == 'https' and forwarded_port == '443')
        if not is_default_port:
            host = f'{host}:{forwarded_port}'

    return f'{scheme}://{host}{prefix}'


def build_external_request_url(request, query_params=None) -> str:
    base = f"{get_external_base_url(request)}{request.path}"
    if query_params is None:
        query_string = request.query_string.decode('utf-8')
    else:
        query_string = urlencode(query_params, doseq=True)
    if query_string:
        return f'{base}?{query_string}'
    return base


def get_page_params(args, default_page_size: int, max_page_size: int):
    try:
        page = int(args.get('page', '1'))
    except ValueError:
        page = 1
    try:
        page_size = int(args.get('page_size', str(default_page_size)))
    except ValueError:
        page_size = default_page_size

    page = max(page, 1)
    page_size = min(max(page_size, 1), max_page_size)
    offset = (page - 1) * page_size
    return page, page_size, offset


def build_opds_xml(request, title: str, entries: list, start_path: str, search_path: str, next_link: str = None) -> str:
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
            if entry.get('cover'):
                cover_url = f"{base_url}/covers/{escape_xml(entry['cover'])}"
                cover_mime = entry.get('cover_mime') or mimetypes.guess_type(entry['cover'])[0] or 'image/png'
                lines.append(f'    <link rel="http://opds-spec.org/image" href="{escape_xml(cover_url)}" type="{escape_xml(cover_mime)}"/>')
                lines.append(f'    <link rel="http://opds-spec.org/image/thumbnail" href="{escape_xml(cover_url)}" type="{escape_xml(cover_mime)}"/>')
        elif entry['type'] == 'acquisition':
            lines.append(
                f'    <link rel="http://opds-spec.org/acquisition" '
                f'href="{escape_xml(href)}" type="{escape_xml(entry["mime"])}"/>'
            )
            if entry.get('cover'):
                cover_url = f"{base_url}/covers/{escape_xml(entry['cover'])}"
                cover_mime = entry.get('cover_mime') or mimetypes.guess_type(entry['cover'])[0] or 'image/png'
                lines.append(f'    <link rel="http://opds-spec.org/image" href="{escape_xml(cover_url)}" type="{escape_xml(cover_mime)}"/>')
                lines.append(f'    <link rel="http://opds-spec.org/image/thumbnail" href="{escape_xml(cover_url)}" type="{escape_xml(cover_mime)}"/>')
        lines.append('  </entry>')

    lines.append('</feed>')
    return '\n'.join(lines)


def atom_response(xml: str) -> Response:
    return Response(xml, mimetype='application/atom+xml; charset=utf-8')
