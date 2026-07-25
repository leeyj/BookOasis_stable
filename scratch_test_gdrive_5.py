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

    print("=== HTML Parsing Test ===")
    
    # 1. HTML aria-label pattern: aria-label="FILENAME ..."
    # Example: aria-label="01권#199.zip Compressed archive Shared"
    aria_matches = re.findall(r'aria-label="([^"]+?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml))(?:[^"]*)"', html, re.IGNORECASE)
    print(f"1. Aria label matches count: {len(aria_matches)}")
    for name in set(aria_matches):
        print(f"   - {name}")

    # 2. Extract file ID & name pairs using DOM snippet regex
    # Pattern: ssk='[^\']*?:([a-zA-Z0-9_-]{25,})[^\']*?'.*?aria-label="([^"]+?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml))
    dom_pairs = re.findall(r'ssk=\'[^\']*?:([a-zA-Z0-9_-]{25,})[^\']*?\'.*?aria-label="([^"]+?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml))', html, re.IGNORECASE | re.DOTALL)
    print(f"\n2. DOM pairs count: {len(dom_pairs)}")
    for fid, fname in set(dom_pairs):
        print(f"   - ID: {fid} | Name: {fname}")
