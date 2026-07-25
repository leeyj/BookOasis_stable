import urllib.request
import re

url = "https://drive.google.com/drive/folders/1NIltJs-PJtn0q7xg-2yDueKP1_5eTQqm?usp=sharing"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        print(f"[*] HTML Length: {len(html)}")

        # Check title
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            print(f"[*] Page Title: {title_match.group(1)}")

        # Check aria-labels
        aria_all = re.findall(r'aria-label="([^"]+)"', html)
        print(f"[*] Total aria-labels count: {len(aria_all)}")
        print("[*] Sample aria-labels:")
        for a in aria_all[:20]:
            print("   -", a)

        # Check any folder or subfolder candidates
        folder_matches = re.findall(r'\["([a-zA-Z0-9_-]{20,})",\["([^"]+)"', html)
        print(f"[*] Raw JSON folder/file matches count: {len(folder_matches)}")
        for m in folder_matches[:15]:
            print("   - Match:", m)

except Exception as e:
    print(f"❌ Error: {e}")
