# -*- coding: utf-8 -*-
"""
plugin_framework – 플러그인 계약(베이스 클래스)의 실제 위치.

plugins/ 는 Docker에서 호스트에 바인드 마운트되는 사용자 데이터 폴더라, 그 안에 둔 파일은
이미지를 올려도 갱신되지 않는다(예전 base.py가 남아 새 계약 메서드가 없다는 오류가 났다).
그래서 계약은 이미지와 함께 갱신되는 이 패키지에 두고, 플러그인이 쓰는 import 경로
`plugins.metadata.base`를 여기로 고정한다. 호스트에 옛 base.py가 있어도 로드되지 않는다.
"""
import importlib
import sys

from plugin_framework import metadata_base

PLUGIN_BASE_MODULE = 'plugins.metadata.base'


def install_plugin_base_alias():
    sys.modules[PLUGIN_BASE_MODULE] = metadata_base
    try:
        importlib.import_module('plugins.metadata').base = metadata_base
    except Exception as e:  # plugins/metadata 폴더가 없어도 alias만으로 import는 된다
        print(f"[PluginFramework] plugins.metadata package attach skipped: {e}")


install_plugin_base_alias()
