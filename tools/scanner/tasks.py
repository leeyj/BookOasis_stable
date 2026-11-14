# -*- coding: utf-8 -*-
import os
import sys

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import gc
from tools.scanner.metadata import parse_info_xml, parse_kavita_yaml, parse_series_json, parse_comicinfo_from_cbz, merge_local_metadata, is_consonant_folder
from tools.scanner.cover import get_series_cover_fallback, get_imgdir_cover, extract_cover_from_b64, download_cover_from_url, get_folder_banner
from tools.scanner.offset import collect_zip_offsets_data
from tools.scanner.path_utils import canonical_path, join_canonical

SUPPORTED_FORMATS = ('.zip', '.cbz', '.epub', '.pdf', '.txt')
from utils import media_types as _media_types
SUPPORTED_IMAGE_FORMATS = _media_types.IMAGE_EXTENSIONS
IMGDIR_VIRTUAL_FILENAME = '__folder__.imgdir'


def _compute_offsets(full_path, filename, is_remote, root, gdrive_file_ids):
    """zip/cbz의 페이지 오프셋을 계산한다. 로컬이면 파일을 직접 열어서, 진짜 gdrive://
    가상 경로면 Range 요청으로 파일 끝(central directory)만 받아서 계산한다(전체 다운로드 없음).
    is_remote가 True인 다른 원격(rclone 마운트 등)은 기존처럼 건너뛴다 — 그런 라이브러리는
    이 함수가 손대지 않고 계속 빈 리스트를 반환한다(원래도 로컬 마운트라 직접 열어도
    되지만, 그 개선은 이 변경의 범위 밖이다)."""
    if root.startswith(('gdrive:', 'gdrive://')):
        file_id = gdrive_file_ids.get(filename) if gdrive_file_ids else None
        if not file_id:
            return []
        from utils.drive_helper import fetch_gdrive_zip_offsets
        try:
            offsets_data, _total_size = fetch_gdrive_zip_offsets(file_id)
            if offsets_data:
                print(f"[Scanner-DEBUG-Task] ⚡ [gdrive Range] '{filename}' offsets computed ({len(offsets_data)}p, no full download)")
            return offsets_data
        except Exception as e:
            print(f"[Scanner-DEBUG-Task] ❌ gdrive Range offset computation failed: '{filename}' - {e}")
            return []
    if is_remote:
        return []
    return collect_zip_offsets_data(full_path)


def _full_path_for(root, filename, gdrive_file_ids):
    """root+filename을 합친 경로에, gdrive 등록분이면 실제 Drive file_id를 얹어 반환한다.

    filename 자체는 절대 건드리지 않는다 — 제목/확장자 판별은 이 함수가 만드는
    full_path가 아니라 별도로 전달되는 원본 filename에서만 이뤄지므로, 여기서
    file_id를 붙여도 화면에 보이는 제목 등은 오염되지 않는다.
    """
    base = join_canonical(root, filename)
    if not gdrive_file_ids:
        return base
    file_id = gdrive_file_ids.get(filename)
    if not file_id:
        return base
    from utils.drive_helper import encode_gdrive_file_id
    return encode_gdrive_file_id(base, file_id)


_META_EXTENSIONS = _media_types.METADATA_EXTENSIONS


def _stage_gdrive_metadata_folder(root, files, gdrive_file_ids, gdrive_meta_dirs=None):
    """gdrive 폴더에 kavita.yaml/series.json/info.xml 등 메타데이터 파일이 있으면
    실제 내용을 로컬 스테이징 폴더로 받아와, merge_local_metadata()가 평소처럼
    os.path.join(folder_path, filename) + open()으로 읽을 수 있게 해준다.

    이렇게 해두면 kavita.yaml에 임베드된 Base64 커버(cover_b64_map)를 커버 스캔 때
    바로 쓸 수 있어, 표지 하나 뽑자고 수십~수백MB 압축 파일 전체를 받을 필요가 없다.

    gdrive_meta_dirs(dict)가 있으면 리모트 카테고리다: 엔진이 스캔 시작 때 rclone sync 한 번으로
    받아둔 메타 미러 폴더를 그대로 쓰고, 여기서 파일별로 내려받지 않는다 — 폴더마다 API 키로
    받으면 대형 공유 폴더에서 수백 건 만에 Google 403으로 차단된다(2026-10-22 .21 실측).
    아래 파일별 다운로드는 리모트가 없는 옛 카테고리용이다.

    실패해도 예외를 전파하지 않고 원본 root를 그대로 반환한다(항상 안전한 폴백).
    """
    if gdrive_meta_dirs is not None:
        mirror_dir = gdrive_meta_dirs.get(root)
        if mirror_dir and os.path.isdir(mirror_dir):
            return mirror_dir, True
        return root, False

    if not gdrive_file_ids:
        return root, False

    meta_filenames = [
        f for f in files
        if f.lower().endswith(_META_EXTENSIONS) and gdrive_file_ids.get(f)
    ]
    if not meta_filenames:
        return root, False

    try:
        import hashlib
        from utils.drive_helper import download_gdrive_file
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        staging_dir = os.path.join(base_dir, 'cache', 'gdrive_meta', hashlib.md5(root.encode('utf-8')).hexdigest())
        os.makedirs(staging_dir, exist_ok=True)

        any_ready = False
        for fname in meta_filenames:
            dest = os.path.join(staging_dir, fname)
            done_marker = dest + '.done'
            if os.path.exists(dest) and os.path.exists(done_marker):
                any_ready = True
                continue
            file_id = gdrive_file_ids.get(fname)
            if download_gdrive_file(file_id, dest):
                with open(done_marker, 'w') as f:
                    f.write('done')
                any_ready = True
            else:
                print(f"[Scanner-DEBUG-Task] ⚠️ Failed to download gdrive metadata file, skipping: '{fname}'")

        if any_ready:
            return staging_dir, True
    except Exception as e:
        print(f"[Scanner-DEBUG-Task] ⚠️ gdrive metadata staging failed, falling back to the original path: {e}")

    return root, False


def _normalize_series_text(name):
    """Normalize folder-derived series text."""
    if not name:
        return ''
    import re
    return re.sub(r'^\[(?:단행|연재|소설|만화|웹툰|일반)\]\s*', '', str(name)).strip()


def process_folder_task(root, files, force, db_meta_full, db_offsets_cached, db_folder_mtimes, is_remote=False, library_id=None, db_files_cache=None, library_root=None, gdrive_file_ids=None, db_type=None, db_book_ids=None, gdrive_meta_dirs=None, gdrive_file_stats=None, db_folder_covers=None):
    """Independent I/O scan task per folder (DB independent, pure FS/I/O scaling)

    db_folder_covers(dict)가 있으면 웹툰 속성 카테고리다: 모든 폴더를 작품으로 보고, 회차는 폴더 대표 표지
    (이미 DB에 있는 같은 폴더 회차의 표지 → yaml/series.json → 첫 회차 첫 장)를 같이 쓴다."""
    root = canonical_path(root)
    print(f"[Scanner-DEBUG-Task] 📂 entering process_folder_task - folder: '{root}'")
    # 리모트가 있는 gdrive 카테고리(gdrive_meta_dirs 전달됨)는 책을 로컬 사본으로 열므로 Range 오프셋이 필요 없다.
    skip_gdrive_offsets = gdrive_meta_dirs is not None
    # gdrive:// 가상 경로는 os.stat이 안 되므로, 엔진이 rclone 목록에서 넘긴 파일별 (수정 시각, 크기)를 쓴다.
    # 이게 있어야 로컬 폴더와 같은 규칙(파일/메타 수정 시각 비교)으로 바뀌지 않은 폴더를 건너뛴다.
    folder_stats = gdrive_file_stats.get(root, {}) if gdrive_file_stats else {}

    def _file_stat(full_path, filename):
        if filename in folder_stats:
            return folder_stats[filename]
        return os.path.getmtime(full_path), os.path.getsize(full_path)
    
    media_files = [f for f in files if f.lower().endswith(SUPPORTED_FORMATS)]
    image_files = [f for f in files if f.lower().endswith(SUPPORTED_IMAGE_FORMATS)]
    has_imgdir_candidate = bool(image_files) and not media_files
    if not media_files and not has_imgdir_candidate:
        print(f"[Scanner-DEBUG-Task] 📁 Unsupported folder (skip) - folder: '{root}'")
        return None

    # 1. Pre-check if metadata file exists
    has_yaml = any(f.lower() == 'kavita.yaml' for f in files)
    has_xml = any(f.lower() == 'info.xml' for f in files)
    # 폴더 메타 신호: 메타 파일 + (책이 있는 폴더의) 표지 그림. 나중에 생기거나 바뀌면 그 폴더 도서를 다시 처리한다.
    meta_signal_files = [f for f in files if f.lower() in ('kavita.yaml', 'info.xml', 'series.json')]
    if media_files:
        meta_signal_files += image_files
    has_meta_files = bool(meta_signal_files)

    dir_mtime = None
    meta_mtime = None

    if root.startswith(('gdrive:', 'gdrive://')):
        is_remote = True
        # 폴더 자체의 수정 시각은 목록에 없으므로 폴더 안 파일 중 가장 최근 수정 시각을 폴더 신호로 쓴다
        # (새 회차는 어차피 DB에 없는 파일이라 파일 단위로 잡힌다). 목록 정보가 없으면 예전처럼 0.
        dir_mtime = max((m for m, _ in folder_stats.values()), default=0.0)
        meta_mtime = max((folder_stats[f][0] for f in meta_signal_files if f in folder_stats), default=0.0)
    else:
        # rclone 마운트도 stat은 VFS 디렉터리 캐시가 답한다(내려받기 없음) → 로컬과 같이 실제 값을 쓴다.
        try:
            dir_mtime = os.path.getmtime(root)
            meta_mtime = max((os.path.getmtime(join_canonical(root, f)) for f in meta_signal_files), default=0.0)
        except Exception as e:
            print(f"[Scanner-DEBUG-Task] ⚠️ Failed to get mtime for folder '{root}': {e}")
            dir_mtime = None

    # 이 폴더의 메타 신호 기준값(folder_mtimes)이 있으면, 책 파일과 메타 신호가 그대로인 도서는 메타가 다
    # 채워졌는지와 상관없이 건너뛴다. 예전엔 출판사·줄거리·표지 중 하나라도 비면 매번 다시 처리해서,
    # 새 회차 하나에도 폴더 회차 전체를 다시 처리·저장했다(커뮤니티 제보, 회차 수에 비례해 수십 초).
    # 원격은 예전에 dir/meta mtime을 0.0으로 기록했으므로 그 행은 기준값이 없는 것으로 보고, 이번만
    # 예전 규칙(메타가 다 채워진 도서만 건너뜀)으로 처리하고 실제 값을 기록한다. gdrive://는 계속 예전 규칙.
    cached_mtimes = db_folder_mtimes.get(root) if db_folder_mtimes else None
    baseline_known = (
        bool(cached_mtimes) and dir_mtime is not None
        and (not is_remote or float(cached_mtimes[0] or 0) > 0)
    )

    # 폴더 메타 신호가 마지막 기록 이후 새로 생기거나 바뀌었으면 파일 단위 스킵을 풀어 새 메타를 DB에 반영한다
    # (예: 이미 스캔된 작품 폴더에 나중에 kavita.yaml을 추가한 경우).
    meta_changed = False
    if baseline_known:
        meta_changed = int(cached_mtimes[1] or 0) != int(meta_mtime or 0)
    elif has_meta_files and not is_remote and dir_mtime is not None and meta_mtime:
        meta_changed = True
    if meta_changed:
        print(f"[Scanner-DEBUG-Task] 📝 Folder metadata file new/changed - per-file skip disabled - folder: '{root}'")

    # 2. Early skip if files are unchanged (mtime & size match DB cache)
    skipped_files = set()
    imgdir_skip = False
    # gdrive 이미지 폴더는 가상 경로에 폴더 ID(?gid=)가 붙는다 — 볼 때 폴더째 받는 데 쓴다.
    imgdir_virtual_path = _full_path_for(root, IMGDIR_VIRTUAL_FILENAME, gdrive_file_ids)

    def _imgdir_stat():
        """이미지 폴더 책의 (수정 시각, 이미지 합계 크기). gdrive는 rclone 목록 값을 쓴다."""
        if folder_stats:
            return dir_mtime, sum(folder_stats[f][1] for f in image_files if f in folder_stats)
        return os.path.getmtime(root), sum(
            os.path.getsize(join_canonical(root, f))
            for f in image_files
            if os.path.exists(join_canonical(root, f))
        )
    if not force and not meta_changed and db_files_cache:
        for filename in media_files:
            full_path = _full_path_for(root, filename, gdrive_file_ids)
            if full_path in db_files_cache:
                try:
                    p_mtime, p_size = _file_stat(full_path, filename)
                    c_mtime, c_size = db_files_cache[full_path]
                    
                    if int(c_mtime) == int(p_mtime) and c_size == p_size:
                        file_ext = os.path.splitext(filename)[1].lower()
                        if file_ext in ('.zip', '.cbz') and not is_remote and full_path not in db_offsets_cached:
                            continue
                        # TXT는 오프셋/표지 강제 재시도가 필요 없으므로 mtime/size 동일 시 바로 스킵
                        if file_ext == '.txt':
                            skipped_files.add(filename)
                            continue
                        if not baseline_known and full_path not in db_meta_full:
                            continue
                        skipped_files.add(filename)
                except Exception:
                    # 원격 드라이브이고 이미 DB 캐시(mtime, 메타데이터, 커버)가 있는 경우 예외가 나더라도 스킵 처리
                    if is_remote and (baseline_known or full_path in db_meta_full):
                        c_mtime, c_size = db_files_cache[full_path]
                        if c_mtime > 0.0:
                            skipped_files.add(filename)

        if has_imgdir_candidate and imgdir_virtual_path in db_files_cache:
            try:
                p_mtime, p_size = _imgdir_stat()
                c_mtime, c_size = db_files_cache[imgdir_virtual_path]
                if int(c_mtime) == int(p_mtime) and int(c_size) == int(p_size):
                    imgdir_skip = True
            except Exception:
                imgdir_skip = False

        all_files_skipped = (
            len(skipped_files) == len(media_files)
            and (not has_imgdir_candidate or imgdir_skip)
        )
        if all_files_skipped:
            if not has_meta_files:
                print(f"[Scanner-DEBUG-Task] ⚡ [Ultra-fast skip] All files unchanged (mtime/size match) - folder: '{root}'")
                return None
            else:
                if dir_mtime is not None:
                    cached_mtimes = db_folder_mtimes.get(root)
                    if cached_mtimes:
                        c_dir_mtime, c_meta_mtime = cached_mtimes
                        if int(c_dir_mtime) == int(dir_mtime) and int(c_meta_mtime) == int(meta_mtime):
                            print(f"[Scanner-DEBUG-Task] ⚡ [Ultra-fast skip] All files unchanged and meta mtime unchanged - folder: '{root}'")
                            return None
                        else:
                            print(f"[Scanner-DEBUG-Task] ⚠️ [Ultra-fast skip failed] mtime changed (dir: {int(c_dir_mtime)}->{int(dir_mtime)}, meta: {int(c_meta_mtime)}->{int(meta_mtime)}) - folder: '{root}'")

    # 일반 파일(archive/txt/pdf/epub)은 "현재 폴더명"을 시리즈로 사용한다.
    # 즉, 라이브러리 루트와 현재 폴더 사이의 중간 경로는 모두 무시한다.
    series_name = _normalize_series_text(os.path.basename(root.rstrip('/')))

    print(f"[Scanner-DEBUG-Task]   - Metadata YAML/XML/JSON load started")
    meta_folder_path, meta_staged_locally = (root, False)
    if is_remote and root.startswith(('gdrive:', 'gdrive://')):
        meta_folder_path, meta_staged_locally = _stage_gdrive_metadata_folder(root, files, gdrive_file_ids, gdrive_meta_dirs)
    merged_meta = merge_local_metadata(meta_folder_path, files=files, is_remote=is_remote and not meta_staged_locally)
    print(f"[Scanner-DEBUG-Task]   - Metadata load completed")

    parser_warnings = merged_meta.pop('parser_warnings', [])

    meta_has_data = bool(
        merged_meta['author'] or merged_meta['publisher'] or
        merged_meta['summary'] or merged_meta['release_date'] or
        merged_meta['cover_b64_map'] or
        merged_meta.get('books_lv') or merged_meta.get('publication_status')
    )

    is_webtoon_library = db_folder_covers is not None
    is_series_folder = bool(merged_meta.get('has_yaml') and merged_meta.get('is_webtoon')) or is_webtoon_library
    is_json_only_webtoon = bool(not merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
    series_cover_url = merged_meta.get('cover_image_url', '') if is_json_only_webtoon else ''
    # 강제 재스캔은 표지를 새로 뽑으므로 예전 대표 표지를 이어 쓰지 않는다.
    shared_cover_image = db_folder_covers.get(root) if is_webtoon_library and not force else None

    # 배너는 표지와 달리 권마다 다를 필요 없는 시리즈/폴더 단위 히어로 이미지라, 폴더당
    # 한 번만 확보해 그 폴더의 모든 도서 결과에 동일하게 반영한다 (공유 드라이브 도서관리
    # 담당자와 합의된 범위: 메타 YAML의 banner 필드 우선, 없으면 폴더 내 loose banner.<ext>,
    # 둘 다 없으면 표지처럼 zip/epub 내부를 강제로 뒤지지 않고 그냥 비워둔다).
    shared_banner_image = None
    if not is_remote and media_files:
        try:
            banner_seed_path = _full_path_for(root, media_files[0], gdrive_file_ids)
            shared_banner_image = get_folder_banner(banner_seed_path, root, banner_b64=merged_meta.get('banner_b64'), force=force, library_id=library_id)
        except Exception as e:
            print(f"[Scanner-DEBUG-Task] ⚠️ Banner extraction failed ('{root}'): {e}")

    import zipfile
    results = []
    errors = list(parser_warnings)
    for filename in media_files:
        full_path = _full_path_for(root, filename, gdrive_file_ids)
        _, ext = os.path.splitext(filename)
        file_format = ext.replace('.', '').lower()

        skip = False
        if not force and not meta_changed and not meta_has_data and full_path in db_meta_full and (full_path in db_offsets_cached or skip_gdrive_offsets):
            skip = True
        elif filename in skipped_files:
            skip = True

        cover_image = None
        offsets_data = []
        offset_only = False  # Cover/meta complete, offset-only fast path flag

        if skip:
            pass  # Fully cached book — skip all processing

        elif (
            not force and
            not meta_changed and
            not meta_has_data and
            full_path in db_meta_full and
            full_path not in db_offsets_cached and
            file_format in ('zip', 'cbz') and
            (not is_remote or (root.startswith(('gdrive:', 'gdrive://')) and not skip_gdrive_offsets))
        ):
            # ── [Offset-only Fast Path] ──
            # If existing book has cover/meta but no offset:
            # Completely skip ComicInfo parsing and cover extraction pipeline
            # Only read ZIP central directory (collect offsets) - Minimize I/O
            # (gdrive:// 가상 경로면 전체 다운로드 없이 Range 요청만으로 처리 — _compute_offsets 참조)
            offset_only = True
            try:
                offsets_data = _compute_offsets(full_path, filename, is_remote, root, gdrive_file_ids)
                if offsets_data:
                    print(f"[Scanner-DEBUG-Task] ⚡ [Offset-only] '{filename}' ({len(offsets_data)}p)")
                else:
                    print(f"[Scanner-DEBUG-Task] ⚡ [Offset-only] Skip ZIP without images: '{filename}'")
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ Offset-only collection failed: '{filename}' - {e}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'OffsetError',
                    'message': f"Offset-only collection failed: {str(e)}"
                })

        else:
            # ── [General Path] Cover extraction + Offset collection ──
            print(f"[Scanner-DEBUG-Task]   - File processing started: '{filename}'")
            try:
                # [ComicInfo.xml parsing] If local file and CBZ format, extract metadata internally
                # Skip remote paths due to high I/O cost -> delegated to Lazy Scanner
                if not is_remote and file_format in ('cbz', 'zip') and (
                    not merged_meta['author'] or not merged_meta['summary'] or not merged_meta.get('genre') or not merged_meta.get('tags')
                    or not merged_meta.get('cover_artist') or not merged_meta.get('teams')
                    or not merged_meta.get('locations') or not merged_meta.get('characters')
                    or not merged_meta.get('books_lv')
                ):
                    try:
                        comicinfo = parse_comicinfo_from_cbz(full_path)
                        if comicinfo['author'] and not merged_meta['author']:
                            merged_meta['author'] = comicinfo['author']
                            print(f"[Scanner-DEBUG-Task]     - ComicInfo.xml author fallback: {comicinfo['author']}")
                        if comicinfo.get('cover_artist') and not merged_meta.get('cover_artist'):
                            merged_meta['cover_artist'] = comicinfo['cover_artist']
                        if comicinfo.get('teams') and not merged_meta.get('teams'):
                            merged_meta['teams'] = comicinfo['teams']
                        if comicinfo.get('locations') and not merged_meta.get('locations'):
                            merged_meta['locations'] = comicinfo['locations']
                        if comicinfo.get('characters') and not merged_meta.get('characters'):
                            merged_meta['characters'] = comicinfo['characters']
                        if comicinfo.get('books_lv') and not merged_meta.get('books_lv'):
                            merged_meta['books_lv'] = comicinfo['books_lv']
                        if comicinfo['publisher'] and not merged_meta['publisher']:
                            merged_meta['publisher'] = comicinfo['publisher']
                        if comicinfo['summary'] and not merged_meta['summary']:
                            merged_meta['summary'] = comicinfo['summary']
                        if comicinfo['release_date'] and not merged_meta['release_date']:
                            merged_meta['release_date'] = comicinfo['release_date']
                        if comicinfo.get('genre') and not merged_meta.get('genre'):
                            merged_meta['genre'] = comicinfo['genre']
                        if comicinfo.get('tags') and not merged_meta.get('tags'):
                            merged_meta['tags'] = comicinfo['tags']
                    except Exception as ce:
                        print(f"[Scanner-DEBUG-Task]     - ComicInfo.xml parsing skipped: {ce}")

                # Convert keys to lowercase to prevent case issues in Linux
                filename_lower = filename.lower()
                b64_keys_lower = {k.lower(): v for k, v in merged_meta['cover_b64_map'].items()}
                
                if filename_lower in b64_keys_lower:
                    print(f"[Scanner-DEBUG-Task]     - YAML b64 cover decoding started")
                    cover_image = extract_cover_from_b64(full_path, b64_keys_lower[filename_lower], force=force, library_id=library_id)
                
                if not cover_image:
                    if (is_series_folder or is_json_only_webtoon) and shared_cover_image:
                        print(f"[Scanner-DEBUG-Task]     - Series cover (thumbnail) cloned")
                        cover_image = shared_cover_image
                    elif is_series_folder and (b64_keys_lower or merged_meta.get('cover_image_url')):
                        # 새 회차만 처리하는 증분 스캔은 기존 회차를 건너뛰어 복제할 커버가 없다 — 전체 스캔과
                        # 같은 결과가 되게 yaml 대표 커버(없으면 series.json 이미지)를 쓴다. gdrive 원본은
                        # 압축을 열 수 없어 이게 없으면 새 회차가 커버 없이 등록된다.
                        print(f"[Scanner-DEBUG-Task]     - Series representative cover (new episode)")
                        if b64_keys_lower:
                            cover_image = extract_cover_from_b64(full_path, next(iter(b64_keys_lower.values())), force=force, library_id=library_id)
                        if not cover_image and merged_meta.get('cover_image_url'):
                            cover_image = download_cover_from_url(full_path, merged_meta['cover_image_url'], force=force, library_id=library_id)
                        if not cover_image:
                            cover_image = get_series_cover_fallback(series_name, root, force=force, is_remote=is_remote, filename=filename, file_path=full_path, library_id=library_id)
                    elif is_json_only_webtoon and series_cover_url:
                        print(f"[Scanner-DEBUG-Task]     - series.json URL cover download started")
                        cover_image = download_cover_from_url(full_path, series_cover_url, force=force, library_id=library_id)
                    else:
                        print(f"[Scanner-DEBUG-Task]     - Fallback cover extraction started")
                        cover_image = get_series_cover_fallback(series_name, root, force=force, is_remote=is_remote, filename=filename, file_path=full_path, library_id=library_id)
                
                # Save first successful cover as shared thumbnail for series folder regardless of source
                if (is_series_folder or is_json_only_webtoon) and cover_image and not shared_cover_image:
                    shared_cover_image = cover_image

                # Real-time check if extracted cover is 0 bytes
                if cover_image:
                    from services.cover_storage_service import get_covers_dir
                    cover_filepath = os.path.join(get_covers_dir(), cover_image)
                    if os.path.exists(cover_filepath) and os.path.getsize(cover_filepath) == 0:
                        print(f"[Scanner-DEBUG-Task] ⚠️ Extracted cover file is 0 bytes: {cover_filepath}")
                        try:
                            os.remove(cover_filepath)
                        except Exception:
                            pass
                        cover_image = None  # Invalidate to include in error report collection
                
                # EPUB 사전 캐싱 (Pre-caching) 트리거
                # get_epub_meta()는 book_id가 있어야만(캐시 키를 만들 수 있어야만) 실제로
                # Redis에 결과를 써서 캐싱한다. 이 시점은 아직 신규 도서를 DB에 insert하기
                # 전(폴더 단위 순수 I/O 스캔 - 실제 insert/update 분기 및 커밋은 나중에
                # engine.py의 as_completed 루프+process_batch에서 일괄 처리됨)라, 신규 도서는
                # book_id가 없어 캐싱이 스킵된다. 다만 재스캔되는 "기존" 도서는 스캔 시작
                # 시점에 이미 조회해둔 db_book_ids(파일 경로 -> book id)로 알 수 있으므로,
                # 이 경우엔 실제로 캐시를 채워 이후 뷰어가 처음 열 때부터 바로 히트하게 한다.
                if file_format == 'epub' and not is_remote:
                    try:
                        from services.text_epub_content_service import TextEpubContentService
                        existing_book_id = db_book_ids.get(full_path) if db_book_ids else None
                        TextEpubContentService.get_epub_meta(full_path, existing_book_id, db_type)
                    except Exception as pre_err:
                        print(f"[Scanner-EPUB-Precache] Notice: {pre_err}")

                # Log to error list if Zip/EPUB format but no cover acquired
                if not cover_image and file_format in ('zip', 'cbz', 'epub'):
                    if is_remote:
                        print(f"[Scanner-DEBUG-Task] ⚠️ No cover for remote archive (deferred to lazy scanner): '{filename}'")
                    else:
                        errors.append({
                            'file_path': full_path,
                            'filename': filename,
                            'error_type': 'NoCover',
                            'message': 'ERR_NO_COVER'
                        })
            except zipfile.BadZipFile as bzf:
                print(f"[Scanner-DEBUG-Task] ❌ BadZipFile detected: '{filename}' - {bzf}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'BadZipFile',
                    'message': str(bzf)
                })
            except ValueError as ve:
                print(f"[Scanner-DEBUG-Task] ❌ ValueError detected: '{filename}' - {ve}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'NoCover',
                    'message': str(ve)
                })
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ General exception detected: '{filename}' - {e}")
                errors.append({
                    'file_path': full_path,
                    'filename': filename,
                    'error_type': 'Exception',
                    'message': str(e)
                })

            try:
                if file_format in ('zip', 'cbz') and (force or full_path not in db_offsets_cached) and not skip_gdrive_offsets:
                    print(f"[Scanner-DEBUG-Task]     - Offset analysis started: '{filename}'")
                    offsets_data = _compute_offsets(full_path, filename, is_remote, root, gdrive_file_ids)
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ Offset analysis failed: '{filename}' - {e}")
                if not any(err['file_path'] == full_path for err in errors):
                    errors.append({
                        'file_path': full_path,
                        'filename': filename,
                        'error_type': 'OffsetAnalysis',
                        'message': f"ERR_OFFSET_FAIL: {str(e)}"
                    })
            print(f"[Scanner-DEBUG-Task]   - File processing completed: '{filename}'")

        f_mtime = 0.0
        f_size = 0
        try:
            f_mtime, f_size = _file_stat(full_path, filename)
        except Exception:
            pass

        results.append({
            'full_path': full_path,
            'filename': filename,
            'file_format': file_format,
            'series_name': series_name,
            'title': None,
            'cover_image': cover_image,
            'banner_image': shared_banner_image,
            'offsets_data': offsets_data,
            'skip': skip,
            'offset_only': offset_only,  # Whether it's offset-only fast path
            'file_mtime': f_mtime,
            'file_size': f_size,
        })

    if has_imgdir_candidate:
        # 이미지 폴더(imgdir)는 "현재 폴더=책", "부모 폴더=시리즈" 규칙을 사용한다.
        parent_folder = os.path.basename(os.path.dirname(root.rstrip('/')))
        if root.startswith(('gdrive:', 'gdrive://')):
            # gdrive 링크 바로 아래 폴더면 부모가 Drive 폴더 ID(가상 경로 첫 마디)라 시리즈 이름이 될 수 없다.
            segments = [p for p in root.split(':', 1)[-1].split('/') if p]
            if len(segments) <= 2:
                parent_folder = ''
        imgdir_series_name = _normalize_series_text(parent_folder) if parent_folder else series_name
        imgdir_title = os.path.basename(root)
        imgdir_cover = None
        imgdir_banner = shared_banner_image
        # gdrive 이미지 폴더는 스캔 때 이미지를 받지 않는다 — 표지는 처음 열 때 첫 이미지로 만든다.
        if not imgdir_skip and not root.startswith(('gdrive:', 'gdrive://')):
            try:
                imgdir_cover = get_imgdir_cover(root, imgdir_virtual_path, force=force, library_id=library_id)
            except Exception as e:
                print(f"[Scanner-DEBUG-Task] ❌ IMGDIR cover extraction failed: '{root}' - {e}")
                errors.append({
                    'file_path': imgdir_virtual_path,
                    'filename': IMGDIR_VIRTUAL_FILENAME,
                    'error_type': 'NoCover',
                    'message': f"IMGDIR cover extraction failed: {str(e)}"
                })
            if imgdir_banner is None and not is_remote:
                try:
                    imgdir_banner = get_folder_banner(imgdir_virtual_path, root, banner_b64=merged_meta.get('banner_b64'), force=force, library_id=library_id)
                except Exception as e:
                    print(f"[Scanner-DEBUG-Task] ⚠️ IMGDIR banner extraction failed ('{root}'): {e}")

        f_mtime = 0.0
        f_size = 0
        try:
            f_mtime, f_size = _imgdir_stat()
        except Exception:
            pass

        results.append({
            'full_path': imgdir_virtual_path,
            'filename': IMGDIR_VIRTUAL_FILENAME,
            'file_format': 'imgdir',
            'series_name': imgdir_series_name,
            'title': imgdir_title,
            'cover_image': imgdir_cover,
            'banner_image': imgdir_banner,
            'offsets_data': [],
            'skip': imgdir_skip,
            'offset_only': False,
            'file_mtime': f_mtime,
            'file_size': f_size,
        })

    # Clear references to large base64 maps used to free memory
    merged_meta.pop('cover_b64_map', None)

    gc.collect()
    print(f"[Scanner-DEBUG-Task] 📁 process_folder_task completed - folder: '{root}'")
    return {
        'root': root,
        'merged_meta': merged_meta,
        'results': results,
        'errors': errors,
        'dir_mtime': dir_mtime,
        'meta_mtime': meta_mtime
    }

def process_folder_covers(parent_dir, folder_rows, is_remote, library_id):
    """Extract covers by folder. Share to rest if first book succeeds."""
    merged_meta = merge_local_metadata(parent_dir, is_remote=is_remote)
    
    is_series = bool(merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
    is_json_only = bool(not merged_meta.get('has_yaml') and merged_meta.get('is_webtoon'))
    series_cover_url = merged_meta.get('cover_image_url', '') if is_json_only else ''
    b64_keys_lower = {k.lower(): v for k, v in merged_meta.get('cover_b64_map', {}).items()}
    
    shared_cover = None
    results = []
    
    for row in folder_rows:
        book_id = row['id']
        file_path = row['file_path']
        filename = os.path.basename(file_path)
        series_name = row['series_name']
        file_format = (row['file_format'] or '').lower() if 'file_format' in row.keys() else ''
        is_imgdir = (file_format == 'imgdir') or file_path.lower().endswith('.imgdir')
        imgdir_folder_path = os.path.dirname(file_path) if is_imgdir else None
        
        file_exists = os.path.exists(file_path)
        
        cover_image = None
        filename_lower = filename.lower()
        
        # 1) kavita.yaml Base64 cover - no actual file access needed, remote files supported
        if filename_lower in b64_keys_lower:
            cover_image = extract_cover_from_b64(file_path, b64_keys_lower[filename_lower], force=True, library_id=library_id)
        
        # 2) Reuse already shared cover (if series folder) - no file access needed
        if not cover_image and (is_series or is_json_only) and shared_cover:
            print(f"[Scanner-Covers] Series cover cloned: '{filename}'")
            cover_image = shared_cover
        
        # 3) series.json URL download - no actual file access needed, remote files supported
        if not cover_image and is_json_only and series_cover_url:
            cover_image = download_cover_from_url(file_path, series_cover_url, force=True, library_id=library_id)
        
        # 4) Fallback: first image in archive - requires file access, skip if none -> delegate to Lazy Scanner
        if not cover_image:
            if is_imgdir and imgdir_folder_path and os.path.isdir(imgdir_folder_path):
                cover_image = get_imgdir_cover(imgdir_folder_path, file_path, force=True, library_id=library_id)
            elif not file_exists:
                print(f"[Scanner-Covers] Remote file unreachable -> Delegated to Lazy scanner: '{filename}'")
            else:
                cover_image = get_series_cover_fallback(
                    series_name, parent_dir, force=True, is_remote=is_remote,
                    filename=filename, file_path=file_path, library_id=library_id
                )

        
        # Cache upon first successful shared cover
        if (is_series or is_json_only) and cover_image and not shared_cover:
            shared_cover = cover_image
        
        if cover_image:
            results.append((book_id, cover_image))
    
    return results

