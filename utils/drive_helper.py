import os
import platform
import sys

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_REMOTE_FS_TYPES = ('fuse.rclone', 'rclone', 'cifs', 'nfs', 'nfs4', 'davfs', 'smbfs', 'fuse', 'sshfs')
_RCLONE_VFS_FS_TYPES = ('fuse.rclone', 'rclone')


def _decode_mount_token(token):
    """Decode escaped mount path tokens from /proc/mounts (e.g. \040 -> space)."""
    if not token or '\\' not in token:
        return token

    out = []
    i = 0
    length = len(token)
    while i < length:
        ch = token[i]
        if ch == '\\' and i + 3 < length:
            octal = token[i + 1:i + 4]
            if all(c in '01234567' for c in octal):
                out.append(chr(int(octal, 8)))
                i += 4
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _iter_mounts():
    """Yield tuples of (mount_point, fstype) from /proc/mounts."""
    if not os.path.exists('/proc/mounts'):
        return

    try:
        with open('/proc/mounts', 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mount_point = _decode_mount_token(parts[1])
                fstype = parts[2].lower()
                yield mount_point, fstype
    except Exception as e:
        print(f"[drive_helper] mounts 파싱 실패: {e}")


def _is_same_or_subpath(path, root):
    """Return True if path is equal to root or inside root directory."""
    try:
        path_norm = os.path.normcase(os.path.realpath(os.path.abspath(path)))
        root_norm = os.path.normcase(os.path.realpath(os.path.abspath(root)))
        return os.path.commonpath([path_norm, root_norm]) == root_norm
    except Exception:
        # Fallback for invalid path edge-cases.
        path_norm = os.path.normcase(os.path.abspath(path))
        root_norm = os.path.normcase(os.path.abspath(root))
        return path_norm == root_norm or path_norm.startswith(root_norm + os.sep)


def _find_best_mount_point(path, fs_type_markers):
    """Find the longest matching mount point that contains path for the given fs type markers."""
    best = ''
    for mount_point, fstype in _iter_mounts() or []:
        if mount_point == '/':
            continue
        if not any(t in fstype for t in fs_type_markers):
            continue
        if _is_same_or_subpath(path, mount_point) and len(mount_point) > len(best):
            best = mount_point
    return best


def _find_best_remote_mount_point(path):
    """Find the longest matching generic remote/network mount point that contains path."""
    return _find_best_mount_point(path, _REMOTE_FS_TYPES)


def _find_best_rclone_mount_point(path):
    """Find the longest matching rclone VFS mount point that contains path."""
    return _find_best_mount_point(path, _RCLONE_VFS_FS_TYPES)

import re
import json
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

SUPPORTED_EXTENSIONS = ('.zip', '.cbz', '.rar', '.cbr', '.epub', '.pdf', '.txt', '.yaml', '.xml', '.json')

# 서브폴더 하나당 API/HTTP 요청 1번인 waterfall 구조라, 깊고 넓은 트리는 순차 재귀 시 매우
# 느려진다. 같은 depth의 형제 서브폴더들은 서로 의존관계가 없으므로 스레드풀로 동시 처리한다.
GDRIVE_SCAN_WORKERS = max(1, int(os.getenv('GDRIVE_SCAN_WORKERS', '4') or '4'))

def extract_gdrive_folder_id(path_or_url):
    """
    구글 드라이브 공유 URL 또는 문자열에서 폴더 ID를 추출합니다.
    """
    if not path_or_url:
        return None
    raw = str(path_or_url).strip()
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', raw)
    if match:
        return match.group(1)
    if re.match(r'^[a-zA-Z0-9_-]{20,}$', raw):
        return raw
    return None


# 공개 웹 폴더 뷰가 SSR로 내려주는 항목 수의 관측된 상한. 실제 폴더 항목 수가 이 값 근처거나
# 넘으면, 나머지는 브라우저가 스크롤 시 비공식 batchexecute API로 추가 로드하는 부분이라
# 이 스크래핑 폴백에는 아예 안 잡힐 가능성이 높다 (완전한 페이지네이션은 리버스엔지니어링이
# 필요해 안정성 문제로 보류 — 대신 잘림을 감지해 경고만 남긴다).
HTML_SCRAPE_SUSPECTED_PAGE_SIZE = 50


def _fetch_subfolders_parallel(sub_specs, depth, max_depth, visited_folders, truncation_warnings):
    """같은 depth의 형제 서브폴더들을 스레드풀로 동시에 재귀 탐색한다.

    visited_folders(set)/truncation_warnings(list)에 대한 동시 append/add는 각각의 개별
    연산이 원자적이라 손상 위험은 없고, 최악의 경우도 극히 드문 폴더 ID 경합으로 인한
    약간의 중복 요청 정도라 별도 락 없이도 충분하다.
    """
    if not sub_specs:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=min(GDRIVE_SCAN_WORKERS, len(sub_specs))) as executor:
        futures = {
            executor.submit(
                fetch_gdrive_folder_files, sub_id, sub_rel, depth + 1, max_depth,
                visited_folders, truncation_warnings
            ): sub_rel
            for sub_id, sub_rel in sub_specs
        }
        for future in as_completed(futures):
            sub_rel = futures[future]
            try:
                results.extend(future.result())
            except Exception as e:
                print(f"[gdrive_helper ⚠️] 서브폴더 병렬 탐색 실패 ('{sub_rel}'): {e}")
    return results


def fetch_gdrive_folder_files(folder_id_or_url, parent_subpath="", depth=0, max_depth=4, visited_folders=None, truncation_warnings=None):
    """
    Google Drive REST API (또는 웹 파싱 폴백)를 호출하여 하위 폴더(Subfolders)까지 재귀 수집합니다.
    """
    if depth > max_depth:
        print(f"[gdrive_helper] ⚠️ 최대 depth({max_depth})를 초과했습니다.")
        return []

    folder_id = extract_gdrive_folder_id(folder_id_or_url)
    if not folder_id:
        print(f"[gdrive_helper] ⚠️ 유효한 폴더 ID를 추출하지 못했습니다: {folder_id_or_url}")
        return []

    if visited_folders is None:
        visited_folders = set()

    if truncation_warnings is None:
        truncation_warnings = []

    if folder_id in visited_folders:
        return []
    visited_folders.add(folder_id)

    from dotenv import load_dotenv
    load_dotenv(os.path.join(MEDIA_SERVER_DIR, '.env'))

    api_key = os.getenv('GDRIVE_API_KEY') or os.getenv('GOOGLE_API_KEY')
    files_result = []

    # 1. API Key 방식 (하위 폴더 계층 정밀 재귀 탐색)
    if api_key:
        try:
            print(f"[gdrive_helper] 🔑 API Key로 탐색: folder_id={folder_id} (depth={depth})")
            query = urllib.parse.quote(f"'{folder_id}' in parents and trashed = false")
            fields = urllib.parse.quote("nextPageToken,files(id,name,mimeType,size,modifiedTime,webContentLink,thumbnailLink)")

            # 한 번의 files.list 호출은 pageSize(최대 1000)만큼만 돌려주므로, 항목이 그보다
            # 많은 폴더는 nextPageToken이 없어질 때까지 계속 이어서 호출해야 전체 목록이 잡힌다.
            # (예전엔 첫 페이지만 읽고 끝내서 큰 폴더의 하위 항목이 조용히 누락됐었음)
            page_token = None
            items = []
            page_count = 0
            while True:
                page_count += 1
                url = f"https://www.googleapis.com/drive/v3/files?q={query}&fields={fields}&key={api_key}&pageSize=1000"
                if page_token:
                    url += f"&pageToken={urllib.parse.quote(page_token)}"

                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))

                page_items = data.get('files', [])
                items.extend(page_items)
                print(f"[gdrive_helper] 🔑 API 페이지 {page_count}: {len(page_items)}개 항목 (누적 {len(items)}개, folder_id={folder_id})")

                page_token = data.get('nextPageToken')
                if not page_token:
                    break

            sub_specs = []
            for item in items:
                name = item.get('name', '')
                mime = item.get('mimeType', '')
                item_id = item.get('id', '')

                if mime == 'application/vnd.google-apps.folder':
                    if item_id not in visited_folders:
                        sub_rel = os.path.join(parent_subpath, name) if parent_subpath else name
                        sub_specs.append((item_id, sub_rel))
                elif any(name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    item['rel_folder'] = parent_subpath
                    files_result.append(item)

            files_result.extend(_fetch_subfolders_parallel(sub_specs, depth, max_depth, visited_folders, truncation_warnings))

            if files_result and depth == 0:
                print(f"[gdrive_helper] ✅ Google API 총 {len(files_result)}개 도서 수집 성공! ({page_count}페이지 조회)")
            return files_result
        except Exception as e:
            print(f"[gdrive_helper ⚠️] API Key fetch warning: {e}")

    # 2. 웹 공개 스크래핑 폴백 (data-id 기반 정밀 파서)
    # 구글 드라이브 HTML의 <tr data-selectable data-id="..." data-target="doc"> 블록에서
    # data-id(파일/폴더 실제 ID)와 aria-label(파일명 + 타입 힌트)을 동시에 추출합니다.
    # aria-label이 "Shared folder" 또는 "폴더"로 끝나면 서브폴더, 그 외는 파일입니다.
    try:
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        print(f"[gdrive_helper] 🌐 공개 웹 파서 탐색 시도: folder_id={folder_id} (depth={depth})")
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        print(f"[gdrive_helper DEBUG] HTML 수집 완료: {len(html):,} bytes")

        # <tr data-selectable data-id="REAL_ID" data-target="doc"> 블록 전체 파싱
        # → data-id에 파일/폴더 실제 Google ID가 온전히 들어있음
        tr_pattern = re.compile(
            r'<tr\s[^>]*data-selectable[^>]*data-id="(1[a-zA-Z0-9_-]{20,})"[^>]*>',
            re.IGNORECASE
        )

        seen_ids = set()
        seen_filenames = set()
        folders_to_recurse = []

        for m in tr_pattern.finditer(html):
            item_id = m.group(1)
            if item_id in seen_ids or item_id == folder_id:
                continue

            # <tr> 블록 내부 최대 3000자 분석
            block = html[m.start(): m.start() + 3000]
            block_end = block.find('</tr>')
            if block_end != -1:
                block = block[:block_end + 6]

            # aria-label에서 항목명 + 타입 힌트 추출
            al_match = re.search(r'aria-label="([^"]+)"', block)
            if not al_match:
                print(f"[gdrive_helper DEBUG] aria-label 없음: id={item_id}")
                continue

            raw_label = al_match.group(1)
            seen_ids.add(item_id)

            # ── 서브폴더 판정: "Shared folder" / "폴더" 키워드 ──
            is_subfolder = bool(re.search(r'(?:Shared folder|공유 폴더|\s폴더)$', raw_label, re.IGNORECASE))

            if is_subfolder:
                # 폴더명 추출 (끝의 타입 설명 제거)
                folder_name = re.sub(r'\s+(?:Shared folder|공유 폴더|폴더)$', '', raw_label, flags=re.IGNORECASE).strip()
                if item_id not in visited_folders:
                    print(f"[gdrive_helper] 📁 하위 폴더 감지: '{folder_name}' (ID: {item_id})")
                    folders_to_recurse.append((item_id, folder_name))
            else:
                # 파일명 추출 (접미사 설명 제거)
                fname = re.split(r'\s+(?:Compressed|Binary|Shared|공유됨|압축|archive)', raw_label)[0].strip()
                fname_key = fname.lower()

                # 지원 확장자 필터링
                if not any(fname_key.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    print(f"[gdrive_helper DEBUG] 미지원 확장자 스킵: '{fname}'")
                    continue

                if fname_key not in seen_filenames:
                    seen_filenames.add(fname_key)
                    print(f"[gdrive_helper] 📄 파일 감지: '{fname}' (ID: {item_id}, folder='{parent_subpath}')")
                    files_result.append({
                        'id': item_id,   # 실제 Google Drive 파일 ID
                        'name': fname,
                        'size': 0,
                        'modifiedTime': '',
                        'rel_folder': parent_subpath
                    })

        print(f"[gdrive_helper DEBUG] depth={depth} 파일={len(files_result)}개, 하위폴더={len(folders_to_recurse)}개 감지")

        # 잘림 감지: 이 depth에서 스크래핑으로 잡은 항목(파일+서브폴더) 수가 관측 상한 근처면,
        # 나머지는 브라우저 스크롤 시에만 로드되는 부분이라 이 요청 한 번으로는 못 잡았을 가능성이 높다.
        total_items_this_level = len(seen_ids)
        if total_items_this_level >= HTML_SCRAPE_SUSPECTED_PAGE_SIZE:
            warn_path = parent_subpath or '(루트)'
            print(
                f"[gdrive_helper] ⚠️ 잘림 의심: '{warn_path}' 폴더에서 {total_items_this_level}개 항목 감지 — "
                f"HTML 스크래핑은 페이지네이션을 지원하지 않아 이 이상은 누락됐을 수 있습니다. "
                f"정확한 결과가 필요하면 GDRIVE_API_KEY/GOOGLE_API_KEY 설정을 권장합니다."
            )
            truncation_warnings.append((warn_path, total_items_this_level))

        # 감지된 서브폴더들을 병렬로 재귀 진입
        sub_specs = [
            (sub_id, os.path.join(parent_subpath, sub_name) if parent_subpath else sub_name)
            for sub_id, sub_name in folders_to_recurse
        ]
        files_result.extend(_fetch_subfolders_parallel(sub_specs, depth, max_depth, visited_folders, truncation_warnings))

        if depth == 0:
            print(f"[gdrive_helper] 🎯 최종 수집 완료된 전체 도서 수: {len(files_result)}개")
            if truncation_warnings:
                affected = ', '.join(f"'{p}'({n}개)" for p, n in truncation_warnings)
                print(
                    f"[gdrive_helper] ⚠️⚠️ 결과 잘림 가능성 요약: {len(truncation_warnings)}개 폴더에서 "
                    f"항목이 누락됐을 수 있습니다 — {affected}. GDRIVE_API_KEY 설정을 강력히 권장합니다."
                )

    except Exception as e:
        print(f"[gdrive_helper ❌] Web scraping fallback error: {e}")

    return files_result


# 가상 경로(gdrive://folder_id/rel/path/filename)에는 실제 Drive 파일 바이트를 받아올 때
# 필요한 file_id가 들어있지 않다 (파일명만으로는 재검색이 필요해 비쌈). 등록 시점에 이미
# 알고 있는 file_id를 경로 끝에 얹어 저장해두면, 나중에 다시 목록을 조회하지 않고도
# 바로 다운로드할 수 있다. 파일명(및 그로부터 파생되는 제목/확장자 판별)은 별도의 원본
# filename 변수를 그대로 쓰는 다른 코드 경로들과 완전히 분리되어 있어, 이 마커가 화면
# 제목이나 확장자 판별에는 영향을 주지 않는다 (books.title은 file_path가 아니라 그
# 원본 filename에서만 파생됨 — tools/scanner/db_writer_sqlite.py의 insert_new_book_v2 참조).
GDRIVE_FILE_ID_MARKER = '?gid='


def encode_gdrive_file_id(path, file_id):
    """가상 경로 끝에 실제 Drive file_id를 얹어 인코딩한다. file_id가 없으면 원본 그대로 반환."""
    if not file_id or not path:
        return path
    return f"{path}{GDRIVE_FILE_ID_MARKER}{file_id}"


def split_gdrive_file_id(path):
    """encode_gdrive_file_id()로 인코딩된 경로를 (원래 경로, file_id)로 분리한다.
    마커가 없으면 (path, None)을 반환한다."""
    if not path or GDRIVE_FILE_ID_MARKER not in path:
        return path, None
    base, _, file_id = str(path).rpartition(GDRIVE_FILE_ID_MARKER)
    return base, (file_id or None)


def download_gdrive_file(file_id, dest_path, timeout=60):
    """Google Drive 파일 하나를 file_id로 내려받아 dest_path에 저장한다 (성공 시 True).

    API 키가 있으면 files.get?alt=media로 바로 받고, 없으면 공개 다운로드 엔드포인트를
    쓰되 대용량 파일에서 뜨는 "바이러스 검사 확인" 경고 페이지(confirm 토큰 필요)를 처리한다.
    임시 파일에 받은 뒤 원자적으로 rename하여, 다운로드 도중 실패해도 손상된 파일이
    캐시에 남지 않게 한다.
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.join(MEDIA_SERVER_DIR, '.env'))
    api_key = os.getenv('GDRIVE_API_KEY') or os.getenv('GOOGLE_API_KEY')

    tmp_path = dest_path + '.tmp'
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    try:
        if api_key:
            url = f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(file_id)}?alt=media&key={api_key}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp_path, 'wb') as out:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
        else:
            session_cookie = None
            confirm_token = None
            url = f"https://drive.google.com/uc?export=download&id={urllib.parse.quote(file_id)}"

            for _attempt in range(2):
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                if session_cookie:
                    req.add_header('Cookie', session_cookie)

                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'text/html' in content_type and confirm_token is None:
                        # 대용량 파일: urllib이 uc?export=download의 303 리다이렉트를 자동으로
                        # 따라가 drive.usercontent.google.com/download의 "바이러스 검사 불가"
                        # 확인 페이지에 도착한다. 이 페이지는 예전처럼 URL에 confirm=xxx가
                        # 붙어있는 게 아니라, <form>의 숨겨진 input(confirm/uuid)에 값이 있고
                        # 그 값들을 그대로 GET 쿼리로 재요청해야 실제 바이트가 내려온다.
                        html = resp.read().decode('utf-8', errors='ignore')
                        confirm_m = re.search(r'name="confirm"\s+value="([^"]*)"', html)
                        uuid_m = re.search(r'name="uuid"\s+value="([^"]*)"', html)
                        if not confirm_m or not uuid_m:
                            print(f"[gdrive_helper ❌] 다운로드 확인 페이지에서 confirm/uuid 토큰을 찾지 못함: file_id={file_id}")
                            return False
                        confirm_token = confirm_m.group(1)
                        uuid_token = uuid_m.group(1)
                        session_cookie = resp.headers.get('Set-Cookie')
                        url = (
                            "https://drive.usercontent.google.com/download"
                            f"?id={urllib.parse.quote(file_id)}&export=download"
                            f"&confirm={urllib.parse.quote(confirm_token)}&uuid={urllib.parse.quote(uuid_token)}"
                        )
                        continue

                    with open(tmp_path, 'wb') as out:
                        while True:
                            chunk = resp.read(1024 * 1024)
                            if not chunk:
                                break
                            out.write(chunk)
                    break
            else:
                return False

        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(tmp_path, dest_path)
        return True
    except Exception as e:
        print(f"[gdrive_helper ❌] 파일 다운로드 실패 (file_id={file_id}): {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return False


def resolve_gdrive_local_path(virtual_path):
    """gdrive:// 가상 경로를 실제 로컬 캐시 파일 경로로 해석한다.

    이미 로컬에 캐시돼 있으면 즉시 그 경로를 반환하고, 없으면 Drive에서 동기적으로
    받아온 뒤 캐시 경로를 반환한다 (첫 접근만 다운로드 비용을 치르고, 이후는 로컬
    캐시를 그대로 재사용). gdrive 가상 경로가 아니면 원본을 그대로 반환한다.
    """
    if not is_gdrive_url(virtual_path):
        return virtual_path

    base_path, file_id = split_gdrive_file_id(virtual_path)
    if not file_id:
        print(f"[gdrive_helper ⚠️] 가상 경로에 file_id가 없어 해석할 수 없습니다: {virtual_path}")
        return virtual_path

    from api.cache import disk_cache_manager
    # base_path(마커 제거된 경로)로 해시/확장자를 계산한다 — 전체 virtual_path를 쓰면
    # get_local_path()의 os.path.splitext()가 "?gid=..." 뒷부분까지 확장자로 잘못
    # 잡아 Windows에서 유효하지 않은 파일명(?  포함)이 만들어진다.
    local_path = disk_cache_manager.get_local_path(base_path)
    done_file = local_path + '.done'

    if os.path.exists(local_path) and os.path.exists(done_file):
        disk_cache_manager.update_access(local_path)
        return local_path

    print(f"[gdrive_helper] ⬇️ 원격 파일 캐시 없음, 동기 다운로드 시작: {os.path.basename(base_path)} (id={file_id})")
    disk_cache_manager.clean_up_if_needed()
    ok = download_gdrive_file(file_id, local_path)
    if not ok:
        return virtual_path

    with open(done_file, 'w') as f:
        f.write('done')
    disk_cache_manager.update_access(local_path)
    print(f"[gdrive_helper] ✅ 원격 파일 캐시 완료: {os.path.basename(base_path)}")
    return local_path


def is_gdrive_url(path):
    """
    주어진 경로가 구글 드라이브 웹 공유 URL(https://drive.google.com/...)이거나 gdrive:// 경로인지 판별합니다.
    """
    if not path:
        return False
    path_str = str(path).strip()
    # canonical_path()/join_canonical()가 "gdrive://id/..."를 os.path.normpath로 정규화하면서
    # 이중 슬래시가 "gdrive:/id/..."(단일 슬래시)로 접히므로, DB에 실제 저장되는 book.file_path는
    # 항상 이 형태다. 'gdrive://'만 검사하면 저장된 경로를 원격으로 인식하지 못해
    # is_remote_path()가 False를 반환하고 로컬 파일처럼 취급되어 열기가 조용히 실패한다.
    return path_str.startswith(('http://', 'https://', 'gdrive://', 'gdrive:')) or 'drive.google.com' in path_str

def is_remote_path(path):
    """
    주어진 경로가 원격 마운트(VFS, rclone, 네트워크 드라이브 등)인지 자동으로 판별합니다.
    """
    if not path:
        return False
        
    if is_gdrive_url(path):
        return True
        
    path = os.path.abspath(path)
    system = platform.system().lower()
    
    # 1. Windows 환경 판별
    if system == 'windows':
        try:
            import ctypes
            # 드라이브 문자 추출 (예: 'C:')
            drive = os.path.splitdrive(path)[0]
            if drive and len(drive) >= 2 and drive[1] == ':':
                drive_root = drive + "\\"
                # GetDriveTypeW 호출
                # 4 = DRIVE_REMOTE (네트워크 드라이브)
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_root)
                if drive_type == 4: # DRIVE_REMOTE
                    return True
        except Exception as e:
            print(f"[is_remote_path] Windows 드라이브 타입 체크 실패: {e}")
            
    # 2. Linux / Unix 환경 판별
    elif system in ('linux', 'darwin'):
        try:
            remote_mount = _find_best_remote_mount_point(path)
            if remote_mount:
                return True
        except Exception as e:
            print(f"[is_remote_path] Linux mounts 체크 실패: {e}")

    # 3. 공통 문자열 패턴 폴백 (예: 마운트 경로 관례 기반)
    # 사용자가 명시적으로 경로명에 클라우드 마운트 지점을 명시한 경우
    path_lower = path.lower()
    remote_keywords = ('gdrive', 'rclone', 'vfs', 'google_drive', 'onedrive', 'sharepoint', 'nas_share', 'webdav')
    if any(keyword in path_lower for keyword in remote_keywords):
        return True

    return False


def is_rclone_vfs_path(path):
    """
    Return True only for paths that are likely backed by rclone VFS/RC refresh.
    SMB/CIFS/NFS/NAS mounts are remote, but they are not valid rclone RC refresh targets.
    """
    if not path:
        return False

    if is_gdrive_url(path):
        return False

    path = os.path.abspath(path)
    system = platform.system().lower()

    if system in ('linux', 'darwin'):
        try:
            if _find_best_rclone_mount_point(path):
                return True
        except Exception as e:
            print(f"[is_rclone_vfs_path] Linux mounts 체크 실패: {e}")

    path_lower = path.lower()
    rclone_keywords = ('gdrive', 'rclone', 'vfs', 'google_drive', 'onedrive', 'sharepoint', 'webdav')
    return any(keyword in path_lower for keyword in rclone_keywords)

def get_rclone_relative_path(path):
    """
    로컬 물리 경로(절대 경로)를 rclone이 내부적으로 인지하는 
    VFS 마운트 기준의 가상 상대 경로로 파싱해 줍니다.
    """
    if not path:
        return ""
        
    path = os.path.abspath(path)
    system = platform.system().lower()
    
    # 1. Windows: G:\Library\Fantasy -> Library/Fantasy
    if system == 'windows':
        drive, rest = os.path.splitdrive(path)
        relative = rest.strip("\\/").replace("\\", "/")
        return relative
        
    # 2. Linux/Unix: /mnt/gdrive/Library/Fantasy -> Library/Fantasy
    elif system in ('linux', 'darwin'):
        try:
            mount_point = _find_best_rclone_mount_point(path)
        except Exception as e:
            print(f"[get_rclone_relative_path] Linux mounts 파싱 실패: {e}")
            mount_point = ''
            
        if mount_point:
            try:
                relative = os.path.relpath(path, mount_point)
            except Exception:
                relative = path[len(mount_point):].strip("\\/")
            if relative in ('.', ''):
                return '.'
            return relative.replace("\\", "/")
            
        # 3. 폴백: 마운트 포인트를 찾지 못한 경우 관례적 걷어내기
        parts = [p for p in path.split(os.sep) if p]
        if len(parts) > 2 and parts[0] in ('mnt', 'media', 'srv'):
            return "/".join(parts[2:])
            
    # 기본 폴백: 앞의 드라이브 문자나 첫 디렉토리를 날린 상대 경로 반환
    parts = [p for p in path.split(os.sep) if p]
    if len(parts) > 1:
        return "/".join(parts[1:])
        
    return path


def get_rclone_refresh_dirs(path):
    """
    Build ordered candidate directories for rclone rc vfs/refresh.
    This improves compatibility when a remote is mounted at root vs specific subfolder.
    """
    rel = get_rclone_relative_path(path)
    candidates = []

    def _push(value):
        value = '' if value is None else str(value)
        if value not in candidates:
            candidates.append(value)

    if rel:
        _push(rel)

    if rel in ('.', ''):
        _push('')
    elif '/' in rel:
        # Fallback for cases where mountpoint detection includes one extra prefix segment.
        _push(rel.split('/')[-1])

    # Last-resort root refresh for mount-root scoped remotes.
    _push('.')

    return candidates
