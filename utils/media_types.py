# -*- coding: utf-8 -*-
"""
media_types.py – 파일 종류 판별에 쓰는 확장자 목록의 단일 출처.

예전엔 같은 목록이 스캐너·드라이브·진단·라우트 곳곳에 따로 있었고 값도 조금씩 달랐다
(비디오 스캐너엔 wmv/flv가 없는데 진단엔 있는 식). 호환성을 넓게 잡아 합집합으로 통일한다.
모두 소문자, 점 포함 튜플이라 str.endswith()에 그대로 넣을 수 있다.
"""

# 표지/폴더 이미지/압축 안 이미지 페이지
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')

# 오디오북/음악 트랙
AUDIO_EXTENSIONS = ('.mp3', '.m4b', '.m4a', '.flac', '.aac', '.wav', '.ogg', '.opus', '.wma')

# 영상 강좌 에피소드. 브라우저가 바로 못 여는 컨테이너(avi/mov/ts/wmv/flv 등)는
# services/video_scanner.is_browser_compatible()가 걸러 ffmpeg 트랜스코딩으로 재생한다.
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.webm', '.mov', '.m4v', '.ts', '.wmv', '.flv')

# 폴더 메타데이터 파일 (kavita.yaml, series.json, info.xml 등)
METADATA_EXTENSIONS = ('.yaml', '.yml', '.json', '.xml')
