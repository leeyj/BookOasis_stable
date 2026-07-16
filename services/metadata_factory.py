# -*- coding: utf-8 -*-
import os
import importlib
from plugins.metadata.base import BaseMetadataProvider

class MetadataFactory:
    _instance = None
    _cached_provider = None
    _loaded_provider_name = None

    @classmethod
    def _build_expected_class_names(cls, provider_name):
        names = []
        # Backward-compatible naming (e.g. aladin_new -> Aladin_newMetadataProvider)
        names.append(f"{provider_name.capitalize()}MetadataProvider")
        # CamelCase naming (e.g. aladin_new -> AladinNewMetadataProvider)
        camel = ''.join(part.capitalize() for part in provider_name.split('_') if part)
        if camel:
            names.append(f"{camel}MetadataProvider")
        return names

    @classmethod
    def _find_provider_class(cls, module, provider_name):
        target_class = None
        for expected_class_name in cls._build_expected_class_names(provider_name):
            if hasattr(module, expected_class_name):
                cls_candidate = getattr(module, expected_class_name)
                if isinstance(cls_candidate, type) and issubclass(cls_candidate, BaseMetadataProvider) and cls_candidate is not BaseMetadataProvider:
                    target_class = cls_candidate
                    break

        if target_class:
            return target_class

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseMetadataProvider) and attr is not BaseMetadataProvider:
                return attr
        return None

    @classmethod
    def _import_provider_module_and_class(cls, provider_name):
        candidate_modules = [
            f"plugins.metadata.{provider_name}",
            f"plugins.metadata.{provider_name}.{provider_name}",
            f"plugins.metadata.{provider_name}.provider",
        ]

        last_error = None
        for module_path in candidate_modules:
            try:
                module = importlib.import_module(module_path)
                target_class = cls._find_provider_class(module, provider_name)
                if target_class:
                    return module, target_class
            except Exception as e:
                last_error = e

        if last_error:
            raise last_error
        raise ImportError(f"Provider '{provider_name}' module load failed.")

    @classmethod
    def _load_plugin_ui_bundle(cls, provider_name):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        plugin_dir = os.path.join(base_dir, 'plugins', 'metadata', provider_name)
        if not os.path.isdir(plugin_dir):
            return None

        bundle = {}
        file_map = {
            'html': 'index.html',
            'css': 'style.css',
            'js': 'script.js',
        }

        for key, file_name in file_map.items():
            file_path = os.path.join(plugin_dir, file_name)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        bundle[key] = f.read()
                except Exception as e:
                    print(f"[MetadataFactory] Plugin UI asset load failed ({provider_name}/{file_name}): {e}")

        return bundle if bundle else None

    @classmethod
    def _discover_provider_classes(cls):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        plugins_dir = os.path.join(base_dir, 'plugins', 'metadata')
        discovered = []

        if not os.path.exists(plugins_dir):
            return discovered

        candidate_provider_names = []
        for entry in os.listdir(plugins_dir):
            full_path = os.path.join(plugins_dir, entry)
            if entry in ('__pycache__',) or entry.startswith('__'):
                continue
            if entry == 'base.py':
                continue
            if os.path.isfile(full_path) and entry.endswith('.py'):
                candidate_provider_names.append(entry[:-3])
            elif os.path.isdir(full_path):
                candidate_provider_names.append(entry)

        for provider_name in candidate_provider_names:
            try:
                _, target_class = cls._import_provider_module_and_class(provider_name)
                if target_class:
                    discovered.append((provider_name, target_class))
            except Exception as e:
                print(f"[MetadataFactory] Plugin load failed ({provider_name}): {e}")

        return discovered

    @classmethod
    def get_provider(cls) -> BaseMetadataProvider:
        """
        .env 설정에 지정된 METADATA_PROVIDER를 읽어와 동적으로 플러그인을 로드 및 인스턴스화하여 반환합니다.
        싱글톤 패턴으로 구현하여 매 호출마다 임포트가 새로 일어나지 않도록 합니다.
        """
        # 1. 설정값 읽기
        provider_name = cls._get_provider_name_from_env()
        
        # 2. 캐시된 Provider가 있고, Provider 설정이 바뀌지 않았다면 캐시 반환
        if cls._cached_provider and cls._loaded_provider_name == provider_name:
            return cls._cached_provider

        print(f"[MetadataFactory] Attempting to load metadata provider: '{provider_name}'")
        
        try:
            module, target_class = cls._import_provider_module_and_class(provider_name)

            if not target_class:
                raise ImportError(f"Provider '{provider_name}'에서 BaseMetadataProvider 구현 클래스를 찾을 수 없습니다.")

            # 5. 인스턴스 생성 및 캐시
            cls._cached_provider = target_class()
            cls._loaded_provider_name = provider_name
            print(f"[MetadataFactory] Provider loaded: {target_class.__name__}")
            return cls._cached_provider

        except Exception as e:
            print(f"[MetadataFactory ERROR] Provider '{provider_name}' load failed: {e}")
            # 폴백(Fallback): 기본 알라딘 Provider 로드 시도
            if provider_name != "aladin":
                print("[MetadataFactory] 알라딘 Provider로 폴백을 시도합니다.")
                try:
                    _, fallback_class = cls._import_provider_module_and_class("aladin")
                    cls._cached_provider = fallback_class()
                    cls._loaded_provider_name = "aladin"
                    return cls._cached_provider
                except Exception as ex:
                    print(f"[MetadataFactory FATAL ERROR] Aladin fallback failed: {ex}")
            
            raise e

    @classmethod
    def _get_provider_name_from_env(cls) -> str:
        """.env 설정 파일에서 METADATA_PROVIDER 값을 읽어옵니다. (디폴트는 aladin)"""
        provider_name = "aladin"
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env_path = os.path.join(base_dir, '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('METADATA_PROVIDER='):
                            val = line.split('=', 1)[1].strip()
                            if val:
                                provider_name = val
                                break
        except Exception as e:
            print(f"[MetadataFactory] Failed to read .env, using default: {e}")
        return provider_name.lower()

    @classmethod
    def get_all_searchable_providers(cls):
        """
        plugins/metadata 디렉토리의 모든 파이썬 파일들을 조회하여
        BaseMetadataProvider를 상속받고 is_searchable=True인 플러그인 목록을 
        각 플러그인의 활성화 여부, 설정 명세, 현재 설정값과 함께 반환합니다.
        """
        providers = []
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        plugins_dir = os.path.join(base_dir, 'plugins', 'metadata')
        
        if not os.path.exists(plugins_dir):
            return providers

        # DB 연결하여 모든 설정을 미리 한 번에 로드 (성능)
        import database
        import json
        db_settings = {}
        try:
            conn = database.get_connection('general')
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            db_settings = {row['key']: row['value'] for row in cursor.fetchall()}
            conn.close()
        except Exception as e:
            print(f"[MetadataFactory] DB 설정 사전 load failed: {e}")

        seen_ids = set()
        for provider_name, target_class in cls._discover_provider_classes():
            try:
                if not target_class:
                    continue

                p_id = getattr(target_class, 'id', provider_name)
                if p_id in seen_ids:
                    continue
                seen_ids.add(p_id)

                p_name = getattr(target_class, 'name', provider_name)
                p_searchable = getattr(target_class, 'is_searchable', True)
                p_schema = getattr(target_class, 'config_schema', [])

                if p_searchable:
                    # DB로부터 활성화 상태 획득 (디폴트는 True '1')
                    enabled_key = f"PLUGIN_ENABLED_{p_id}"
                    is_enabled = db_settings.get(enabled_key, '1') == '1'

                    # DB로부터 설정 데이터 획득 (디폴트는 {})
                    config_key = f"PLUGIN_CONFIG_{p_id}"
                    config_val = db_settings.get(config_key, '{}')
                    config_data = {}
                    try:
                        config_data = json.loads(config_val)
                    except Exception:
                        pass

                    provider_item = {
                        'id': p_id,
                        'name': p_name,
                        'enabled': is_enabled,
                        'config_schema': p_schema,
                        'config': config_data
                    }

                    ui_bundle = cls._load_plugin_ui_bundle(p_id)
                    if ui_bundle:
                        provider_item['ui'] = ui_bundle

                    providers.append(provider_item)
            except Exception as e:
                print(f"[MetadataFactory] Plugin load failed ({provider_name}): {e}")
        return providers

    @classmethod
    def get_available_providers(cls):
        """Return all discovered providers (including non-searchable) with enabled/config state."""
        providers = []

        import database
        import json

        db_settings = {}
        try:
            conn = database.get_connection('general')
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            db_settings = {row['key']: row['value'] for row in cursor.fetchall()}
            conn.close()
        except Exception as e:
            print(f"[MetadataFactory] DB 설정 사전 load failed: {e}")

        seen_ids = set()
        for provider_name, target_class in cls._discover_provider_classes():
            try:
                p_id = getattr(target_class, 'id', provider_name)
                if p_id in seen_ids:
                    continue
                seen_ids.add(p_id)

                p_name = getattr(target_class, 'name', provider_name)
                p_searchable = getattr(target_class, 'is_searchable', True)
                p_schema = getattr(target_class, 'config_schema', [])
                p_widget = getattr(target_class, 'dashboard_widget', None)
                p_update_manifest = getattr(target_class, 'update_manifest', None)

                enabled_key = f"PLUGIN_ENABLED_{p_id}"
                is_enabled = db_settings.get(enabled_key, '1') == '1'

                config_key = f"PLUGIN_CONFIG_{p_id}"
                config_val = db_settings.get(config_key, '{}')
                config_data = {}
                try:
                    config_data = json.loads(config_val)
                except Exception:
                    pass

                provider_item = {
                    'id': p_id,
                    'name': p_name,
                    'enabled': is_enabled,
                    'is_searchable': p_searchable,
                    'config_schema': p_schema,
                    'config': config_data,
                    'dashboard_widget': p_widget,
                    'update_manifest': p_update_manifest,
                }

                providers.append(provider_item)
            except Exception as e:
                print(f"[MetadataFactory] Plugin load failed ({provider_name}): {e}")

        return providers

    @classmethod
    def get_provider_by_id(cls, provider_id) -> BaseMetadataProvider:
        """
        특정 provider_id (예: 'aladin')에 부합하는 메타데이터 Provider 인스턴스를 동적으로 로드하여 반환합니다.
        단, 해당 플러그인이 비활성화(PLUGIN_ENABLED_{provider_id} == '0')된 경우 예외를 발생시킵니다.
        """
        if not provider_id:
            provider_id = cls._get_provider_name_from_env()
            
        # 활성화 여부 DB 조회
        import database
        is_enabled = True
        try:
            conn = database.get_connection('general')
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (f"PLUGIN_ENABLED_{provider_id}",))
            row = cursor.fetchone()
            conn.close()
            if row and row['value'] == '0':
                is_enabled = False
        except Exception:
            pass
            
        if not is_enabled:
            print(f"[MetadataFactory] Warning: Requested plugin '{provider_id}'is disabled.")
            raise ValueError(f"'{provider_id}' 플러그인이 비활성화 상태입니다. 환경설정에서 먼저 활성화해 주세요.")
            
        try:
            _, target_class = cls._import_provider_module_and_class(provider_id)

            if target_class:
                return target_class()
        except Exception as e:
            print(f"[MetadataFactory] provider_id '{provider_id}' load failed: {e}")
            
        return cls.get_provider()
