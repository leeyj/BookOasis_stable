import requests
import time
API_KEY = "AIzaSyCk_orpowSYRTRvuSBlRYWco8RUCSpow6w" # AIzaSy...
ROOT_FOLDER_ID = "1cIw5M-6s2GuW_O8UPc76JnFMl5hROpR8"

from concurrent.futures import ThreadPoolExecutor

def fetch_folder_contents(folder_id):
    """단일 폴더 내부 항목을 조회하는 전용 함수"""
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{folder_id}' in parents and trashed = false",
        'fields': "files(id, name, mimeType)",
        'key': API_KEY,
        'supportsAllDrives': 'true',
        'includeItemsFromAllDrives': 'true',
        'pageSize': 1000
    }
    try:
        res = requests.get(url, params=params).json()
        return res.get('files', [])
    except Exception as e:
        print(f"⚠️ 요청 에러 ({folder_id}): {e}")
        return []

def scan_directory_parallel(folder_id, current_path=""):
    # 1. 현재 폴더의 하위 항목 조회
    items = fetch_folder_contents(folder_id)
    
    all_results = []
    sub_folders = []

    for item in items:
        name = item['name']
        item_id = item['id']
        is_folder = (item['mimeType'] == 'application/vnd.google-apps.folder')
        path = f"{current_path}/{name}"

        result_entry = {
            'id': item_id,
            'name': name,
            'path': path,
            'is_folder': is_folder
        }
        all_results.append(result_entry)

        if is_folder:
            sub_folders.append((item_id, path))

    # 2. 하위 폴더들이 발견되면 병렬(ThreadPool)로 동시 탐색 ⚡
    if sub_folders:
        # max_workers=10 -> 동시에 10개 폴더씩 concurrent하게 조회
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(scan_directory_parallel, sub_id, sub_path)
                for sub_id, sub_path in sub_folders
            ]
            for future in futures:
                all_results.extend(future.result())

    return all_results

# --- 실행 ---
if __name__ == "__main__":
    start_time = time.time()
    print("🚀 초고속 병렬 드라이브 스캔 시작...\n")
    
    structure = scan_directory_parallel(ROOT_FOLDER_ID)
    
    elapsed = time.time() - start_time
    print("=" * 60)
    print(f"⚡ 스캔 완료! (소요시간: {elapsed:.2f}초, 총 {len(structure)}개 항목 발견)")
    print("=" * 60)

    for item in structure:
        icon = "📁" if item['is_folder'] else "📄"
        print(f"{icon} {item['path']} (ID: {item['id']})")