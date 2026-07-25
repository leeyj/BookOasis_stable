import urllib.request
import re
import json

url = "https://drive.google.com/drive/folders/1dNxV48rJE-ujVbNOCbfm1HdthKfaCtyW?usp=sharing"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='ignore')
    
    # Check AF_initDataCallback contents
    callbacks = re.findall(r'AF_initDataCallback\(\{key:\s*\'([^\']+)\',\s*hash:\s*\'[^\']*\',\s*data:(.*?)\}\);</script>', html, re.DOTALL)
    print(f"Found {len(callbacks)} AF_initDataCallback blocks")
    for key, data_str in callbacks:
        print(f"--- Key: {key} (length: {len(data_str)}) ---")
        # find filenames in data_str
        fnames = re.findall(r'"([^"]+?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml))"', data_str, re.IGNORECASE)
        print(f"   Filenames found: {len(fnames)} -> {set(fnames)}")

    # Test broad regex pattern: ["file_id", "file_name"] or ["file_id", ["file_name"]
    broad_matches = re.findall(r'\["([a-zA-Z0-9_-]{25,})",\s*\[?"([^"\n]+?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml))"', html, re.IGNORECASE)
    print(f"\nBroad matches count: {len(broad_matches)}")
    for fid, fname in broad_matches[:10]:
        print(f"   ID: {fid} | Name: {fname}")
