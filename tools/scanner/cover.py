# -*- coding: utf-8 -*-
import os
import shutil
import hashlib
import zipfile
import urllib.parse
import base64
import io
import xml.etree.ElementTree as ET
from PIL import Image

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COVERS_DIR = os.path.join(MEDIA_SERVER_DIR, 'covers')
os.makedirs(COVERS_DIR, exist_ok=True)

def extract_epub_cover_direct(epub_path, dest_path):
    """EPUB 파일 내에서 표지 이미지를 탐색하여 dest_path에 WebP 포맷으로 변환하여 저장"""
    try:
        with zipfile.ZipFile(epub_path, 'r') as zf:
            # 1) META-INF/container.xml 에서 rootfile path 획득
            container_xml = zf.read('META-INF/container.xml')
            root = ET.fromstring(container_xml)
            ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
            rootfile = root.find('.//ns:rootfile', ns)
            if rootfile is None:
                return False
            
            opf_path = rootfile.attrib.get('full-path')
            if not opf_path:
                return False
                
            # opf 디렉토리 확보
            opf_dir = os.path.dirname(opf_path)
            opf_content = zf.read(opf_path)
            opf_root = ET.fromstring(opf_content)
            
            # XML 네임스페이스 정의
            ns_opf = {
                'opf': 'http://www.idpf.org/2007/opf',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }
            
            # 표지 이미지 ID 찾기 (meta tag cover 또는 manifest에서 cover 단어 수색)
            cover_id = None
            meta_cover = opf_root.find(".//opf:meta[@name='cover']", ns_opf)
            if meta_cover is not None:
                cover_id = meta_cover.attrib.get('content')
                
            # manifest 아이템 맵 빌드
            manifest_items = {}
            for item in opf_root.findall(".//opf:manifest/opf:item", ns_opf):
                iid = item.attrib.get('id')
                href = item.attrib.get('href')
                media_type = item.attrib.get('media-type', '')
                if iid and href:
                    manifest_items[iid] = (href, media_type)
            
            cover_href = None
            if cover_id in manifest_items:
                cover_href = manifest_items[cover_id][0]
            else:
                # Fallback: manifest 항목 중 파일명이나 id에 'cover', 'thumbnail'이 들어간 이미지 파일을 스캔
                for iid, (href, media_type) in manifest_items.items():
                    if 'image' in media_type:
                        low_href = href.lower()
                        low_id = iid.lower()
                        if 'cover' in low_href or 'cover' in low_id or 'thumb' in low_href or 'thumb' in low_id:
                            cover_href = href
                            break
                
                # Still None? manifest의 첫 번째 이미지 사용
                if not cover_href:
                    for iid, (href, media_type) in manifest_items.items():
                        if 'image' in media_type:
                            cover_href = href
                            break
                            
            if cover_href:
                cover_href = urllib.parse.unquote(cover_href)
                # 상대 경로 교정
                actual_img_path = os.path.normpath(os.path.join(opf_dir, cover_href)).replace('\\', '/')
                
                # zip 리스트에 매칭되는 실제 파일 찾기
                zip_names = zf.namelist()
                matched_name = None
                for zname in zip_names:
                    if zname.lower() == actual_img_path.lower() or zname.lower().endswith(actual_img_path.lower()):
                        matched_name = zname
                        break
                        
                if not matched_name:
                    # 한번 더 fallback: href 파일명 단독 매칭
                    base_img_name = os.path.basename(actual_img_path)
                    for zname in zip_names:
                        if os.path.basename(zname).lower() == base_img_name.lower():
                            matched_name = zname
                            break
                            
                if matched_name:
                    img_data = zf.read(matched_name)
                    # Pillow를 통한 WebP 인코딩 저장
                    try:
                        img = Image.open(io.BytesIO(img_data))
                        img.save(dest_path, "WEBP", quality=80)
                    except Exception as e:
                        print(f"[Scanner-EPUB-Cover] WebP 인코딩 실패, 원본 바이너리 저장: {e}")
                        with open(dest_path, 'wb') as out_f:
                            out_f.write(img_data)
                    del img_data
                    return True
    except Exception as e:
        print(f"[Scanner-EPUB-Cover] EPUB 표지 추출 중 예외 발생 ({epub_path}): {e}")
    return False

def download_cover_from_url(file_path, image_url, force=False, library_id=None):
    """온라인 URL에서 표지 이미지를 다운로드하여 WebP로 저장 (series.json의 image 필드 전용)"""
    if not image_url or not image_url.startswith('http'):
        return None
    
    import urllib.request
    import ssl
    
    # 파일 전체 경로 기반 MD5 해시 파일명 생성
    book_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    cover_filename = f"book_{book_hash}.webp"
    
    if library_id is not None:
        dest_dir = os.path.join(COVERS_DIR, str(library_id))
        os.makedirs(dest_dir, exist_ok=True)
        db_cover_path = f"{library_id}/{cover_filename}"
    else:
        dest_dir = COVERS_DIR
        db_cover_path = cover_filename
        
    cover_filepath = os.path.join(dest_dir, cover_filename)
    
    # 이미 존재하면 재다운로드 스킵 (force가 아닐 때만)
    if not force and os.path.exists(cover_filepath) and os.path.getsize(cover_filepath) > 0:
        return db_cover_path

    try:
        # SSL 인증서 문제 방지용 컨텍스트
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            img_data = resp.read()
        
        try:
            img = Image.open(io.BytesIO(img_data))
            img.save(cover_filepath, "WEBP", quality=80)
        except Exception as e:
            print(f"[Scanner-Cover] URL 이미지 WebP 인코딩 실패: {e}. 원본 저장 시도.")
            with open(cover_filepath, 'wb') as out_f:
                out_f.write(img_data)
        
        print(f"[Scanner-Cover] URL 표지 다운로드 완료: '{image_url}' -> '{db_cover_path}'")
        return db_cover_path
    except Exception as e:
        print(f"[Scanner-Cover] URL 표지 다운로드 실패 ({image_url}): {e}")
        return None


def extract_cover_from_b64(file_path, cover_b64, force=False, library_id=None):
    """Base64 이미지를 디코딩하여 WebP 포맷으로 covers/{library_id} 폴더에 저장하고 상대 경로를 반환 (force=True인 경우 강제 재생성)"""
    try:
        import re
        # Remove data URI scheme prefix if exists (e.g. data:image/jpeg;base64,)
        if "," in cover_b64:
            cover_b64 = cover_b64.split(",", 1)[1]
            
        # Clean up all invalid base64 characters including whitespaces/newlines
        cover_b64 = re.sub(r'[^A-Za-z0-9+/=_-]', '', cover_b64)
        
        # Remove any existing padding to recalculate
        cover_b64 = cover_b64.rstrip('=')
        
        # A valid base64 string without padding cannot have a length % 4 == 1.
        # If it does, we trim the trailing garbage character.
        if len(cover_b64) % 4 == 1:
            cover_b64 = cover_b64[:-1]
            
        missing_padding = len(cover_b64) % 4
        if missing_padding:
            cover_b64 += '=' * (4 - missing_padding)
            
        img_data = base64.b64decode(cover_b64)
        
        # 파일 전체 경로 기반 MD5 해시 파일명 생성 (동일 파일명 충돌 원천 해결, webp 고정)
        book_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
        cover_filename = f"book_{book_hash}.webp"
        
        if library_id is not None:
            dest_dir = os.path.join(COVERS_DIR, str(library_id))
            os.makedirs(dest_dir, exist_ok=True)
            db_cover_path = f"{library_id}/{cover_filename}"
        else:
            dest_dir = COVERS_DIR
            db_cover_path = cover_filename
            
        cover_filepath = os.path.join(dest_dir, cover_filename)
        
        # 이미 로컬 커버 디렉터리에 파일이 존재한다면 디코딩/쓰기 스킵 (force가 아닐 때만)
        if not force and os.path.exists(cover_filepath) and os.path.getsize(cover_filepath) > 0:
            return db_cover_path
            
        # Pillow를 통한 WebP 인코딩 저장
        try:
            img = Image.open(io.BytesIO(img_data))
            img.save(cover_filepath, "WEBP", quality=80)
        except Exception as e:
            print(f"[Scanner-Cover] Base64 이미지 식별/WebP 렌더링 실패 (바이너리 손상 의심): {e}. 원본 파일 내 표지 추출로 Fallback합니다.")
            return None
                
        print(f"[Scanner DEBUG] 커버 복원 완료 (WebP): '{file_path}' -> '{cover_filepath}' (바이너리 크기: {len(img_data)} bytes), Force={force}")
        del img_data
        return db_cover_path
    except Exception as e:
        import traceback
        print(f"[Scanner] 커버 복원 실패 ({file_path}): {e}")
        traceback.print_exc()
        return None

def get_series_cover_fallback(series_name, folder_path, force=False, is_remote=False, filename=None, file_path=None, library_id=None):
    """시리즈 이름(혹은 개별 책 파일명)에 해당하는 캐시 커버가 존재하는지 검사하고,
    작품 폴더 내에 cover.jpg/png 등이 있으면 이를 WebP로 인코딩하여 covers/{library_id} 디렉토리에 저장.
    없다면 해당 폴더(혹은 지정된 압축파일)에서 첫 이미지를 WebP 표지로 강제 추출하여 생성 (force=True인 경우 덮어쓰기)
    """
    if not series_name:
        return None
    
    # 만약 전체 경로(file_path)가 제공되었다면 이를 사용하고, 없으면 folder_path + filename 결합 고유화
    target_path_seed = file_path
    if not target_path_seed and filename:
        target_path_seed = os.path.join(folder_path, filename)
        
    if target_path_seed:
        book_hash = hashlib.md5(target_path_seed.encode('utf-8')).hexdigest()
        cover_filename = f"book_{book_hash}.webp"
    else:
        series_hash = hashlib.md5(series_name.encode('utf-8')).hexdigest()
        cover_filename = f"series_{series_hash}.webp"

    if library_id is not None:
        dest_dir = os.path.join(COVERS_DIR, str(library_id))
        os.makedirs(dest_dir, exist_ok=True)
        db_cover_path = f"{library_id}/{cover_filename}"
    else:
        dest_dir = COVERS_DIR
        db_cover_path = cover_filename

    local_cover_path = os.path.join(dest_dir, cover_filename)
    
    if not force and os.path.exists(local_cover_path) and os.path.getsize(local_cover_path) > 0:
        return db_cover_path
        
    # ── [분기 1] 개별 책(filename) 전용 1:1 매핑 커버 파일 수색 ──
    if filename:
        base_name, _ = os.path.splitext(filename)
        for ext_candidate in ['.jpg', '.jpeg', '.png', '.webp']:
            cand_filename = base_name + ext_candidate
            cand_path = os.path.join(folder_path, cand_filename)
            if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
                try:
                    with Image.open(cand_path) as img:
                        img.save(local_cover_path, "WEBP", quality=80)
                    print(f"[Scanner-Cover] 개별 도서 1:1 매핑 커버 WebP 변환 복사 완료: {cand_path} -> {local_cover_path}, Force={force}")
                    return db_cover_path
                except Exception as e:
                    print(f"[Scanner-Cover] 개별 도서 1:1 매핑 커버 WebP 변환 복사 실패: {e}. 일반 복사 시도.")
                    try:
                        shutil.copy2(cand_path, local_cover_path)
                        return db_cover_path
                    except Exception as e2:
                        print(f"[Scanner-Cover] 개별 도서 복사 백업도 실패: {e2}")
    else:
        # ── [분기 2] 시리즈(filename 없음) 대표 공통 커버 수색 ──
        candidates = ['cover.jpg', 'cover.png', 'folder.jpg', 'folder.png']
        for cand in candidates:
            cand_path = os.path.join(folder_path, cand)
            if os.path.exists(cand_path) and os.path.getsize(cand_path) > 0:
                try:
                    with Image.open(cand_path) as img:
                        img.save(local_cover_path, "WEBP", quality=80)
                    print(f"[Scanner-Cover] 시리즈 대표 공통 커버 WebP 변환 복사 완료: {cand_path} -> {local_cover_path}, Force={force}")
                    return db_cover_path
                except Exception as e:
                    print(f"[Scanner-Cover] 시리즈 대표 공통 커버 WebP 변환 복사 실패: {e}. 일반 복사 시도.")
                    try:
                        shutil.copy2(cand_path, local_cover_path)
                        return db_cover_path
                    except Exception as e2:
                        print(f"[Scanner-Cover] 시리즈 대표 복사 백업도 실패: {e2}")

    # 원격지 경로(VFS)인 경우 대량 스캔 중 원격 압축 파일 I/O를 원천 차단하기 위해 분석을 스킵합니다.
    if is_remote:
        print(f"[Scanner-Cover] 원격 경로 감지로 압축 파일/EPUB 내 표지 자동 추출 스킵: {folder_path}")
        return None

    try:
        from utils.sort_helper import natural_sort_key
        
        # filename이 지정되었다면 해당 파일만 타겟으로 하고, 없으면 폴더 내 첫 번째 파일을 타겟으로 함
        if filename:
            target_files = [filename]
        else:
            target_files = sorted(
                [f for f in os.listdir(folder_path) if f.lower().endswith(('.zip', '.cbz', '.epub'))],
                key=natural_sort_key
            )
        
        if target_files:
            target_file_path = os.path.join(folder_path, target_files[0])
            img_ext = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
            
            if target_file_path.lower().endswith('.epub'):
                if extract_epub_cover_direct(target_file_path, local_cover_path):
                    print(f"[Scanner-Cover-Auto] EPUB 표지 자동 추출 완료: '{target_file_path}' -> '{local_cover_path}'")
                    return db_cover_path
            elif target_file_path.lower().endswith('.pdf'):
                # OOM 및 Worker Timeout 방지를 위해 PDF 대량 표지 추출을 임시 제외 처리합니다.
                print(f"[Scanner-Cover-Auto] PDF 표지 자동 추출 임시 제외 처리 (Lazy 스캔 연동 대기): '{target_file_path}'")
                return None
            elif target_file_path.lower().endswith(('.zip', '.cbz')):
                try:
                    with zipfile.ZipFile(target_file_path, 'r') as zf:
                        infolist = zf.infolist()
                        img_infos = sorted(
                            [info for info in infolist if info.filename.lower().endswith(img_ext)],
                            key=lambda x: natural_sort_key(x.filename)
                        )
                        
                        if img_infos:
                            first_img_name = img_infos[0].filename
                            img_data = zf.read(first_img_name)
                            
                            # Pillow를 통한 WebP 인코딩 저장
                            try:
                                img = Image.open(io.BytesIO(img_data))
                                img.save(local_cover_path, "WEBP", quality=80)
                            except Exception as e:
                                print(f"[Scanner-Cover-Auto] WebP 인코딩 실패, 원본 바이너리 저장: {e}")
                                with open(local_cover_path, 'wb') as img_f:
                                    img_f.write(img_data)
                                    
                            print(f"[Scanner-Cover-Auto] 압축 파일 첫 페이지 추출 및 표지 생성 완료: '{target_file_path}' ({first_img_name}) -> '{local_cover_path}', Force={force}")
                            return db_cover_path
                        else:
                            raise ValueError("압축파일 내에 이미지 파일이 존재하지 않습니다.")
                except zipfile.BadZipFile as bzf:
                    raise zipfile.BadZipFile(f"압축 파일이 손상되었거나 유효하지 않은 Zip 포맷입니다: {os.path.basename(target_file_path)}")
                except Exception as e:
                    raise e
    except Exception as e:
        print(f"[Scanner-Cover-Auto] 파일 내 첫 이미지 추출 실패 ({series_name}): {e}")
        raise e
                
    return None
