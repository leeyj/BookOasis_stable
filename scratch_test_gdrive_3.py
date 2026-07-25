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
    
    callbacks = re.findall(r'AF_initDataCallback\(\{key:\s*\'[^\']+\',\s*hash:\s*\'[^\']*\',\s*data:(.*?)\}\);</script>', html, re.DOTALL)
    for data_str in callbacks:
        if '.zip' in data_str or '.cbz' in data_str:
            try:
                data = json.loads(data_str)
                # Inspect data structure recursively
                found = []
                def walk(obj):
                    if isinstance(obj, list):
                        # Google Drive item tuple pattern: [id, name, mimeType, ...] or [id, [name, ...]]
                        if len(obj) >= 2 and isinstance(obj[0], str) and re.match(r'^[a-zA-Z0-9_-]{25,}$', obj[0]):
                            fid = obj[0]
                            name = None
                            if isinstance(obj[1], str):
                                name = obj[1]
                            elif isinstance(obj[1], list) and len(obj[1]) > 0 and isinstance(obj[1][0], str):
                                name = obj[1][0]
                            if name:
                                found.append((fid, name))
                        for item in obj:
                            walk(item)
                    elif isinstance(obj, dict):
                        for k, v in obj.items():
                            walk(v)
                walk(data)
                print(f"Extracted {len(found)} item pairs via JSON walk:")
                for fid, fn in found[:20]:
                    print(f"   ID: {fid} | Name: {fn}")
            except Exception as e:
                print(f"JSON parse error: {e}")
