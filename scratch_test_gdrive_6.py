import urllib.request
import re

url = "https://drive.google.com/drive/folders/1dNxV48rJE-ujVbNOCbfm1HdthKfaCtyW?usp=sharing"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='ignore')

    # Current regex in drive_helper.py
    dom_items = re.findall(r'ssk=\'[^\']*?:([a-zA-Z0-9_-]{25,})[^\']*?\'.*?aria-label="([^"]+?)"', html, re.IGNORECASE | re.DOTALL)
    print(f"Total dom_items count: {len(dom_items)}")
    
    # Check how many are file vs folder vs garbage
    files_found = []
    garbage_found = []
    
    SUPPORTED_EXTENSIONS = ('.zip', '.cbz', '.rar', '.cbr', '.epub', '.pdf', '.txt', '.yaml', '.xml', '.json')

    for raw_fid, raw_name in dom_items:
        fid = raw_fid.split('-')[0]
        ext_match = re.search(r'^(.*?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml|json))', raw_name, re.IGNORECASE)
        if ext_match:
            fname = ext_match.group(1).strip()
            files_found.append((fid, fname))
        else:
            fname = raw_name.split(' Compressed')[0].split(' Shared')[0].split(' 공유됨')[0].split(' 압축')[0].strip()
            garbage_found.append((fid, fname))

    print(f"\nFiles found count ({len(files_found)}):")
    for f in files_found:
        print("  - File:", f)

    print(f"\nGarbage/Folders count ({len(garbage_found)}): Sample 10:")
    for g in garbage_found[:10]:
        print("  - Garbage:", g)
