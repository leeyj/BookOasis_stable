# -*- coding: utf-8 -*-
import os
import importlib
from plugins.metadata.base import BaseMetadataProvider

class MetadataFactory:
    _instance = None
    _cached_provider = None
    _loaded_provider_name = None

    @classmethod
    def get_provider(cls) -> BaseMetadataProvider:
        """
        .env 설정에 지정된 METADATA_PROVIDER를 읽어와 동적으로 플러그인을 로드 및 인스턴스화하여 반환합니다.
        싱글톤 패턴으로 구현하여 매 호출마다 임포트가 새로 일어나지 않도록 합니다.
        """
        # 1. 설정값 읽기
        provider_name = cls._get_provider_name_from_env()
        
        # 2. 캐시된 프로바이더가 있고, 프로바이더 설정이 바뀌지 않았다면 캐시 반환
        if cls._cached_provider and cls._loaded_provider_name == provider_name:
            return cls._cached_provider

        print(f"[MetadataFactory] 메타데이터 프로바이더 로드 시도: '{provider_name}'")
        
        try:
            # 3. plugins.metadata.{provider_name} 모듈 임포트
            module_path = f"plugins.metadata.{provider_name}"
            module = importlib.import_module(module_path)
            
            # 4. 클래스 동적 식별: BaseMetadataProvider를 상속받은 클래스 탐색
            target_class = None
            expected_class_name = f"{provider_name.capitalize()}MetadataProvider"
            
            # 4-1. 예상되는 이름의 클래스가 있는지 먼저 탐색
            if hasattr(module, expected_class_name):
                cls_candidate = getattr(module, expected_class_name)
                if isinstance(cls_candidate, type) and issubclass(cls_candidate, BaseMetadataProvider) and cls_candidate is not BaseMetadataProvider:
                    target_class = cls_candidate
            
            # 4-2. 예상 이름이 없는 경우 모듈 전체에서 상속 클래스 검색
            if not target_class:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseMetadataProvider) and attr is not BaseMetadataProvider:
                        target_class = attr
                        break
            
            if not target_class:
                raise ImportError(f"모듈 {module_path}에서 BaseMetadataProvider를 상속받은 구현 클래스를 찾을 수 없습니다.")

            # 5. 인스턴스 생성 및 캐시
            cls._cached_provider = target_class()
            cls._loaded_provider_name = provider_name
            print(f"[MetadataFactory] 프로바이더 로드 완료: {target_class.__name__}")
            return cls._cached_provider

        except Exception as e:
            print(f"[MetadataFactory ERROR] 프로바이더 '{provider_name}' 로드 실패: {e}")
            # 폴백(Fallback): 기본 알라딘 프로바이더 로드 시도
            if provider_name != "aladin":
                print("[MetadataFactory] 알라딘 프로바이더로 폴백을 시도합니다.")
                try:
                    from plugins.metadata.aladin import AladinMetadataProvider
                    cls._cached_provider = AladinMetadataProvider()
                    cls._loaded_provider_name = "aladin"
                    return cls._cached_provider
                except Exception as ex:
                    print(f"[MetadataFactory FATAL ERROR] 알라딘 폴백 실패: {ex}")
            
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
            print(f"[MetadataFactory] .env 읽기 실패, 기본값 사용: {e}")
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
            print(f"[MetadataFactory] DB 설정 사전 로드 실패: {e}")
            
        for file in os.listdir(plugins_dir):
            if file.endswith('.py') and not file.startswith('__') and file != 'base.py':
                provider_name = file[:-3]
                try:
                    module_path = f"plugins.metadata.{provider_name}"
                    module = importlib.import_module(module_path)
                    
                    target_class = None
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BaseMetadataProvider) and attr is not BaseMetadataProvider:
                            target_class = attr
                            break
                            
                    if target_class:
                        p_id = getattr(target_class, 'id', provider_name)
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
                                
                            providers.append({
                                'id': p_id,
                                'name': p_name,
                                'enabled': is_enabled,
                                'config_schema': p_schema,
                                'config': config_data
                            })
                except Exception as e:
                    print(f"[MetadataFactory] 플러그인 로드 실패 ({provider_name}): {e}")
        return providers

    @classmethod
    def get_provider_by_id(cls, provider_id) -> BaseMetadataProvider:
        """
        특정 provider_id (예: 'aladin')에 부합하는 메타데이터 프로바이더 인스턴스를 동적으로 로드하여 반환합니다.
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
            print(f"[MetadataFactory] 경고: 요청된 플러그인 '{provider_id}'이(가) 비활성화 상태입니다.")
            raise ValueError(f"'{provider_id}' 플러그인이 비활성화 상태입니다. 환경설정에서 먼저 활성화해 주세요.")
            
        try:
            module_path = f"plugins.metadata.{provider_id}"
            module = importlib.import_module(module_path)
            
            target_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseMetadataProvider) and attr is not BaseMetadataProvider:
                    target_class = attr
                    break
                    
            if target_class:
                return target_class()
        except Exception as e:
            print(f"[MetadataFactory] provider_id '{provider_id}' 로드 실패: {e}")
            
        return cls.get_provider()
