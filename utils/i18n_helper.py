# -*- coding: utf-8 -*-
import os
import json

# i18n 번역 파일 경로 정의
I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'i18n')

def get_available_languages():
    """static/i18n/ 디렉토리를 스캔하여 감지된 언어 목록 반환"""
    languages = []
    
    if not os.path.exists(I18N_DIR):
        # 디렉토리가 없으면 기본 ko, en 사전 기반으로 리턴
        return [
            {"code": "ko", "name": "한국어"},
            {"code": "en", "name": "English"}
        ]
        
    for filename in os.listdir(I18N_DIR):
        if filename.endswith('.json'):
            lang_code = filename.replace('.json', '')
            file_path = os.path.join(I18N_DIR, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 내부 _meta 객체에서 다국어 라벨명 추출
                    lang_name = data.get('_meta', {}).get('lang_name', lang_code)
                    languages.append({
                        "code": lang_code,
                        "name": lang_name
                    })
            except Exception as e:
                # 파일 파싱 실패 예외 처리
                print(f"[i18n] Failed to load {filename}: {e}")
                
    # 코드가 ko가 최우선으로 오도록 정렬 (혹은 알파벳 정렬)
    languages.sort(key=lambda x: (0 if x['code'] == 'ko' else 1, x['code']))
    return languages
