# -*- coding: utf-8 -*-
import json
import re
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import database

class PluginService:
    @staticmethod
    def _parse_version_tokens(version):
        raw = str(version or '').strip()
        if raw.startswith('v') or raw.startswith('V'):
            raw = raw[1:]

        # Accept plain SemVer core (major.minor.patch) with optional pre-release/build suffix.
        match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$', raw)
        if not match:
            return None

        return tuple(int(match.group(i)) for i in (1, 2, 3))

    @classmethod
    def compare_versions(cls, left, right):
        """Return -1 if left < right, 0 if equal, 1 if left > right (SemVer core only)."""
        l = cls._parse_version_tokens(left)
        r = cls._parse_version_tokens(right)
        if l is None or r is None:
            raise ValueError('Invalid version format. Expected SemVer core: MAJOR.MINOR.PATCH')

        if l < r:
            return -1
        if l > r:
            return 1
        return 0

    @classmethod
    def can_update_to_github_version(cls, current_version, github_version):
        """Allow update only when current_version < github_version."""
        cmp_result = cls.compare_versions(current_version, github_version)
        if cmp_result >= 0:
            return False, 'Update blocked: current version is not lower than github version'
        return True, None

    @staticmethod
    def _parse_plugin_version_text(version_text, key_hint='plugin version'):
        """Accepts policy key first, then legacy fallback key names."""
        if not isinstance(version_text, str):
            return None

        safe_key = re.escape(str(key_hint or 'plugin version'))
        patterns = [rf'"{safe_key}"\s*:\s*"([^"]+)"']
        if key_hint != 'plugin version':
            patterns.append(r'"plugin version"\s*:\s*"([^"]+)"')
        patterns.append(r'"plugin_version"\s*:\s*"([^"]+)"')
        for pattern in patterns:
            match = re.search(pattern, version_text)
            if match:
                return match.group(1).strip()
        return None

    @classmethod
    def _fetch_text(cls, url, timeout=8):
        req = Request(url, headers={'User-Agent': 'BookOasis/1.0'})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')

    @classmethod
    def _get_plugin_dir(cls, plugin_id):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, 'plugins', 'metadata', str(plugin_id or '').strip())

    @classmethod
    def _read_local_plugin_version(cls, plugin_id, version_file='VERSION', version_key='plugin version'):
        version_path = os.path.join(cls._get_plugin_dir(plugin_id), version_file)
        if not os.path.isfile(version_path):
            raise ValueError(f'Local VERSION file not found for plugin: {plugin_id}')

        with open(version_path, 'r', encoding='utf-8') as f:
            version_text = f.read()

        local_ver = cls._parse_plugin_version_text(version_text, key_hint=version_key)
        if not local_ver:
            raise ValueError(f'Local plugin VERSION must include "{version_key}"')
        return local_ver

    @classmethod
    def _fetch_remote_plugin_version(cls, raw_base_url, version_file='VERSION', version_key='plugin version'):
        version_url = f"{str(raw_base_url).rstrip('/')}/{version_file}"
        version_text = cls._fetch_text(version_url)
        remote_ver = cls._parse_plugin_version_text(version_text, key_hint=version_key)
        if not remote_ver:
            raise ValueError(f'GitHub plugin VERSION is invalid: missing "{version_key}"')
        return remote_ver

    @classmethod
    def _validate_update_manifest(cls, plugin_id, manifest):
        if not isinstance(manifest, dict):
            raise ValueError('Plugin update manifest is missing')
        if not manifest.get('enabled'):
            raise ValueError('Plugin update is disabled by manifest')
        if manifest.get('provider') != 'github-raw':
            raise ValueError('Only github-raw update provider is supported currently')

        raw_base_url = str(manifest.get('raw_base_url', '')).strip()
        files = manifest.get('files') or []
        version_file = str(manifest.get('version_file', 'VERSION')).strip() or 'VERSION'
        version_key = str(manifest.get('version_key', 'plugin version')).strip() or 'plugin version'

        if not raw_base_url:
            raise ValueError('update_manifest.raw_base_url is required')
        if not isinstance(files, list) or not files:
            raise ValueError('update_manifest.files must be a non-empty list')

        safe_files = []
        for name in files:
            path = str(name or '').strip()
            if not path or '..' in path or path.startswith('/') or path.startswith('\\'):
                raise ValueError(f'Unsafe file path in update manifest: {name}')
            safe_files.append(path)

        if version_file not in safe_files:
            safe_files.append(version_file)

        return {
            'plugin_id': plugin_id,
            'raw_base_url': raw_base_url,
            'files': safe_files,
            'version_file': version_file,
            'version_key': version_key,
        }

    @classmethod
    def sample_update_plugin(cls, plugin_id):
        """Manifest-driven sample updater: plugin declares update behavior internally."""
        plugin_id = str(plugin_id or '').strip()
        if not plugin_id:
            return False, {'error': 'plugin_id is required'}

        from services.metadata_factory import MetadataFactory

        try:
            _, target_class = MetadataFactory._import_provider_module_and_class(plugin_id)
        except Exception as e:
            return False, {'error': f'Plugin load failed: {e}'}

        manifest = getattr(target_class, 'update_manifest', None)
        spec = cls._validate_update_manifest(plugin_id, manifest)

        local_ver = cls._read_local_plugin_version(
            plugin_id,
            version_file=spec['version_file'],
            version_key=spec['version_key'],
        )
        remote_ver = cls._fetch_remote_plugin_version(
            spec['raw_base_url'],
            version_file=spec['version_file'],
            version_key=spec['version_key'],
        )
        can_update, reason = cls.can_update_to_github_version(local_ver, remote_ver)
        if not can_update:
            return False, {
                'error': reason or 'Update blocked',
                'local_version': local_ver,
                'github_version': remote_ver,
            }

        plugin_dir = cls._get_plugin_dir(plugin_id)
        os.makedirs(plugin_dir, exist_ok=True)

        downloaded = {}
        for name in spec['files']:
            file_url = f"{spec['raw_base_url'].rstrip('/')}/{name}"
            try:
                downloaded[name] = cls._fetch_text(file_url)
            except HTTPError as e:
                if e.code == 404:
                    return False, {'error': f'GitHub file not found: {name}'}
                raise

        for name, content in downloaded.items():
            path = os.path.join(plugin_dir, name)
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(content)

        reload_info = {
            'plugin_id': plugin_id,
            'removed_modules': [],
            'removed_count': 0,
            'provider_cache_cleared': False,
            'reload_ok': True,
        }

        try:
            from services.metadata_factory import MetadataFactory
            reload_info = MetadataFactory.hot_reload_plugin(plugin_id)
            reload_info['reload_ok'] = True
        except Exception as e:
            # 업데이트 자체는 성공으로 유지하되, 리로드 실패는 응답에 경고로 포함
            reload_info = {
                'plugin_id': plugin_id,
                'removed_modules': [],
                'removed_count': 0,
                'provider_cache_cleared': False,
                'reload_ok': False,
                'reload_error': str(e),
            }

        return True, {
            'message': f'{plugin_id} plugin updated successfully',
            'plugin_id': plugin_id,
            'local_version': local_ver,
            'github_version': remote_ver,
            'reload': reload_info,
        }

    @staticmethod
    def toggle_plugin_enabled(db_type, plugin_id, enabled_val):
        if not plugin_id:
            return False, 'plugin_id is required'

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        key = f"PLUGIN_ENABLED_{plugin_id}"
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, enabled_val))
        conn.commit()
        conn.close()

        return True, None

    @staticmethod
    def save_plugin_config(db_type, plugin_id, config_data):
        if not plugin_id:
            return False, 'plugin_id is required'

        if not isinstance(config_data, str):
            try:
                config_str = json.dumps(config_data)
            except (TypeError, ValueError):
                return False, 'Invalid config data'
        else:
            config_str = config_data

        try:
            json.loads(config_str)
        except (TypeError, ValueError):
            return False, 'Invalid JSON config'

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        key = f"PLUGIN_CONFIG_{plugin_id}"
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, config_str))
        conn.commit()
        conn.close()

        return True, None
