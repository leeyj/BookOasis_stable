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

    # Find pattern: ["25자리_ID", "파일명.zip" ...]
    # Or ["25자리_ID", null, "파일명.zip" ...]
    matches = re.findall(r'\["([a-zA-Z0-9_-]{25,})",\s*(?:\[|null,|"[^"]*",)*\s*"([^"\n]+?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml))"', html, re.IGNORECASE)
    print(f"Matches count: {len(matches)}")
    seen = set()
    for fid, fname in matches:
        if fid not in seen:
            seen.add(fid)
            print(f" - ID: {fid} | Name: {fname}")

    # Let's inspect raw snippet around '01권#199.zip'
    idx = html.find('01권#199.zip')
    if idx != -1:
        print("\n--- Raw snippet around '01권#199.zip' ---")
        print(html[max(0, idx-300):min(len(html), idx+300)])
