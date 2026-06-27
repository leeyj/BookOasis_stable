# -*- coding: utf-8 -*-
import os
import json
import urllib.request
import urllib.parse
import hashlib
import database
from plugins.metadata.base import BaseMetadataProvider

class AladinMetadataProvider(BaseMetadataProvider):
    """
    한국 알라딘 OpenAPI를 이용해 도서 정보를 검색하고 적용하는 플러그인입니다.
    다른 메타데이터 플러그인 제작 시 이 클래스를 표준 예시(교재)로 참고하여 구현할 수 있습니다.
    """
    id = "aladin"
    name = "알라딘 도서 검색"
    is_searchable = True
    config_schema = [
        {"key": "ALADIN", "label": "알라딘 OpenAPI TTBKey", "type": "text", "required": True, "description": "국내 도서 정보 메타데이터 및 책 표지를 자동으로 수집하는 데 필요한 알라딘 API 키입니다."}
    ]

    def _get_ttbkey(self, db_type):
        """
        설정 DB(settings 테이블) 알라딘 OpenAPI 인증용 TTBKey를 조회합니다.
        
        Args:
            db_type (str): 데이터베이스 구분 ('general' 또는 'adult')
            
        Returns:
            str: 조회된 TTBKey 문자열
        """
        ttbkey = None
        print(f"[AladinMetadataProvider] TTBKey DB 조회 시작 (db_type: {db_type})")
        try:
            # 1. 플러그인 전용 범용 설정을 먼저 조회
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'PLUGIN_CONFIG_aladin'")
            row = cursor.fetchone()
            if row and row['value']:
                try:
                    config = json.loads(row['value'])
                    ttbkey = config.get('ALADIN')
                    if ttbkey:
                        masked = ttbkey[:4] + "****" if len(ttbkey) > 4 else ttbkey
                        print(f"[AladinMetadataProvider] 1단계: 플러그인 전용 설정에서 TTBKey 획득 성공 ({masked})")
                except Exception as ex:
                    print(f"[AladinMetadataProvider] 플러그인 전용 설정 JSON 파싱 에러: {ex}")
            conn.close()
        except Exception as e:
            print(f"[AladinMetadataProvider] TTBKey DB 조회 중 예외 발생: {e}")
        
        if not ttbkey:
            print("[AladinMetadataProvider] [경고] 모든 경로에서 TTBKey를 획득하는 데 실패했습니다.")
        return ttbkey

    def search(self, db_type, query):
        """
        알라딘 OpenAPI 상품 검색(ItemSearch) API를 호출하여 도서 후보군 목록을 검색합니다.
        
        Args:
            db_type (str): 데이터베이스 타입 ('general' 또는 'adult')
            query (str): 검색할 검색어 (도서 제목, 시리즈 이름 등)
            
        Returns:
            list[dict]: 통일된 메타데이터 규격을 만족하는 도서 목록.
                        결과가 없거나 에러 발생 시 빈 배열 [] 을 반환합니다.
        """
        print(f"[AladinMetadataProvider] search 호출됨 (query: '{query}', db_type: '{db_type}')")
        if not query:
            print("[AladinMetadataProvider] 검색어가 비어 있어 검색을 건너뜁니다.")
            return []
            
        ttbkey = self._get_ttbkey(db_type)
        if not ttbkey:
            print("[AladinMetadataProvider] TTBKey가 설정되어 있지 않아 OpenAPI 요청을 중단합니다.")
            return []

        # 알라딘 ItemSearch API 상세 명세 파라미터 매핑
        url = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx"
        params = {
            'ttbkey': ttbkey,
            'Query': query,
            'QueryType': 'Title',          # 제목 기준 검색
            'MaxResults': 50,             # 반환할 최대 결과 수
            'start': 1,
            'SearchTarget': 'Book',        # 도서 대상
            'output': 'js',                # JSON 형태 응답 요구
            'Version': '20131101'
        }
        
        try:
            query_string = urllib.parse.urlencode(params)
            # 로그 출력용 마스킹 처리된 URL
            masked_ttbkey = ttbkey[:4] + "****" if len(ttbkey) > 4 else ttbkey
            masked_query_string = query_string.replace(ttbkey, masked_ttbkey)
            print(f"[AladinMetadataProvider] API 요청 전송: {url}?{masked_query_string}")
            
            full_url = f"{url}?{query_string}"
            req = urllib.request.Request(
                full_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                print(f"[AladinMetadataProvider] API 응답 수신 성공 (Status: {response.status})")
                res_body = response.read().decode('utf-8')
                print(f"[AladinMetadataProvider] API 응답 원문 바디: {res_body}")
                
                # 알라딘 JSON API 응답 문자열 끝에 세미콜론이 붙어 나오는 비표준 대응
                if res_body.endswith(';'):
                    res_body = res_body[:-1]
                data = json.loads(res_body)
                
                # 에러 응답 구조 확인
                if 'errorCode' in data:
                    print(f"[AladinMetadataProvider] 알라딘 API 에러 반환: [{data.get('errorCode')}] {data.get('errorMessage')}")
                    return []
                    
                items = data.get('item', [])
                print(f"[AladinMetadataProvider] 파싱 성공, 검색된 도서 개수: {len(items)}")
                
                # 공통 규격의 데이터 구조로 매핑 정제
                results = []
                for item in items:
                    results.append({
                        'title': item.get('title'),
                        'author': item.get('author'),
                        'publisher': item.get('publisher'),
                        'pubDate': item.get('pubDate'),
                        'cover': item.get('cover'),
                        'description': item.get('description', ''),
                        'link': item.get('link')
                    })
                return results
        except Exception as e:
            import traceback
            print(f"[AladinMetadataProvider] 알라딘 API 호출 에러 예외 발생: {e}")
            print(f"[AladinMetadataProvider] 예외 트레이스백: {traceback.format_exc()}")
            return []
    def apply(self, db_type, book_id, item_data):
        """
        사용자가 수동 매칭 모달에서 특정 책을 선택했을 때, 
        선택된 알라딘 도서 메타데이터를 로컬 DB에 반영하고 표지 이미지를 저장합니다.
        
        Args:
            db_type (str): 데이터베이스 타입 ('general' 또는 'adult')
            book_id (int): 변경할 도서의 로컬 DB ID (Primary Key)
            item_data (dict): 반영할 도서 메타데이터 (search 결과의 1개 아이템 딕셔너리)
            
        Returns:
            tuple[bool, str]: (성공 여부, 결과 메시지)
        """
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        try:
            # 1. 타겟 도서 정보 유효성 검증
            cursor.execute("SELECT file_path, series_name, library_id FROM books WHERE id = ?", (book_id,))
            book = cursor.fetchone()
            if not book:
                conn.close()
                return False, '대상 도서를 찾을 수 없습니다.'
                
            file_path = book['file_path']
            library_id = book['library_id']
            
            # 2. 표지 이미지(Cover) 다운로드 및 로컬 캐싱 처리
            cover_url = item_data.get('cover')
            cover_filename = None
            
            if cover_url:
                try:
                    # media_server 루트 경로 하위의 covers 폴더 획득
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    covers_dir = os.path.join(base_dir, 'covers', str(library_id))
                    os.makedirs(covers_dir, exist_ok=True)
                    
                    # 파일명 중복을 방지하기 위해 파일 전체 경로의 MD5 해시를 고유 키로 활용
                    filename = os.path.basename(file_path)
                    book_hash = hashlib.md5(filename.encode('utf-8')).hexdigest()
                    cover_filename = f"book_{book_hash}.png"
                    dest_path = os.path.join(covers_dir, cover_filename)
                    
                    # User-Agent를 차단하는 일부 네트워크 환경 대비 헤더 정의
                    req = urllib.request.Request(
                        cover_url, 
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                    )
                    with urllib.request.urlopen(req, timeout=10) as response:
                        img_data = response.read()
                        with open(dest_path, 'wb') as img_f:
                            img_f.write(img_data)
                    print(f"[AladinMetadataProvider] 알라딘 커버 이미지 다운로드 완료: {cover_url} -> {dest_path}")
                    
                    # DB에 저장할 상대적 경로 명칭 구성 ({library_id}/book_{hash}.png)
                    cover_filename = f"{library_id}/{cover_filename}"
                except Exception as e:
                    print(f"[AladinMetadataProvider] 커버 다운로드 실패: {e}")
                    cover_filename = None

            # 3. HTML 태그 제거 및 텍스트 정제
            try:
                from tools.scanner import clean_html_tags
                description = clean_html_tags(item_data.get('description', ''))
            except Exception:
                description = item_data.get('description', '')

            title = item_data.get('title', '')
            author = item_data.get('author', '')
            publisher = item_data.get('publisher', '')
            link = item_data.get('link', '')
            
            # 4. DB 테이블 레코드 갱신 실행 (새 표지가 다운로드되지 않은 경우 기존 표지를 보존)
            cursor.execute("""
                UPDATE books
                SET author = ?,
                    publisher = ?,
                    summary = ?,
                    link = ?,
                    cover_image = COALESCE(NULLIF(?, ''), cover_image),
                    cover_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                author,
                publisher,
                description,
                link,
                cover_filename,
                book_id
            ))
            
            conn.commit()
            conn.close()
            return True, f'"{title}" 메타데이터가 도서 정보에 성공적으로 반영되었습니다.'
        except Exception as e:
            if conn:
                conn.close()
            return False, f'DB 업데이트 오류: {str(e)}'
        
