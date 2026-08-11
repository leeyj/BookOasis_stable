# -*- coding: utf-8 -*-
"""BookOasis 엔진(스캐너/VFS 캐시 갱신 등) 출처 표시용 공용 시그니처.

AGPLv3 5조는 수정본이라도 원 저작물의 저작권/라이선스 고지를 유지하도록 요구한다.
이 상수를 HTTP 응답 헤더, 실행 로그, 소스 헤더 주석에 일관되게 재사용해
고지가 여러 경로에 겹쳐 남도록 하고, 추후 무단 재배포/도용 정황을 판별할 때
근거로 삼을 수 있게 한다.
"""

ENGINE_NAME = 'BookOasis Engine'
ENGINE_SIGNATURE = 'boe-core-a17f3c9'
ENGINE_LICENSE = 'AGPLv3'


def engine_banner_line():
    """스캐너/VFS 등 핵심 엔진 기동 시 로그에 한 번 남기는 출처 배너 문구."""
    return f"{ENGINE_NAME} ({ENGINE_SIGNATURE}) - Licensed under {ENGINE_LICENSE}. See LICENSE for corresponding source rights."
