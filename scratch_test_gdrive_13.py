"""
구글 드라이브 API v3 직접 테스트
- API Key가 공유 폴더 접근 권한이 있는지 확인
- 상위/하위 폴더 모두 테스트
"""
import os, json, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv(r"c:\project\media_server\.env")

API_KEY = os.getenv('GDRIVE_API_KEY') or os.getenv('GOOGLE_API_KEY')
print(f"[*] API Key 확인: {API_KEY[:15]}..." if API_KEY else "[!] API Key 없음")

PARENT_ID = "1NIltJs-PJtn0q7xg-2yDueKP1_5eTQqm"  # upload (상위)
CHILD_ID  = "1dNxV48rJE-ujVbNOCbfm1HdthKfaCtyW"  # 내일의 요이치! (하위)

def test_api(label, folder_id):
    print(f"\n{'='*60}")
    print(f"  [{label}] folder_id={folder_id}")
    print(f"{'='*60}")
    
    query = urllib.parse.quote(f"'{folder_id}' in parents and trashed = false")
    fields = urllib.parse.quote("files(id,name,mimeType,size,modifiedTime)")
    url = f"https://www.googleapis.com/drive/v3/files?q={query}&fields={fields}&key={API_KEY}&pageSize=100"
    print(f"[*] 요청 URL: {url[:120]}...")
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8')
            data = json.loads(raw)
            items = data.get('files', [])
            print(f"[*] 응답 아이템 수: {len(items)}개")
            for item in items:
                mime = item.get('mimeType', '')
                name = item.get('name', '')
                iid  = item.get('id', '')
                kind = "📁 폴더" if mime == 'application/vnd.google-apps.folder' else "📄 파일"
                print(f"   {kind}: {name!r} (id={iid}, mime={mime})")
            if not items:
                print(f"[!] 빈 응답 - 전체 raw:\n{raw[:500]}")
    except Exception as e:
        print(f"[❌] 오류: {type(e).__name__}: {e}")

test_api("PARENT(upload 상위폴더)", PARENT_ID)
test_api("CHILD(내일의요이치 파일폴더)", CHILD_ID)
