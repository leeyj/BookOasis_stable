# -*- coding: utf-8 -*-
"""e-paper 리더용 변환기 (독립 모듈).

코어는 이 패키지를 services/epaper_service.py 한 곳에서만 부른다. 이 패키지는 DB·설정·Flask를 모른다
(파일 경로를 받아 파일을 쓰고 보고서 dict를 돌려줄 뿐이다).
"""
from services.epaper.epub import UnsupportedEpub, optimize_epub
from services.epaper.images import to_feed_jpeg
from services.epaper.profile import CONVERTER_REVISION, DEFAULT_PROFILE, PROFILES, TXT_PROFILE_ID, Profile
from services.epaper.txt import convert_txt
from services.epaper.zipio import UnsafeArchive

__all__ = ['CONVERTER_REVISION', 'DEFAULT_PROFILE', 'PROFILES', 'Profile', 'TXT_PROFILE_ID', 'UnsafeArchive', 'UnsupportedEpub', 'convert', 'convert_txt',
           'optimize_epub', 'to_feed_jpeg']


def convert(src_path, dst_path, source_format, title='', author='', profile=None):
    """source_format: 'epub' | 'txt'. profile(Profile)을 안 주면 DEFAULT_PROFILE. 보고서 dict를 돌려준다.
    TXT는 profile과 상관없이 늘 같은 결과다(표식 TXT_PROFILE_ID)."""
    fmt = str(source_format or '').lower()
    if fmt == 'epub':
        return optimize_epub(src_path, dst_path, profile)
    if fmt in ('txt', 'text'):
        return convert_txt(src_path, dst_path, title=title, author=author)
    raise UnsupportedEpub(f'unsupported format: {source_format}')
