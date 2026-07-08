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
from tools.scanner.folder_image import find_common_cover, find_individual_cover

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COVERS_DIR = os.path.join(MEDIA_SERVER_DIR, 'covers')
os.makedirs(COVERS_DIR, exist_ok=True)

SUPPORTED_IMAGE_FORMATS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')

def extract_epub_cover_direct(epub_path, dest_path):
    """Search cover image in EPUB file, convert to WebP format and save to dest_path"""
    try:
        with zipfile.ZipFile(epub_path, 'r') as zf:
            # 1) Get rootfile path from META-INF/container.xml
            container_xml = zf.read('META-INF/container.xml')
            root = ET.fromstring(container_xml)
            ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
            rootfile = root.find('.//ns:rootfile', ns)
            if rootfile is None:
                return False
            
            opf_path = rootfile.attrib.get('full-path')
            if not opf_path:
                return False
                
            # Get opf directory
            opf_dir = os.path.dirname(opf_path)
            opf_content = zf.read(opf_path)
            opf_root = ET.fromstring(opf_content)
            
            # Define XML namespaces
            ns_opf = {
                'opf': 'http://www.idpf.org/2007/opf',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }
            
            # Find cover image ID (search cover in meta tag or manifest)
            cover_id = None
            meta_cover = opf_root.find(".//opf:meta[@name='cover']", ns_opf)
            if meta_cover is not None:
                cover_id = meta_cover.attrib.get('content')
                
            # Build manifest item map
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
                # Fallback: scan image files with 'cover', 'thumbnail' in filename or id in manifest
                for iid, (href, media_type) in manifest_items.items():
                    if 'image' in media_type:
                        low_href = href.lower()
                        low_id = iid.lower()
                        if 'cover' in low_href or 'cover' in low_id or 'thumb' in low_href or 'thumb' in low_id:
                            cover_href = href
                            break
                
                # Still None? Use first image in manifest
                if not cover_href:
                    for iid, (href, media_type) in manifest_items.items():
                        if 'image' in media_type:
                            cover_href = href
                            break
                            
            if cover_href:
                cover_href = urllib.parse.unquote(cover_href)
                # Correct relative path
                actual_img_path = os.path.normpath(os.path.join(opf_dir, cover_href)).replace('\\', '/')
                
                # Find actual file matching in zip list
                zip_names = zf.namelist()
                matched_name = None
                for zname in zip_names:
                    if zname.lower() == actual_img_path.lower() or zname.lower().endswith(actual_img_path.lower()):
                        matched_name = zname
                        break
                        
                if not matched_name:
                    # One more fallback: href filename only match
                    base_img_name = os.path.basename(actual_img_path)
                    for zname in zip_names:
                        if os.path.basename(zname).lower() == base_img_name.lower():
                            matched_name = zname
                            break
                            
                if matched_name:
                    img_data = zf.read(matched_name)
                    # Save via Pillow WebP encoding
                    try:
                        with Image.open(io.BytesIO(img_data)) as img:
                            img.save(dest_path, "WEBP", quality=80)
                    except Exception as e:
                        print(f"[Scanner-EPUB-Cover] WebP encoding failed, saving original binary: {e}")
                        with open(dest_path, 'wb') as out_f:
                            out_f.write(img_data)
                    del img_data
                    return True
    except Exception as e:
        print(f"[Scanner-EPUB-Cover] Exception during EPUB cover extraction ({epub_path}): {e}")
    return False

def download_cover_from_url(file_path, image_url, force=False, library_id=None):
    """Download cover image from URL and save as WebP (series.json image field only)"""
    if not image_url or not image_url.startswith('http'):
        return None
    
    import urllib.request
    import ssl
    
    # Create MD5 hash filename based on full file path
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
    
    # Skip re-download if already exists (only when force=False)
    if not force and os.path.exists(cover_filepath) and os.path.getsize(cover_filepath) > 0:
        return db_cover_path

    try:
        # Context to prevent SSL cert issues
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
            print(f"[Scanner-Cover] URL image WebP encoding failed: {e}. Trying original save.")
            with open(cover_filepath, 'wb') as out_f:
                out_f.write(img_data)
        
        print(f"[Scanner-Cover] URL cover download complete: '{image_url}' -> '{db_cover_path}'")
        return db_cover_path
    except Exception as e:
        print(f"[Scanner-Cover] URL cover download failed ({image_url}): {e}")
        return None


def extract_cover_from_b64(file_path, cover_b64, force=False, library_id=None):
    """Decode Base64 image and save as WebP format in covers/{library_id} folder and return relative path (force regenerate if force=True)"""
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
        
        # Create MD5 hash filename based on full file path (동일 파일명 충돌 원천 해결, webp 고정)
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
        
        # Skip decode/write if file already exists in local cover directory (only when force=False)
        if not force and os.path.exists(cover_filepath) and os.path.getsize(cover_filepath) > 0:
            return db_cover_path
            
        # Save via Pillow WebP encoding
        try:
            img = Image.open(io.BytesIO(img_data))
            img.save(cover_filepath, "WEBP", quality=80)
        except Exception as e:
            print(f"[Scanner-Cover] Base64 image identify/WebP render failed (binary corruption suspected): {e}. Fallback to cover extraction in original file.")
            return None
                
        print(f"[Scanner DEBUG] Cover restore complete (WebP): '{file_path}' -> '{cover_filepath}' (Binary size: {len(img_data)} bytes), Force={force}")
        del img_data
        return db_cover_path
    except Exception as e:
        import traceback
        print(f"[Scanner] Cover restore failed ({file_path}): {e}")
        traceback.print_exc()
        return None

def get_series_cover_fallback(series_name, folder_path, force=False, is_remote=False, filename=None, file_path=None, library_id=None):
    """Check if cache cover corresponding to series name (or individual book filename) exists,
    If cover.jpg/png etc exists in folder, encode it to WebP and save to covers/{library_id} directory.
    If not, force extract first image from folder (or specified archive) as WebP cover (overwrite if force=True)
    """
    if not series_name:
        return None
    
    # If full path (file_path) provided, use it, else combine folder_path + filename to make unique
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
        
    # -- [Branch 1] Search individual book (filename) 1:1 mapped cover file --
    cand_path = find_individual_cover(folder_path, filename) if filename else None
    if cand_path:
        try:
            with Image.open(cand_path) as img:
                img.save(local_cover_path, "WEBP", quality=80)
            print(f"[Scanner-Cover] Individual book 1:1 mapped cover WebP convert copy complete: {cand_path} -> {local_cover_path}, Force={force}")
            return db_cover_path
        except Exception as e:
            print(f"[Scanner-Cover] Individual book 1:1 mapped cover WebP convert copy failed: {e}. Trying general copy.")
            try:
                shutil.copy2(cand_path, local_cover_path)
                return db_cover_path
            except Exception as e2:
                print(f"[Scanner-Cover] Individual book copy backup also failed: {e2}")

    # -- [Branch 2] Search series representative common cover (also fallback for individual books) --
    cand_path = find_common_cover(folder_path)
    if cand_path:
        try:
            with Image.open(cand_path) as img:
                img.save(local_cover_path, "WEBP", quality=80)
            print(f"[Scanner-Cover] Series representative common cover WebP convert copy complete: {cand_path} -> {local_cover_path}, Force={force}")
            return db_cover_path
        except Exception as e:
            print(f"[Scanner-Cover] Series representative common cover WebP convert copy failed: {e}. Trying general copy.")
            try:
                shutil.copy2(cand_path, local_cover_path)
                return db_cover_path
            except Exception as e2:
                print(f"[Scanner-Cover] Series representative copy backup also failed: {e2}")

    # If remote path (VFS), skip analysis to block remote archive file I/O during mass scan.
    if is_remote:
        print(f"[Scanner-Cover] Skip automatic cover extraction in archive/EPUB due to remote path detection: {folder_path}")
        return None

    try:
        from utils.sort_helper import natural_sort_key
        
        # If filename specified, target only that file, else target first file in folder
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
                    print(f"[Scanner-Cover-Auto] EPUB cover auto extraction complete: '{target_file_path}' -> '{local_cover_path}'")
                    return db_cover_path
            elif target_file_path.lower().endswith('.pdf'):
                # Temporarily exclude mass PDF cover extraction to prevent OOM and Worker Timeout.
                print(f"[Scanner-Cover-Auto] PDF cover auto extraction temporarily excluded (waiting for Lazy Scan): '{target_file_path}'")
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
                            
                            # Save via Pillow WebP encoding
                            try:
                                with Image.open(io.BytesIO(img_data)) as img:
                                    img.save(local_cover_path, "WEBP", quality=80)
                            except Exception as e:
                                print(f"[Scanner-Cover-Auto] WebP encoding failed, saving original binary: {e}")
                                with open(local_cover_path, 'wb') as img_f:
                                    img_f.write(img_data)
                                    
                            print(f"[Scanner-Cover-Auto] First page extraction and cover generation complete: '{target_file_path}' ({first_img_name}) -> '{local_cover_path}', Force={force}")
                            return db_cover_path
                        else:
                            raise ValueError("No image files found in archive.")
                except zipfile.BadZipFile as bzf:
                    raise zipfile.BadZipFile(f"Archive is corrupted or invalid Zip format: {os.path.basename(target_file_path)}")
                except Exception as e:
                    raise e
    except Exception as e:
        print(f"[Scanner-Cover-Auto] Failed to extract first image in file ({series_name}): {e}")
        raise e
                
    return None


def get_imgdir_cover(folder_path, virtual_file_path, force=False, library_id=None):
    """Extract cover for image-directory books and save as WebP."""
    if not folder_path or not virtual_file_path:
        return None

    cover_hash = hashlib.md5(virtual_file_path.encode('utf-8')).hexdigest()
    cover_filename = f"book_{cover_hash}.webp"

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

    candidate = find_common_cover(folder_path)
    if not candidate:
        from utils.sort_helper import natural_sort_key
        image_files = sorted(
            [f for f in os.listdir(folder_path) if f.lower().endswith(SUPPORTED_IMAGE_FORMATS)],
            key=natural_sort_key
        )
        if image_files:
            candidate = os.path.join(folder_path, image_files[0])

    if not candidate or not os.path.exists(candidate):
        return None

    try:
        with Image.open(candidate) as img:
            img.save(local_cover_path, "WEBP", quality=80)
        print(f"[Scanner-Cover-IMGDIR] Cover generated: '{candidate}' -> '{local_cover_path}'")
        return db_cover_path
    except Exception as e:
        print(f"[Scanner-Cover-IMGDIR] Cover extraction failed ({candidate}): {e}")
        return None
