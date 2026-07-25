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

    SUPPORTED_EXTENSIONS = ('.zip', '.cbz', '.rar', '.cbr', '.epub', '.pdf', '.txt', '.yaml', '.xml', '.json')

    files_result = []
    seen_filenames = set()

    # 1. Direct aria-label matching for book/meta files
    aria_matches = re.findall(r'aria-label="([^"]+?\.(?:zip|cbz|rar|cbr|epub|pdf|txt|yaml|xml|json))(?:[^"]*)"', html, re.IGNORECASE)
    print(f"Direct aria-label book matches count: {len(aria_matches)}")
    
    for raw_fname in aria_matches:
        # Trim description text (e.g. "01권#199.zip Compressed archive Shared" -> "01권#199.zip")
        fname = raw_fname.split(' Compressed')[0].split(' Shared')[0].split(' 공유됨')[0].split(' 압축')[0].strip()
        
        if fname.lower() not in seen_filenames:
            seen_filenames.add(fname.lower())
            files_result.append(fname)

    print(f"\nFinal extracted unique books ({len(files_result)}):")
    for f in sorted(files_result):
        print("  - Book:", f)
