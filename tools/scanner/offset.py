# -*- coding: utf-8 -*-
import os
import zipfile
from utils.sort_helper import natural_sort_key

IMG_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')


def _offsets_from_zipfile(zf):
    """열려 있는 zipfile.ZipFile(로컬 파일이든 메모리 버퍼든)에서 이미지 항목의
    오프셋 메타데이터를 (page_idx, filename, header_offset, compress_size, file_size, compress_type)
    튜플 리스트로 뽑아낸다. 로컬 스캔과 gdrive 원격(Range 기반) 스캔이 이 로직을 공유한다."""
    img_infos = [info for info in zf.infolist() if info.filename.lower().endswith(IMG_EXT)]
    img_infos.sort(key=lambda x: natural_sort_key(x.filename))
    return [
        (page_idx, info.filename, info.header_offset, info.compress_size, info.file_size, info.compress_type)
        for page_idx, info in enumerate(img_infos)
    ]


def resolve_data_offset_from_header_bytes(header_offset, header_bytes):
    """로컬 파일 헤더 30바이트(그 이상이어도 앞 30바이트만 사용)를 파싱해 fname_len/extra_len을
    반영한, 압축 데이터가 실제로 시작하는 바이트 위치를 계산한다. 시그니처가 아니거나 길이가
    부족하면 None — 호출자는 이 경우 기존 2-왕복 헤더 프로브 방식으로 안전하게 폴백해야 한다.

    utils/drive_helper.py의 fetch_gdrive_page_bytes()가 서빙 시점에 매번 하던 것과 동일한
    파싱을, 이미 읽어둔(또는 스캔 시점에 미리 읽은) 바이트에 대해 재사용 가능하도록 뽑아낸
    순수 함수다 — 로컬 파일 핸들 기반 스캔과 gdrive tail 버퍼 기반 스캔이 함께 쓴다."""
    header = header_bytes[:30]
    if len(header) != 30 or header[:4] != b'PK\x03\x04':
        return None
    fn_len = int.from_bytes(header[26:28], 'little')
    extra_len = int.from_bytes(header[28:30], 'little')
    return header_offset + 30 + fn_len + extra_len


def _resolve_data_offset(file_handle, header_offset):
    """로컬 파일 핸들에서 header_offset의 실제 로컬 파일 헤더를 읽어 검증된 data_offset을 계산한다.

    이건 central directory 메타데이터만으로 추정하는 게 아니라, 스캔 시점에 실제
    로컬 헤더를 한 번 읽어서 검증된 값을 얻는 것 — 원격(gdrive) 서빙 시점에 매 페이지마다
    걸던 '헤더 프로브' 왕복 요청을 스캔 때 미리 대신 치러두는 셈이다. 실패하면 None을
    반환해 호출자가 그 페이지만 조용히 건너뛰게 하고, 서빙 쪽은 기존 2-왕복 프로브로
    안전하게 폴백한다."""
    try:
        file_handle.seek(header_offset)
        header = file_handle.read(30)
        return resolve_data_offset_from_header_bytes(header_offset, header)
    except Exception:
        return None


def _offsets_with_data_offset(zf, file_path):
    """_offsets_from_zipfile 결과에 data_offset(검증된 로컬 헤더 기반 값)을 덧붙인다.
    file_path는 이 시점에 항상 로컬에서 열람 가능해야 한다(gdrive 원본은 스캔 전에
    이미 로컬 디스크 캐시로 내려받아둔 뒤 이 함수에 전달됨)."""
    rows = _offsets_from_zipfile(zf)
    if not rows:
        return []

    try:
        with open(file_path, 'rb') as f:
            return [
                (page_idx, filename, header_offset, compress_size, file_size, compress_type,
                 _resolve_data_offset(f, header_offset))
                for page_idx, filename, header_offset, compress_size, file_size, compress_type in rows
            ]
    except Exception as e:
        print(f"[Scanner-Offset] '{os.path.basename(file_path)}' data_offset resolve failed (fallback to header-probe serving): {e}")
        return [row + (None,) for row in rows]


def collect_zip_offsets(cursor, book_id, file_path):
    """Analyze image entries of ZIP file and collect byte offset metadata (reuse active cursor)"""
    if not os.path.exists(file_path):
        return

    try:
        cursor.execute("DELETE FROM book_offsets WHERE book_id = ?", (book_id,))

        with zipfile.ZipFile(file_path, 'r') as zf:
            bulk_data = [
                (book_id, page_idx, filename, header_offset, compress_size, file_size, compress_type, data_offset)
                for page_idx, filename, header_offset, compress_size, file_size, compress_type, data_offset in _offsets_with_data_offset(zf, file_path)
            ]

            if bulk_data:
                cursor.executemany("""
                    INSERT INTO book_offsets
                    (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type, data_offset)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, bulk_data)

                cursor.execute("""
                    UPDATE books SET
                        total_pages = ?,
                        has_offsets = 1
                    WHERE id = ?
                """, (len(bulk_data), book_id))

        print(f"[Scanner-Offset] '{os.path.basename(file_path)}' offset index complete (total {len(bulk_data)} pages)")
    except Exception as e:
        print(f"[Scanner-Offset] '{os.path.basename(file_path)}' offset index failed: {e}")

def collect_zip_offsets_data(file_path):
    """Analyze image entries of ZIP file and collect byte offset metadata (pure memory parsing)"""
    if not os.path.exists(file_path):
        return []

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            return _offsets_with_data_offset(zf, file_path)
    except Exception as e:
        print(f"[Scanner-Offset] '{os.path.basename(file_path)}' offset parsing failed: {e}")
        return []
