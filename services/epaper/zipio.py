# -*- coding: utf-8 -*-
"""EPUB(ZIP) 안전하게 읽기 + 결정적으로 쓰기.

읽기: 엔트리 수, 압축 해제 총량, 압축비(ZIP 폭탄), '../'·절대 경로를 검사한다.
쓰기: mimetype(무압축)을 맨 앞에, 나머지는 이름순. 타임스탬프·권한·OS 필드를 고정한다.
같은 입력이면 같은 바이트가 나온다(같은 zlib 버전 안에서).
"""
import os
import posixpath
import tempfile
import zipfile

from services.epaper import profile


class UnsafeArchive(ValueError):
    """열면 안 되는 ZIP (경로 탈출, 폭탄, 손상)."""


_FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def _fix_name(info):
    """UTF-8 플래그 없이 CP949로 저장된 이름(zipfile이 cp437로 읽음)을 되살린다."""
    name = info.filename
    if info.flag_bits & 0x800:
        return name
    try:
        raw = name.encode('cp437')
    except UnicodeEncodeError:
        return name
    for enc in ('utf-8', 'cp949'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return name


def _check_name(name):
    if not name or name.startswith(('/', '\\')) or ':' in name.split('/', 1)[0] or '\x00' in name:
        raise UnsafeArchive(f'unsafe entry name: {name!r}')
    norm = posixpath.normpath(name.replace('\\', '/'))
    if norm == '..' or norm.startswith('../'):
        raise UnsafeArchive(f'unsafe entry name: {name!r}')
    return norm


def read_entries(path):
    """ZIP → {정규화된 이름: bytes} (파일 순서는 원본 순서). 폴더 엔트리는 뺀다."""
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise UnsafeArchive(f'not a zip file: {e}') from e
    with zf:
        infos = zf.infolist()
        if len(infos) > profile.MAX_ZIP_ENTRIES:
            raise UnsafeArchive(f'too many entries: {len(infos)}')
        total = 0
        for info in infos:
            total += info.file_size
            if info.file_size > 1024 * 1024 and info.compress_size > 0 \
                    and info.file_size / info.compress_size > profile.MAX_COMPRESSION_RATIO:
                raise UnsafeArchive(f'compression ratio too high: {info.filename!r}')
        if total > profile.MAX_UNCOMPRESSED_TOTAL:
            raise UnsafeArchive(f'uncompressed size too large: {total}')
        entries = {}
        read_total = 0
        for info in infos:
            if info.is_dir():
                continue
            name = _check_name(_fix_name(info))
            try:
                data = zf.read(info)
            except Exception as e:  # 손상된 엔트리, 암호, 지원 안 하는 압축
                raise UnsafeArchive(f'cannot read entry {name!r}: {e}') from e
            read_total += len(data)
            if read_total > profile.MAX_UNCOMPRESSED_TOTAL:
                raise UnsafeArchive('uncompressed size too large')
            if name not in entries:
                entries[name] = data
        return entries


def write_epub(dst_path, entries):
    """{이름: bytes} → 결정적 EPUB. 임시 파일에 쓴 뒤 이름을 바꾼다(반쯤 쓴 파일이 보이지 않게)."""
    names = sorted(n for n in entries if n != 'mimetype')
    if 'META-INF/container.xml' in names:
        names.remove('META-INF/container.xml')
        names.insert(0, 'META-INF/container.xml')
    directory = os.path.dirname(os.path.abspath(dst_path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.epaper-', suffix='.tmp', dir=directory)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, 'w') as zf:
            _write_one(zf, 'mimetype', b'application/epub+zip', zipfile.ZIP_STORED)
            for name in names:
                _write_one(zf, name, entries[name], zipfile.ZIP_DEFLATED)
        os.replace(tmp, dst_path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _write_one(zf, name, data, compress_type):
    info = zipfile.ZipInfo(name, date_time=_FIXED_DATE)
    info.compress_type = compress_type
    info.create_system = 0
    info.external_attr = 0
    zf.writestr(info, data, compress_type=compress_type, compresslevel=9 if compress_type == zipfile.ZIP_DEFLATED else None)
