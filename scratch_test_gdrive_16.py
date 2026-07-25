"""
새 구글 드라이브 URL 테스트
https://drive.google.com/drive/folders/1cIw5M-6s2GuW_O8UPc76JnFMl5hROpR8?usp=sharing
"""
import sys
sys.path.insert(0, r"c:\project\media_server")

from utils.drive_helper import fetch_gdrive_folder_files

TEST_URL = "https://drive.google.com/drive/folders/1hBSQZirNwlBj4R5fBIrPT0npuRR4wm39"

print("=" * 60)
print("  파서 전체 흐름 테스트")
print("=" * 60)
files = fetch_gdrive_folder_files(TEST_URL)
print(f"\n최종 결과: {len(files)}개")
for f in files:
    print(f"  - {f['name']} (id={f['id']}, folder={f['rel_folder']!r})")
