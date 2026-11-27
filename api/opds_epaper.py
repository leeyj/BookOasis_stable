# -*- coding: utf-8 -*-
"""
opds_epaper.py – e-paper 리더 전용 OPDS 피드 /opds-epaper/v1 (명세: docs/device-api.md)

표준 /opds 와 분리된 갈래다. 표준 피드(아이패드 KOReader 등)는 원본을 그대로 보내고, 이 피드만 변환본을 보낸다.
- 일반(general) 도서관의 EPUB/TXT만 보인다. 받기 링크는 모두 application/epub+zip.
- 변환 프로필은 로그인한 사용자의 "피드 기기" 설정(EPAPER_FEED_DEVICE, 없으면 v1)을 따른다. 주소의 v1은 피드 API 버전이다.
- 모든 목록은 한 페이지 PAGE_SIZE개, 다음 페이지는 rel="next". 기기는 한 페이지에 62항목까지만 담는다.
- 표지는 그레이스케일 JPEG(긴 변 480px 이하). 설명은 짧게, 제목·저자는 FAT32 파일명에 쓸 수 있게 다듬는다.
- 인증: Basic(표준 OPDS와 같은 계정·5분 캐시). 다운로드는 피드가 붙인 서명 토큰으로도 받을 수 있다.
"""
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

from flask import Blueprint, Response, g, request, send_file

from api.opds import _get_authenticated_user, _make_download_token, _verify_download_token
from api.opds_common.auth import unauthorized_response
from api.opds_common.xml import escape_xml, get_external_base_url
from api.cache import LRUCache

opds_epaper_bp = Blueprint('opds_epaper', __name__)

PREFIX = '/opds-epaper/v1'
DB_TYPE = 'general'
PAGE_SIZE = 40
SUMMARY_MAX = 200
TITLE_MAX = 80
AUTHOR_MAX = 40
FEED_CACHE_TTL = 300
NAV_TYPE = 'application/atom+xml;profile=opds-catalog;kind=navigation'
ACQ_TYPE = 'application/atom+xml;profile=opds-catalog;kind=acquisition'
_feed_cache = LRUCache(capacity=200)

_FAT_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
_TAG = re.compile(r'<[^>]+>')


# ---- 공용 ----

def clean_name(value, limit):
    """FAT32 파일명에 못 쓰는 문자 제거, 공백 정리, 길이 제한 (기기가 저자·제목으로 파일명을 만든다)."""
    s = _FAT_UNSAFE.sub(' ', str(value or ''))
    s = ' '.join(s.split()).strip(' .')
    if len(s) > limit:
        s = s[:limit].rstrip(' .')
    return s


def clean_summary(value):
    s = ' '.join(_TAG.sub(' ', str(value or '')).split())
    return s if len(s) <= SUMMARY_MAX else s[:SUMMARY_MAX - 1].rstrip() + '…'


def _user():
    user = _get_authenticated_user(is_adult=False)
    g.epaper_user = (user or {}).get('username')
    return user


def _feed_profile(user):
    from services import epaper_service
    return epaper_service.profile_for_user((user or {}).get('id'), 'feed')


def _unauthorized():
    auth = request.authorization
    if auth and auth.username:
        print(f"[EPAPER] auth failed user={clean_name(auth.username, 64)} path={request.path}")
    return unauthorized_response('BookOasis e-paper')


@opds_epaper_bp.after_request
def _log_request(response):
    if request.path.startswith(PREFIX):
        user = getattr(g, 'epaper_user', None)
        started = getattr(g, 'epaper_started', None)
        ms = f' ms={int((time.time() - started) * 1000)}' if started else ''
        # 첫 두 번은 인증 없이 와서 401이 정상이다(기기 동작) - 그건 남기지 않는다
        if user or response.status_code != 401:
            print(f"[EPAPER] {request.method} {request.path} user={user or '-'} status={response.status_code}{ms}")
    return response


@opds_epaper_bp.before_request
def _mark_start():
    g.epaper_started = time.time()


def _page():
    try:
        page = max(1, int(request.args.get('page', '1')))
    except ValueError:
        page = 1
    return page, (page - 1) * PAGE_SIZE


def _url(path, **params):
    base = get_external_base_url(request) + PREFIX + path
    query = '&'.join(f'{k}={quote(str(v), safe="")}' for k, v in params.items() if v is not None and v != '')
    return f'{base}?{query}' if query else base


def _now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _feed(title, entries, kind, next_url=None, up_url=None):
    now = _now()
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">',
             f'<id>urn:bookoasis:epaper:{escape_xml(request.path)}:{escape_xml(request.query_string.decode("latin-1"))}</id>',
             f'<title>{escape_xml(title)}</title>', f'<updated>{now}</updated>',
             f'<link rel="start" href="{escape_xml(_url(""))}" type="{NAV_TYPE}"/>',
             f'<link rel="search" href="{escape_xml(_url("/search"))}" type="application/opensearchdescription+xml"/>']
    if up_url:
        lines.append(f'<link rel="up" href="{escape_xml(up_url)}" type="{NAV_TYPE}"/>')
    if next_url:
        lines.append(f'<link rel="next" href="{escape_xml(next_url)}" type="{kind}"/>')
    for e in entries:
        lines += ['<entry>', f'<title>{escape_xml(e["title"])}</title>', f'<id>{escape_xml(e["id"])}</id>',
                  f'<updated>{now}</updated>']
        if e.get('author'):
            lines.append(f'<author><name>{escape_xml(e["author"])}</name></author>')
        if e.get('summary'):
            lines.append(f'<summary>{escape_xml(e["summary"])}</summary>')
        if e.get('nav'):
            lines.append(f'<link rel="subsection" href="{escape_xml(e["nav"])}" type="{e.get("nav_type", NAV_TYPE)}"/>')
        if e.get('acq'):
            lines.append(f'<link rel="http://opds-spec.org/acquisition" href="{escape_xml(e["acq"])}" type="application/epub+zip"/>')
        if e.get('cover'):
            lines.append(f'<link rel="http://opds-spec.org/image" href="{escape_xml(e["cover"])}" type="image/jpeg"/>')
            lines.append(f'<link rel="http://opds-spec.org/image/thumbnail" href="{escape_xml(e["cover"])}" type="image/jpeg"/>')
        lines.append('</entry>')
    lines.append('</feed>')
    return Response('\n'.join(lines), mimetype='application/atom+xml; charset=utf-8')


def _cached(key, build):
    hit = _feed_cache.get(key)
    if hit and time.time() - hit[1] < FEED_CACHE_TTL:
        return Response(hit[0], mimetype='application/atom+xml; charset=utf-8')
    response = build()
    _feed_cache.put(key, (response.get_data(as_text=True), time.time()))
    return response


def _book_entries(rows, user):
    entries = []
    for b in rows:
        token = _make_download_token(DB_TYPE, int(b['id']), int(user.get('id') or 0))
        title = clean_name(b.get('title'), TITLE_MAX) or f"book {b['id']}"
        entries.append({
            'id': f"urn:bookoasis:epaper:book:{DB_TYPE}:{b['id']}",
            'title': title,
            'author': clean_name(b.get('author'), AUTHOR_MAX),
            'summary': clean_summary(b.get('summary')),
            'acq': _url(f"/book/{b['id']}.epub", token=token),
            'cover': _url(f"/cover/{b['id']}.jpg", token=token) if b.get('cover_image') else None,
        })
    return entries


def _repo():
    from repositories.epaper_feed_repository import EpaperFeedRepository
    return EpaperFeedRepository


def _next(total, offset, count, path, **params):
    more = (offset + count < total) if total is not None else (count >= PAGE_SIZE)
    if not more:
        return None
    page = offset // PAGE_SIZE + 2
    return _url(path, page=page, **params)


# ---- 피드 ----

@opds_epaper_bp.route(PREFIX, methods=['GET'])
@opds_epaper_bp.route(PREFIX + '/', methods=['GET'])
def epaper_root():
    user = _user()
    if not user:
        return _unauthorized()

    def build():
        entries = [
            {'id': 'urn:bookoasis:epaper:recent', 'title': '신규 추가', 'nav': _url('/recent'), 'nav_type': ACQ_TYPE},
            {'id': 'urn:bookoasis:epaper:reading', 'title': '최근 읽은 책', 'nav': _url('/reading'), 'nav_type': ACQ_TYPE},
        ]
        for lib in _repo().list_libraries(DB_TYPE, user['id'], user.get('role'))[:PAGE_SIZE]:
            entries.append({'id': f"urn:bookoasis:epaper:library:{lib['id']}", 'title': clean_name(lib['name'], TITLE_MAX),
                            'summary': f"{int(lib['book_count'])}권", 'nav': _url(f"/library/{lib['id']}")})
        return _feed('BookOasis', entries, NAV_TYPE)
    return _cached(f"root:{user['id']}", build)


@opds_epaper_bp.route(PREFIX + '/library/<int:lib_id>', methods=['GET'])
def epaper_library(lib_id):
    user = _user()
    if not user:
        return _unauthorized()
    page, offset = _page()

    def build():
        rows, total = _repo().list_series(DB_TYPE, lib_id, user['id'], user.get('role'), PAGE_SIZE, offset)
        entries = []
        for s in rows:
            name = s['series_name'] or ''
            label = clean_name(name, TITLE_MAX) or '기타'
            entries.append({'id': f"urn:bookoasis:epaper:series:{lib_id}:{name}", 'title': label,
                            'summary': f"{int(s['book_count'])}권", 'nav_type': ACQ_TYPE,
                            'nav': _url(f"/library/{lib_id}/series", name=name or '-'),
                            'cover': _url(f"/cover/{s['cover_book_id']}.jpg",
                                          token=_make_download_token(DB_TYPE, int(s['cover_book_id']), int(user['id'])))
                            if s.get('cover_book_id') else None})
        return _feed('시리즈', entries, NAV_TYPE, next_url=_next(total, offset, len(rows), f'/library/{lib_id}'),
                     up_url=_url(''))
    return _cached(f"lib:{user['id']}:{lib_id}:{page}", build)


@opds_epaper_bp.route(PREFIX + '/library/<int:lib_id>/series', methods=['GET'])
def epaper_series(lib_id):
    user = _user()
    if not user:
        return _unauthorized()
    name = request.args.get('name', '')
    series = '' if name == '-' else name
    page, offset = _page()
    rows, total = _repo().list_books(DB_TYPE, lib_id, series, user['id'], user.get('role'), PAGE_SIZE, offset)
    return _feed(clean_name(series, TITLE_MAX) or '기타', _book_entries(rows, user), ACQ_TYPE,
                 next_url=_next(total, offset, len(rows), f'/library/{lib_id}/series', name=name),
                 up_url=_url(f'/library/{lib_id}'))


@opds_epaper_bp.route(PREFIX + '/recent', methods=['GET'])
def epaper_recent():
    user = _user()
    if not user:
        return _unauthorized()
    page, offset = _page()
    rows, total = _repo().recently_added(DB_TYPE, user['id'], user.get('role'), PAGE_SIZE, offset)
    return _feed('신규 추가', _book_entries(rows, user), ACQ_TYPE,
                 next_url=_next(total, offset, len(rows), '/recent') if page < 5 else None, up_url=_url(''))


@opds_epaper_bp.route(PREFIX + '/reading', methods=['GET'])
def epaper_reading():
    user = _user()
    if not user:
        return _unauthorized()
    page, offset = _page()
    rows, total = _repo().recently_read(DB_TYPE, user['id'], user.get('role'), PAGE_SIZE, offset)
    return _feed('최근 읽은 책', _book_entries(rows, user), ACQ_TYPE,
                 next_url=_next(total, offset, len(rows), '/reading') if page < 5 else None, up_url=_url(''))


@opds_epaper_bp.route(PREFIX + '/search', methods=['GET'])
def epaper_search():
    query = (request.args.get('q') or '').strip()
    if not query:
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">'
               '<ShortName>BookOasis</ShortName><Description>BookOasis e-paper</Description>'
               '<InputEncoding>UTF-8</InputEncoding><OutputEncoding>UTF-8</OutputEncoding>'
               f'<Url type="{ACQ_TYPE}" template="{escape_xml(_url("/search"))}?q={{searchTerms}}"/>'
               '</OpenSearchDescription>')
        return Response(xml, mimetype='application/opensearchdescription+xml; charset=utf-8')
    user = _user()
    if not user:
        return _unauthorized()
    page, offset = _page()
    rows, total = _repo().search(DB_TYPE, query, user['id'], user.get('role'), PAGE_SIZE, offset)
    return _feed(f'검색: {clean_name(query, 40)}', _book_entries(rows, user), ACQ_TYPE,
                 next_url=_next(total, offset, len(rows), '/search', q=query), up_url=_url(''))


# ---- 다운로드 / 표지 ----

def _download_user(book_id):
    user = _user()
    if user:
        return user
    token = request.args.get('token', '')
    if token and _verify_download_token(DB_TYPE, book_id, token):
        try:
            uid = int(token.rsplit(':', 1)[-1])
        except ValueError:
            return None
        from repositories.user_repository import UserRepository
        row = UserRepository.find_by_id('general', uid)
        if row:
            row = dict(row)
            g.epaper_user = row.get('username')
            return {'id': row['id'], 'username': row.get('username'), 'role': row.get('role')}
    return None


def _text_error(status, message, retry_after=None):
    res = Response(message + '\n', status=status, mimetype='text/plain; charset=utf-8')
    if retry_after:
        res.headers['Retry-After'] = str(int(retry_after))
    res.headers['Cache-Control'] = 'no-store'
    return res


class _CachedFileBody:
    """캐시 파일을 보내는 응답 본문. 다 보냈거나 연결이 끊겨 서버가 close()를 부르면 '전송 중' 표시를 푼다.
    (send_file 응답은 direct_passthrough라 call_on_close가 불리지 않는다.)"""

    def __init__(self, path):
        from services import epaper_service
        self._service = epaper_service
        self._path = path
        self._released = False
        epaper_service.acquire(path)

    def __iter__(self):
        self._gen = self._chunks()
        return self._gen

    def _chunks(self):
        try:
            with open(self._path, 'rb') as f:
                while True:
                    chunk = f.read(256 * 1024)
                    if not chunk:
                        break
                    yield chunk
        finally:
            self._release()

    def close(self):
        gen = getattr(self, '_gen', None)
        if gen is not None:
            gen.close()          # 열린 파일을 바로 닫는다 (Windows에서는 열린 파일을 바꿀 수 없다)
        self._release()

    def _release(self):
        if not self._released:
            self._released = True
            self._service.release(self._path)


def _send_cached(path, download_name, disposition, meta):
    import os
    size = os.path.getsize(path)
    response = Response(_CachedFileBody(path), mimetype='application/epub+zip', direct_passthrough=True)
    response.headers['Content-Length'] = str(size)
    response.headers['Content-Disposition'] = disposition
    response.headers['X-Epaper-Profile'] = str(meta.get('profile') or '')
    response.headers['X-Epaper-Digest'] = str(meta.get('digest') or '')
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


def _download_refusal(user, book_id):
    """Same rules as the web download (check_download_permission + check_book_rating_permission).
    Category permission is already applied by the feed repository (get_book), so it is not re-checked here."""
    from api.opds_common.permissions import refusal
    return refusal(DB_TYPE, book_id, user, need_download=True, check_category=False)


@opds_epaper_bp.route(PREFIX + '/book/<int:book_id>.epub', methods=['GET'])
def epaper_download(book_id):
    user = _download_user(book_id)
    if not user:
        return _unauthorized()
    book = _repo().get_book(DB_TYPE, book_id, user.get('id'), user.get('role'))
    if not book:
        return _text_error(404, '책을 찾을 수 없습니다.')
    refusal = _download_refusal(user, book_id)
    if refusal:
        print(f"[EPAPER] download refused book={book_id} user={user.get('username')} reason={refusal[0]}")
        if refusal[0] == 'not_found':
            return _text_error(404, '책을 찾을 수 없습니다.')
        return _text_error(403, refusal[1])
    from services import epaper_service
    try:
        epub_path, meta = epaper_service.get_book_epub(DB_TYPE, book, profile=_feed_profile(user))
    except epaper_service.Pending as p:
        return _text_error(503, '변환 중입니다. 잠시 후 다시 받아 주세요.', retry_after=p.retry_after)
    except epaper_service.ConversionFailed as e:
        return _text_error(422, f'이 책은 변환할 수 없습니다. ({str(e.reason)[:120]})')
    epaper_service.mark_downloaded(epub_path, meta)
    filename = clean_name(' - '.join(x for x in (clean_name(book.get('author'), AUTHOR_MAX),
                                                  clean_name(book.get('title'), TITLE_MAX)) if x), 120) or f'book_{book_id}'
    return _send_cached(epub_path, f'book_{book_id}.epub',
                        f"attachment; filename=\"book_{book_id}.epub\"; filename*=UTF-8''{quote(filename + '.epub', safe='')}",
                        meta)


@opds_epaper_bp.route(PREFIX + '/cover/<int:book_id>.jpg', methods=['GET'])
def epaper_cover(book_id):
    user = _download_user(book_id)
    if not user:
        return _unauthorized()
    book = _repo().get_book(DB_TYPE, book_id, user.get('id'), user.get('role'))
    if not book:
        return _text_error(404, 'not found')
    from services import epaper_service
    try:
        path = epaper_service.feed_cover(DB_TYPE, book, _feed_profile(user))
    except Exception as e:
        print(f"[EPAPER] cover failed book={book_id}: {type(e).__name__}: {e}")
        path = None
    if not path:
        return _text_error(404, 'no cover')
    res = send_file(path, mimetype='image/jpeg', conditional=True)
    res.headers['Cache-Control'] = 'private, max-age=86400'
    return res


# ---- 로컬 EPUB 업로드·변환 (기기 전용 계정, EPAPER_UPLOAD_USERS에 적힌 사용자만) ----

UPLOAD_MAX_BYTES = 50 * 1024 * 1024
_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _json(status, **body):
    import json
    res = Response(json.dumps(body, ensure_ascii=False), status=status, mimetype='application/json; charset=utf-8')
    res.headers['Cache-Control'] = 'no-store'
    return res


def _upload_user():
    user = _user()
    if not user:
        return None, _unauthorized()
    from services.settings_service import SettingsService
    allowed = [u.strip() for u in str(SettingsService.get('EPAPER_UPLOAD_USERS', '') or '').split(',') if u.strip()]
    if user.get('username') not in allowed:
        print(f"[EPAPER] upload refused user={user.get('username')} reason=not_upload_user")
        return None, _json(403, error='upload_not_allowed', message='이 계정은 업로드 권한이 없습니다.')
    return user, None


def _upload_state(sha, prof):
    from services import epaper_service
    found = epaper_service.find_upload(sha, prof)
    if found:
        _path, meta = found
        return _json(200, state='done', sha256=sha, profile=meta.get('profile'), digest=meta.get('digest'),
                     size=meta.get('size'), download=_url(f'/uploads/{sha}.epub'))
    state = epaper_service.upload_job_state(sha, prof)
    if state['state'] == 'converting':
        return _json(202, state='converting', sha256=sha, status_url=_url(f'/uploads/{sha}'))
    if state['state'] == 'failed':
        return _json(422, state='failed', sha256=sha, reason=str(state.get('reason') or '')[:200])
    return _json(404, state='unknown', sha256=sha)


@opds_epaper_bp.route(PREFIX + '/uploads/<string:sha>', methods=['GET'])
def epaper_upload_status(sha):
    user_row, error = _upload_user()
    if error:
        return error
    sha = sha.lower()
    if not _SHA256.match(sha):
        return _json(400, error='bad_sha256')
    return _upload_state(sha, _feed_profile(user_row))


@opds_epaper_bp.route(PREFIX + '/uploads', methods=['POST'])
def epaper_upload():
    import hashlib
    import os
    import tempfile
    user_row, error = _upload_user()
    if error:
        return error
    prof = _feed_profile(user_row)  # POST 시점에 정한다 - 변환 스레드에는 요청 맥락이 없다
    claimed = (request.headers.get('X-Content-SHA256') or '').strip().lower()
    if claimed and not _SHA256.match(claimed):
        return _json(400, error='bad_sha256')
    length = request.content_length
    if length is not None and length > UPLOAD_MAX_BYTES:
        print(f"[EPAPER] upload refused user={g.epaper_user} reason=too_large size={length}")
        return _json(413, error='too_large', limit=UPLOAD_MAX_BYTES)
    if claimed:
        from services import epaper_service
        if epaper_service.find_upload(claimed, prof) or epaper_service.upload_job_state(claimed, prof)['state'] == 'converting':
            return _upload_state(claimed, prof)

    from services import epaper_service
    staging = tempfile.mkdtemp(prefix='up-', dir=epaper_service.upload_staging_dir())
    src = os.path.join(staging, 'source.epub')
    digest = hashlib.sha256()
    size = 0
    try:
        with open(src, 'wb') as f:
            while True:
                chunk = request.stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > UPLOAD_MAX_BYTES:
                    raise ValueError('too_large')
                digest.update(chunk)
                f.write(chunk)
    except ValueError:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        print(f"[EPAPER] upload refused user={g.epaper_user} reason=too_large")
        return _json(413, error='too_large', limit=UPLOAD_MAX_BYTES)
    sha = digest.hexdigest()
    reason = None
    if size == 0:
        reason = 'empty'
    elif claimed and claimed != sha:
        reason = 'sha256_mismatch'
    else:
        with open(src, 'rb') as f:
            if f.read(4) != b'PK\x03\x04':
                reason = 'not_epub'
    if reason:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        print(f"[EPAPER] upload refused user={g.epaper_user} reason={reason} size={size}")
        return _json(400, error=reason)
    if epaper_service.find_upload(sha, prof) or epaper_service.upload_job_state(sha, prof)['state'] == 'converting':
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        return _upload_state(sha, prof)
    title = clean_name(request.headers.get('X-Title', ''), TITLE_MAX)
    print(f"[EPAPER] upload accepted user={g.epaper_user} sha256={sha} size={size} profile={prof.id}")
    epaper_service.start_upload_conversion(sha, src, prof, title=title)
    return _json(202, state='converting', sha256=sha, status_url=_url(f'/uploads/{sha}'))


@opds_epaper_bp.route(PREFIX + '/uploads/<string:sha>.epub', methods=['GET'])
def epaper_upload_download(sha):
    user_row, error = _upload_user()
    if error:
        return error
    sha = sha.lower()
    if not _SHA256.match(sha):
        return _json(400, error='bad_sha256')
    from services import epaper_service
    prof = _feed_profile(user_row)
    found = epaper_service.find_upload(sha, prof)
    if not found:
        return _upload_state(sha, prof)
    path, meta = found
    epaper_service.mark_downloaded(path, meta)
    return _send_cached(path, f'{sha[:16]}.epub', f'attachment; filename="{sha[:16]}.epub"', meta)
