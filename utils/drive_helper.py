# -*- coding: utf-8 -*-
import os
import platform
import sys

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
            # /proc/mounts 파일이 있는지 확인
            if os.path.exists('/proc/mounts'):
                with open('/proc/mounts', 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 3:
                            mount_point = parts[1]
                            fstype = parts[2].lower()
                            # 대상 경로가 해당 마운트 지점의 하위 경로인지 확인
                            if path.startswith(mount_point):
                                # 원격 파일 시스템 종류 매칭
                                remote_types = ('fuse.rclone', 'rclone', 'cifs', 'nfs', 'nfs4', 'davfs', 'smbfs', 'fuse', 'sshfs')
                                if any(t in fstype for t in remote_types):
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
        mount_point = ""
        try:
            if os.path.exists('/proc/mounts'):
                with open('/proc/mounts', 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            pt = parts[1]
                            if path.startswith(pt) and len(pt) > len(mount_point) and pt != '/':
                                mount_point = pt
        except Exception as e:
            print(f"[get_rclone_relative_path] Linux mounts 파싱 실패: {e}")
            
        if mount_point:
            relative = path[len(mount_point):].strip("\\/")
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
