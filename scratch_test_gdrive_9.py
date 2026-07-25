import urllib.request
import re

url = "https://drive.google.com/drive/folders/1NIltJs-PJtn0q7xg-2yDueKP1_5eTQqm?usp=sharing"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='ignore')

    # Subfolder aria-label regex test
    # Example: aria-label="내일의 요이치! Shared folder" or aria-label="내일의 요이치! 폴더"
    subfolder_aria = re.findall(r'aria-label="([^"]+?)(?:\s+Shared folder|\s+폴더)"', html, re.IGNORECASE)
    print(f"Subfolder aria matches ({len(subfolder_aria)}):")
    for f in subfolder_aria:
        print("  - Folder:", f)

    # Pair with ssk ID if available
    dom_folders = re.findall(r'ssk=\'[^\']*?:([a-zA-Z0-9_-]{25,})[^\']*?\'.*?aria-label="([^"]+?)(?:\s+Shared folder|\s+폴더)"', html, re.IGNORECASE | re.DOTALL)
    print(f"\nSubfolder DOM pairs ({len(dom_folders)}):")
    for fid, fname in dom_folders:
        print(f"  - ID: {fid} | Folder: {fname}")
