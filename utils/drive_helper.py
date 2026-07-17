# -*- coding: utf-8 -*-
import os
import platform
import sys


_REMOTE_FS_TYPES = ('fuse.rclone', 'rclone', 'cifs', 'nfs', 'nfs4', 'davfs', 'smbfs', 'fuse', 'sshfs')


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


def _find_best_remote_mount_point(path):
    """Find the longest matching remote mount point that contains path."""
    best = ''
    for mount_point, fstype in _iter_mounts() or []:
        if mount_point == '/':
            continue
        if not any(t in fstype for t in _REMOTE_FS_TYPES):
            continue
        if _is_same_or_subpath(path, mount_point) and len(mount_point) > len(best):
            best = mount_point
    return best

def is_remote_path(path):
    """
    주어진 경로가 원격 마운트(VFS, rclone, 네트워크 드라이브 등)인지 자동으로 판별합니다.
    """
    if not path:
        return False
        
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
            mount_point = _find_best_remote_mount_point(path)
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
