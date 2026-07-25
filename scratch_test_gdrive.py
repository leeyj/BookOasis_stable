import urllib.request
import urllib.parse
import re
import json

url = "https://drive.google.com/drive/folders/1dNxV48rJE-ujVbNOCbfm1HdthKfaCtyW?usp=sharing"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        print(f"[*] HTML Length: {len(html)}")
        
        # 1. Check title
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            print(f"[*] Page Title: {title_match.group(1)}")
            
        # 2. Search for any IDs or strings
        items_20 = re.findall(r'\["([a-zA-Z0-9_-]{20,})",\["([^"]+)"', html)
        print(f"[*] Pattern 1 (20+ chars) matches count: {len(items_20)}")
        if items_20:
            for m in items_20[:10]:
                print("   - Match:", m)

        # 3. Search for AF_initDataCallback
        callbacks = re.findall(r'AF_initDataCallback\((.*?)\);</script>', html, re.DOTALL)
        print(f"[*] AF_initDataCallback count: {len(callbacks)}")

        # 4. Search for filenames like zip, cbz, txt or folder names
        filenames = re.findall(r'"([^"]+?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml))"', html, re.IGNORECASE)
        print(f"[*] Filename extension regex matches count: {len(filenames)}")
        if filenames:
            print("   - Sample filenames:", filenames[:10])

        # 5. Search for any korean text in script
        korean_matches = re.findall(r'[\uac00-\ud7a3]+', html)
        print(f"[*] Korean words count in HTML: {len(korean_matches)}")
        if korean_matches:
            print("   - Sample Korean words:", korean_matches[:10])

except Exception as e:
    print(f"❌ Error: {e}")
