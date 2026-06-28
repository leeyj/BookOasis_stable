# -*- coding: utf-8 -*-
import os
import re
import html
import yaml
import xml.etree.ElementTree as ET

HTML_TAG_RE = re.compile(r'<[^>]*>')

# 한글 초성 목록 및 자음 분기 폴더 판별 정규식 (초성 자음 폴더 예: ㄱ, ㄴ, 아, 자, 타 등)
HANGUL_CONSONANTS = set(['ㄱ','ㄴ','ㄷ','ㄹ','ㅁ','ㅂ','ㅅ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ',
                         '가','나','다','라','마','바','사','아','자','차','카','타','파','하'])

def clean_html_tags(text):
    """HTML 태그 제거 및 특수 엔티티 복원"""
    if not text:
        return ''
    cleaned = HTML_TAG_RE.sub('', text)
    return html.unescape(cleaned).strip()

def is_consonant_folder(foldername):
    """폴더명이 초성 자음 인덱스 폴더인지 판별"""
    foldername = foldername.strip()
    if foldername in HANGUL_CONSONANTS:
        return True
    if re.match(r'^[ㄱ-ㅎ]$', foldername):
        return True
    return False

def parse_info_xml(folder_path, files=None):
    """작품 폴더 내의 info.xml 파일을 읽어 메타데이터를 파싱"""
    xml_path = os.path.join(folder_path, 'info.xml')
    meta = {
        'title': '',
        'series': '',
        'author': '',
        'publisher': '',
        'summary': '',
        'genre': '',
        'tags': '',
        'release_date': ''
    }
    
    has_xml = False
    if files is not None:
        has_xml = any(f.lower() == 'info.xml' for f in files)
    else:
        has_xml = os.path.exists(xml_path)

    if not has_xml:
        return meta

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        def _get_text(tag):
            elem = root.find(tag)
            return elem.text.strip() if elem is not None and elem.text else ''

        meta['title'] = _get_text('Title')
        meta['series'] = _get_text('Series')
        meta['author'] = _get_text('Writer')
        meta['publisher'] = _get_text('Publisher')
        meta['summary'] = _get_text('Summary')
        meta['genre'] = _get_text('Genre')
        meta['tags'] = _get_text('Tags')
        
        year = _get_text('Year')
        month = _get_text('Month').zfill(2) if _get_text('Month') else ''
        day = _get_text('Day').zfill(2) if _get_text('Day') else ''
        
        if year:
            meta['release_date'] = f"{year}-{month or '01'}-{day or '01'}"
            
    except Exception as e:
        print(f"[Scanner] XML 파싱 오류 ({folder_path}): {e}")
        
    meta['summary'] = clean_html_tags(meta['summary'])
    return meta

def parse_kavita_yaml(folder_path, files=None):
    """작품 폴더 내의 kavita.yaml 파일을 읽어 메타데이터를 파싱"""
    yaml_path = os.path.join(folder_path, 'kavita.yaml')
    meta = {
        'author': '',
        'publisher': '',
        'summary': '',
        'score': 0,
        'link': '',
        'genre': '',
        'tags': '',
        'cover_b64_map': {},
        'has_yaml': False
    }
    
    has_yaml = False
    actual_yaml_path = yaml_path
    
    if files is not None:
        for f in files:
            if f.lower() in ('kavita.yaml', 'kavita.yml'):
                has_yaml = True
                actual_yaml_path = os.path.join(folder_path, f)
                break
    else:
        # 파일 목록이 없는 경우 직접 디렉터리를 스캔하여 대소문자 무시 검색
        if os.path.exists(folder_path):
            try:
                for f in os.listdir(folder_path):
                    if f.lower() in ('kavita.yaml', 'kavita.yml'):
                        has_yaml = True
                        actual_yaml_path = os.path.join(folder_path, f)
                        break
            except Exception:
                pass

    if not has_yaml:
        return meta
        
    meta['has_yaml'] = True

    try:
        from yaml import CSafeLoader as SafeLoader
    except ImportError:
        from yaml import SafeLoader
        
    try:
        with open(actual_yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.load(f, Loader=SafeLoader) or {}
        
        def _parse_list_or_str(val):
            if not val:
                return ''
            if isinstance(val, list):
                return ', '.join(str(v).strip() for v in val if v)
            return str(val).strip()

        # 1) meta 노드가 명시되어 있지 않은 경우를 대비해 루트 레벨(data)도 탐색 범위에 포함
        if isinstance(data, dict):
            sources = [data.get('meta', {}), data]
            for src in sources:
                if not isinstance(src, dict): continue
                meta['publisher'] = meta['publisher'] or src.get('Person Publisher') or src.get('publisher') or ''
                meta['author'] = meta['author'] or src.get('Person Writers') or src.get('Writer') or src.get('author') or ''
                meta['summary'] = meta['summary'] or src.get('Summary') or src.get('summary') or ''
                meta['link'] = meta['link'] or src.get('Web Links') or src.get('link') or ''
                meta['tags'] = meta['tags'] or _parse_list_or_str(src.get('Tags') or src.get('tags') or src.get('tag'))
                meta['genre'] = meta['genre'] or _parse_list_or_str(src.get('Genres') or src.get('genre'))
                
            # 2) 만약 search 노드가 존재하면 보강
            search_list = data.get('search', [])
            if search_list and isinstance(search_list, list) and len(search_list) > 0:
                search_item = search_list[0]
                if isinstance(search_item, dict):
                    meta['author'] = meta['author'] or search_item.get('author', '')
                    meta['publisher'] = meta['publisher'] or search_item.get('publisher', '')
                    meta['link'] = meta['link'] or search_item.get('link', '')
                    meta['summary'] = meta['summary'] or search_item.get('description', '')
                    meta['score'] = search_item.get('score', meta['score'])
                    meta['tags'] = meta['tags'] or _parse_list_or_str(search_item.get('tag') or search_item.get('tags') or search_item.get('Tags'))
                    meta['genre'] = meta['genre'] or _parse_list_or_str(search_item.get('genre') or search_item.get('genres') or search_item.get('Genres'))
                
            # 각 파일별 커버 이미지
            files_node = data.get('files', {})
            first_cover_b64 = None
            if isinstance(files_node, dict):
                # 1. 먼저 실제 Base64 데이터가 있는 첫 번째 커버를 찾아서 저장
                for fname, info in files_node.items():
                    if isinstance(info, dict) and 'cover' in info:
                        cover_val = info['cover']
                        if cover_val and isinstance(cover_val, str) and len(cover_val) > 100:
                            if not first_cover_b64:
                                first_cover_b64 = cover_val
                            meta['cover_b64_map'][fname] = cover_val
                            
                # 2. 다시 순회하며 'FIRST' 지시어가 있는 경우 첫 번째 커버로 복제 적용
                for fname, info in files_node.items():
                    if isinstance(info, dict) and 'cover' in info:
                        cover_val = info['cover']
                        if cover_val == 'FIRST' and first_cover_b64:
                            meta['cover_b64_map'][fname] = first_cover_b64
        
        # 가비지 컬렉션을 돕기 위해 임시 파싱 딕셔너리 명시적 소거
        del data
    except Exception as e:
        print(f"[Scanner] YAML 파싱 오류 ({folder_path}): {e}")
        
    meta['summary'] = clean_html_tags(meta['summary'])
    return meta

def parse_series_json(folder_path, files=None):
    """작품 폴더 내의 series.json 파일을 읽어 메타데이터를 파싱 (웹툰용)"""
    import json
    json_path = os.path.join(folder_path, 'series.json')
    meta = {
        'author': '',
        'summary': '',
        'cover_image_url': '',
        'is_webtoon': False
    }
    
    has_json = False
    if files is not None:
        has_json = any(f.lower() == 'series.json' for f in files)
    else:
        has_json = os.path.exists(json_path)

    if not has_json:
        return meta
        
    meta['is_webtoon'] = True

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                meta['author'] = data.get('author', '')
                meta['summary'] = clean_html_tags(data.get('desc', ''))
                meta['cover_image_url'] = data.get('image', '')
    except Exception as e:
        print(f"[Scanner] JSON 파싱 오류 ({folder_path}): {e}")
        
    return meta

def parse_comicinfo_from_cbz(file_path):
    """CBZ/ZIP 파일 내부의 ComicInfo.xml을 파싱하여 메타데이터를 반환합니다.
    Kavita 표준 포맷과 완전 호환됩니다.
    원격 경로나 파일 접근 실패 시 빈 메타데이터를 반환합니다.
    """
    import zipfile
    import io

    meta = {
        'author': '',
        'publisher': '',
        'summary': '',
        'release_date': '',
        'genre': '',
        'tags': '',
        'cover_b64': None,     # ComicInfo.xml 내 표지 이미지 데이터 (있을 경우)
    }

    if not file_path.lower().endswith(('.cbz', '.zip')):
        return meta

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # 대소문자 무시로 ComicInfo.xml 탐색
            names_lower = {n.lower(): n for n in zf.namelist()}
            comicinfo_key = names_lower.get('comicinfo.xml')
            if not comicinfo_key:
                return meta

            xml_data = zf.read(comicinfo_key)
            root = ET.fromstring(xml_data)

            def _get(tag):
                elem = root.find(tag)
                return elem.text.strip() if elem is not None and elem.text else ''

            # 저자: Writer → Penciller → Artist 순으로 탐색
            author = _get('Writer') or _get('Penciller') or _get('Artist')
            meta['author'] = author
            meta['publisher'] = _get('Publisher')
            meta['summary'] = clean_html_tags(_get('Summary'))
            meta['genre'] = _get('Genre')
            meta['tags'] = _get('Tags')

            # 발행일 조합
            year = _get('Year')
            month = _get('Month').zfill(2) if _get('Month') else ''
            day = _get('Day').zfill(2) if _get('Day') else ''
            if year:
                meta['release_date'] = f"{year}-{month or '01'}-{day or '01'}"

    except zipfile.BadZipFile:
        pass  # 손상된 파일은 조용히 스킵
    except Exception as e:
        print(f"[Scanner] ComicInfo.xml 파싱 오류 ({file_path}): {e}")

    return meta
