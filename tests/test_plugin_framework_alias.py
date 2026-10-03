"""plugins.metadata.base 고정: Docker 바인드 마운트에 옛 base.py가 남아 있어도 플러그인은 코어의 계약을 상속한다.

sys.modules를 건드리므로 별도 프로세스에서 확인한다.
"""
import os
import subprocess
import sys
import textwrap

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STALE_BASE = '''
from abc import ABC
class BaseMetadataProvider(ABC):
    id = "base"
'''

STALE_PLUGIN = '''
from plugins.metadata.base import BaseMetadataProvider
class OldplugMetadataProvider(BaseMetadataProvider):
    id = "oldplug"
'''

CHECK = textwrap.dedent('''
    import sys
    sys.path[:0] = [{mount!r}, {repo!r}]
    import plugin_framework
    from plugin_framework.metadata_base import BaseMetadataProvider
    from plugins.metadata.oldplug import OldplugMetadataProvider
    import plugins.metadata.base as alias
    assert alias is plugin_framework.metadata_base, alias.__file__
    assert issubclass(OldplugMetadataProvider, BaseMetadataProvider)
    assert hasattr(OldplugMetadataProvider, 'lookup_music_album')
    print('OK')
''')


def test_stale_mounted_base_is_ignored(tmp_path):
    metadata = tmp_path / 'plugins' / 'metadata'
    metadata.mkdir(parents=True)
    (metadata / '__init__.py').write_text('', encoding='utf-8')
    (metadata / 'base.py').write_text(STALE_BASE, encoding='utf-8')
    (metadata / 'oldplug.py').write_text(STALE_PLUGIN, encoding='utf-8')

    code = CHECK.format(mount=str(tmp_path), repo=REPO_ROOT)
    proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert 'OK' in proc.stdout


def test_shim_reexports_core_base():
    from plugin_framework.metadata_base import BaseMetadataProvider
    from plugins.metadata.base import BaseMetadataProvider as via_shim
    assert via_shim is BaseMetadataProvider
