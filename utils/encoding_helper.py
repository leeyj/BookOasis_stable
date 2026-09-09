# -*- coding: utf-8 -*-
"""
encoding_helper.py - Windows 콘솔/파이프 인코딩(CP949 등) 문제로 로그의 한글이나
이모지가 깨지거나 print()가 UnicodeEncodeError를 내는 것을 막는 공용 헬퍼.

한국어 Windows는 콘솔 기본 코드페이지가 CP949다. CP949는 로그 메시지에 흔히
쓰이는 이모지(🔄 ❌ ✅ 🚫 등)를 표현하지 못해서, print()가 콘솔에 그대로
출력되거나(배치파일 창) 파일로 리다이렉트될 때(서비스 래퍼 등) 예외가 나거나
글자가 깨진다. 로그 파일 자체는 이미 어디서나 encoding='utf-8'로 열고 있으므로
(utils/logger.py 등), 남은 문제는 stdout/stderr뿐이다.

core.py(웹 프로세스), tools/scanner_worker.py, tools/lazy_scanner.py는 각각
별도의 OS 프로세스로 뜨기 때문에(core.py -> subprocess.Popen -> scanner_worker.py
-> subprocess.Popen -> lazy_scanner.py), 한쪽에서 force_utf8_stdio()를 호출해도
다른 쪽 프로세스에는 적용되지 않는다 - 각 진입점 맨 앞에서 개별적으로 호출해야 한다.
"""
import os
import sys


def force_utf8_stdio():
    """현재 프로세스의 stdout/stderr를 UTF-8로 강제 재설정하고, 이후 이 프로세스가
    자식 프로세스를 띄울 때(env=os.environ.copy()) PYTHONUTF8=1이 함께 상속되도록
    환경변수도 같이 설정한다. 여러 번 호출해도 안전하다."""
    os.environ.setdefault('PYTHONUTF8', '1')
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            # 스트림이 이미 닫혔거나(드문 경우) reconfigure를 지원하지 않는 래퍼인 경우 무시.
            pass
