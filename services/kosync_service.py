# -*- coding: utf-8 -*-
"""
kosync_service.py – KOReader 진행 동기화(kosync 호환 API)

KOReader의 "진행 상황 동기화" 플러그인은 사용자 지정 서버를 쓸 수 있다. BookOasis가 같은 API를 제공해
KOReader에서 읽은 위치를 저장하고 기기 사이에 주고받는다.

- 인증: KOReader는 비밀번호의 MD5만 보낸다(x-auth-key). BookOasis 로그인 비밀번호는 단방향 해시라 맞춰볼 수
  없으므로, 계정 메뉴에서 따로 정한 '동기화 비밀번호'의 MD5를 다시 해시해 저장한다.
- 문서 식별: KOReader 기본값(바이너리)은 파일의 정해진 위치 12곳에서 1KB씩 읽어 만든 partial MD5다.
  OPDS로 내려받을 때 서버가 같은 값을 계산해 도서와 이어 둔다(내려받으며 어차피 파일 전체를 읽으므로 원격
  드라이브 추가 부담이 없다).
- BookOasis 진행률과 맞추기: 페이지 기반 형식(만화 압축/이미지 폴더, PDF)만. KOReader의 페이지 번호(1부터)가
  BookOasis의 '읽은 페이지 수'와 같다. EPUB/TXT는 위치 형식이 달라(KOReader xpointer vs 웹 뷰어 cfi/청크)
  KOReader 기기끼리만 동기화한다 - 웹 뷰어의 위치를 퍼센트로 덮어쓰지 않기 위함.
"""
import hashlib
import threading
import time
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

PAGED_FORMATS = ('zip', 'cbz', 'imgdir', 'pdf')
WEB_DEVICE_NAME = 'BookOasis'
WEB_DEVICE_ID = 'bookoasis-web'
# BookOasis 진행이 KOReader 기록보다 이만큼(초) 이상 나중일 때만 웹 진행을 돌려준다(방금 KOReader가 올린 것을
# 그대로 미러링한 값을 '더 새로운 웹 진행'으로 착각하지 않도록)
WEB_NEWER_MARGIN_SEC = 5
MIN_SYNC_PASSWORD_LENGTH = 4
MAX_FIELD_LENGTH = 2000


# ---- 문서 식별 (KOReader util.partialMD5와 같은 방식) ----

def partial_md5(file_path):
    """오프셋 0, 1K, 4K, 16K, ... 1G(1024 << 2i, i=-1..10 - i=-1은 LuaJIT에서 0)에서 1KB씩 읽어 MD5.
    파일 끝을 지나면 거기서 멈춘다."""
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for i in range(-1, 11):
            f.seek(0 if i < 0 else 1024 << (2 * i))
            sample = f.read(1024)
            if not sample:
                break
            md5.update(sample)
    return md5.hexdigest()


def remember_document(db_type, book_id, file_path):
    from repositories.kosync_repository import KosyncRepository
    try:
        KosyncRepository.save_document(partial_md5(file_path), db_type, book_id)
    except Exception as e:
        print(f"[Kosync] document digest failed (db={db_type}, book_id={book_id}): {e}")


def remember_document_async(db_type, book_id, file_path):
    """OPDS 다운로드 응답을 늦추지 않도록 백그라운드에서 계산한다."""
    thread = threading.Thread(target=remember_document, args=(db_type, int(book_id), file_path), daemon=True)
    thread.start()
    return thread


# ---- 인증 ----

def _key_from_password(password):
    return hashlib.md5(str(password).encode('utf-8')).hexdigest()


def set_sync_password(user_id, password):
    password = str(password or '')
    if len(password) < MIN_SYNC_PASSWORD_LENGTH:
        raise ValueError(f'동기화 비밀번호는 {MIN_SYNC_PASSWORD_LENGTH}자 이상이어야 합니다.')
    from repositories.kosync_repository import KosyncRepository
    KosyncRepository.set_credential(user_id, generate_password_hash(_key_from_password(password)))


def clear_sync_password(user_id):
    from repositories.kosync_repository import KosyncRepository
    KosyncRepository.delete_credential(user_id)


def has_sync_password(user_id):
    from repositories.kosync_repository import KosyncRepository
    return bool(KosyncRepository.get_credential(user_id))


def authenticate(username, auth_key):
    """x-auth-user / x-auth-key(동기화 비밀번호의 MD5) → 사용자 dict 또는 None."""
    if not username or not auth_key:
        return None
    from repositories.kosync_repository import KosyncRepository
    from repositories.user_repository import UserRepository
    user = UserRepository.find_by_username('general', str(username))
    if not user:
        return None
    user = dict(user)
    key_hash = KosyncRepository.get_credential(user['id'])
    if not key_hash or not check_password_hash(key_hash, str(auth_key).strip().lower()):
        return None
    return user


# ---- 진행 ----

def _book_for_document(document):
    from repositories.kosync_repository import KosyncRepository
    from repositories.reading_progress_repository import ReadingProgressRepository
    mapped = KosyncRepository.get_document(document)
    if not mapped:
        return None
    book = ReadingProgressRepository.get_book_for_progress(mapped['db_type'], mapped['book_id'])
    if not book:
        return None
    return {'db_type': mapped['db_type'], 'book_id': int(mapped['book_id']),
            'format': str(book['file_format'] or '').lower(), 'total_pages': int(book['total_pages'] or 0)}


def _clip(value, limit=MAX_FIELD_LENGTH):
    return None if value is None else str(value)[:limit]


def push_progress(user_id, payload):
    """KOReader PUT /syncs/progress. 돌려주는 값: {'document', 'timestamp'}."""
    from repositories.kosync_repository import KosyncRepository
    document = str(payload.get('document') or '').strip()
    if not document or len(document) > 64:
        raise ValueError('document가 필요합니다.')
    try:
        percentage = float(payload.get('percentage'))
    except (TypeError, ValueError):
        percentage = None
    progress = _clip(payload.get('progress'))
    timestamp = int(time.time())
    KosyncRepository.save_progress(user_id, document, progress, percentage, _clip(payload.get('device'), 255),
                                   _clip(payload.get('device_id'), 255), timestamp)
    _mirror_to_bookoasis(user_id, document, progress, percentage)
    return {'document': document, 'timestamp': timestamp}


def _mirror_to_bookoasis(user_id, document, progress, percentage):
    """페이지 기반 형식이면 BookOasis 읽은 위치에도 반영한다."""
    try:
        book = _book_for_document(document)
        if not book or book['format'] not in PAGED_FORMATS or not str(progress or '').isdigit():
            return
        page = int(progress)
        total = book['total_pages']
        if total <= 0 and percentage:
            total = max(page, int(round(page / percentage)))
        if page <= 0 or total <= 0:
            return
        from services.reading_progress_service import ReadingProgressService
        ReadingProgressService.record_progress(book['db_type'], book['book_id'], page - 1, total, user_id=user_id)
    except Exception as e:
        print(f"[Kosync] mirror to BookOasis failed (document={document}): {e}")


def _to_epoch(value):
    if not value:
        return 0
    if isinstance(value, datetime):
        return int(value.timestamp())
    try:
        return int(datetime.strptime(str(value)[:19], '%Y-%m-%d %H:%M:%S').timestamp())
    except ValueError:
        return 0


def pull_progress(user_id, document):
    """KOReader GET /syncs/progress/<document>. 기록이 없으면 {}."""
    from repositories.kosync_repository import KosyncRepository
    record = KosyncRepository.get_progress(user_id, document)
    result = None
    if record:
        result = {k: record.get(k) for k in ('document', 'progress', 'percentage', 'device', 'device_id', 'timestamp')}
        result['timestamp'] = int(result['timestamp'] or 0)

    # 페이지 기반 형식: 웹 뷰어(또는 OPDS 페이지 스트리밍)에서 더 나중에 읽었으면 그 위치를 준다
    try:
        book = _book_for_document(document)
        if book and book['format'] in PAGED_FORMATS:
            from services.reading_progress_service import ReadingProgressService
            state = ReadingProgressService.get_progress_state(book['db_type'], book['book_id'], user_id=user_id)
            pages_read = int((state or {}).get('pages_read') or 0)
            total = int((state or {}).get('total_pages') or 0) or book['total_pages']
            web_ts = _to_epoch((state or {}).get('last_read_at'))
            record_ts = result['timestamp'] if result else 0
            if pages_read > 0 and web_ts > record_ts + WEB_NEWER_MARGIN_SEC:
                result = {'document': document, 'progress': str(pages_read),
                          'percentage': round(pages_read / total, 4) if total > 0 else None,
                          'device': WEB_DEVICE_NAME, 'device_id': WEB_DEVICE_ID, 'timestamp': web_ts}
    except Exception as e:
        print(f"[Kosync] web progress lookup failed (document={document}): {e}")
    return result or {}
