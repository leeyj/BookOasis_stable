"""
새 data-id 기반 파서 로컬 검증 테스트
- 저장된 HTML 파일로 파서 로직 검증
"""
import sys
sys.path.insert(0, r"c:\project\media_server")

from utils.drive_helper import fetch_gdrive_folder_files

print("\n" + "="*60)
print("  [테스트 1] PARENT - upload 상위 폴더")
print("="*60)
files = fetch_gdrive_folder_files("https://drive.google.com/drive/folders/1cIw5M-6s2GuW_O8UPc76JnFMl5hROpR8?usp=sharing")
print(f"\n최종 결과: {len(files)}개")
for f in files:
    print(f"  - {f['name']} (id={f['id']}, folder={f['rel_folder']!r})")

print("\n" + "="*60)
print("  [테스트 2] CHILD - 내일의 요이치! 직접 폴더")
print("="*60)
files2 = fetch_gdrive_folder_files("https://drive.google.com/drive/folders/1cIw5M-6s2GuW_O8UPc76JnFMl5hROpR8?usp=sharing")
print(f"\n최종 결과: {len(files2)}개")
for f in files2:
    print(f"  - {f['name']} (id={f['id']}, folder={f['rel_folder']!r})")
