"""
1. API Key 없이 key='' 로 보내면 어떻게 되는지 확인
2. 공개 공유 폴더 + API Key 없이 접근 가능한 공식 방법 탐색
   - https://www.googleapis.com/drive/v3/files?q=...&key=AIzaSy... (API key 필요)
   - 대안: exportLinks, webContentLink 등
"""
import json, urllib.request, urllib.parse

PARENT_ID = "1NIltJs-PJtn0q7xg-2yDueKP1_5eTQqm"
CHILD_ID  = "1dNxV48rJE-ujVbNOCbfm1HdthKfaCtyW"

# 테스트 1: key 파라미터를 아예 생략하면?
def test_no_key(folder_id, label):
    print(f"\n[테스트: key 없음] {label}")
    query = urllib.parse.quote(f"'{folder_id}' in parents and trashed = false")
    url = f"https://www.googleapis.com/drive/v3/files?q={query}&fields=files(id,name,mimeType)&pageSize=50"
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            print(f"  ✅ 성공: {len(data.get('files',[]))}개")
    except Exception as e:
        print(f"  ❌ {e}")

# 테스트 2: metadata fetch (단일 파일/폴더 정보)
def test_metadata(folder_id, label):
    print(f"\n[테스트: 폴더 메타데이터 조회] {label}")
    url = f"https://www.googleapis.com/drive/v3/files/{folder_id}?fields=id,name,mimeType"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            print(f"  ✅ 성공: {data}")
    except Exception as e:
        print(f"  ❌ {e}")

# 테스트 3: 공개 접근용 export URL (페이지)
def test_export_url(folder_id, label):
    print(f"\n[테스트: export JSON endpoint] {label}")
    # 구글 드라이브 비공개 API 시도 (몇가지 변형)
    urls = [
        f"https://drive.google.com/drive/folders/{folder_id}?hl=ko",
        f"https://www.googleapis.com/drive/v2/files?q=%27{folder_id}%27+in+parents&fields=items(id,title,mimeType)&maxResults=100",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
                print(f"  [{url[:60]}...]: 응답 {len(raw)}bytes - {raw[:200]}")
        except Exception as e:
            print(f"  [{url[:60]}...]: ❌ {e}")

test_no_key(PARENT_ID, "PARENT")
test_no_key(CHILD_ID, "CHILD")
test_metadata(PARENT_ID, "PARENT")
test_metadata(CHILD_ID, "CHILD")
