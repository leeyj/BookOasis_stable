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

SUPPORTED_EXTENSIONS = ('.zip', '.cbz', '.rar', '.cbr', '.epub', '.pdf', '.txt', '.yaml', '.xml', '.json')

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

def fetch_gdrive_folder_files(folder_id_or_url, parent_subpath="", depth=0, max_depth=4, visited_folders=None):
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
            fields = urllib.parse.quote("files(id,name,mimeType,size,modifiedTime,webContentLink,thumbnailLink)")
            url = f"https://www.googleapis.com/drive/v3/files?q={query}&fields={fields}&key={api_key}&pageSize=1000"
            
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                items = data.get('files', [])
                for item in items:
                    print(item)
                    name = item.get('name', '')
                    mime = item.get('mimeType', '')
                    item_id = item.get('id', '')

                    if mime == 'application/vnd.google-apps.folder':
                        if item_id not in visited_folders:
                            sub_rel = os.path.join(parent_subpath, name) if parent_subpath else name
                            sub_files = fetch_gdrive_folder_files(item_id, parent_subpath=sub_rel, depth=depth+1, max_depth=max_depth, visited_folders=visited_folders)
                            files_result.extend(sub_files)
                    elif any(name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                        item['rel_folder'] = parent_subpath
                        files_result.append(item)

                if files_result and depth == 0:
                    print(f"[gdrive_helper] ✅ Google API 총 {len(files_result)}개 도서 수집 성공!")
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

        # 감지된 서브폴더 재귀 진입
        for sub_id, sub_name in folders_to_recurse:
            sub_rel = os.path.join(parent_subpath, sub_name) if parent_subpath else sub_name
            print(f"[gdrive_helper] 📂 재귀 진입: '{sub_name}' (ID: {sub_id})")
            sub_files = fetch_gdrive_folder_files(
                sub_id, parent_subpath=sub_rel,
                depth=depth + 1, max_depth=max_depth,
                visited_folders=visited_folders
            )
            files_result.extend(sub_files)

        if depth == 0:
            print(f"[gdrive_helper] 🎯 최종 수집 완료된 전체 도서 수: {len(files_result)}개")

    except Exception as e:
        print(f"[gdrive_helper ❌] Web scraping fallback error: {e}")

    return files_result

def is_gdrive_url(path):
    """
    주어진 경로가 구글 드라이브 웹 공유 URL(https://drive.google.com/...)이거나 gdrive:// 경로인지 판별합니다.
    """
    if not path:
        return False
    path_str = str(path).strip()
    return path_str.startswith(('http://', 'https://', 'gdrive://')) or 'drive.google.com' in path_str

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
