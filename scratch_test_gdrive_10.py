"""
구글 드라이브 HTML 원본 덤프 & 폴더/파일 구분 분석 스크립트
- 상위 폴더(upload): 1NIltJs-PJtn0q7xg-2yDueKP1_5eTQqm
"""
import urllib.request
import re

PARENT_URL = "https://drive.google.com/drive/folders/1NIltJs-PJtn0q7xg-2yDueKP1_5eTQqm?usp=sharing"
CHILD_URL  = "https://drive.google.com/drive/folders/1dNxV48rJE-ujVbNOCbfm1HdthKfaCtyW?usp=sharing"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

def dump_html(label, url, out_path):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[{label}] HTML 저장 완료: {out_path} ({len(html):,} bytes)")
    return html

def analyze(label, html):
    print(f"\n{'='*60}")
    print(f"  [{label}] 분석 시작")
    print(f"{'='*60}")

    # 1. 모든 aria-label 수집
    aria_all = re.findall(r'aria-label="([^"]+)"', html)
    print(f"\n[1] 전체 aria-label 개수: {len(aria_all)}")

    # 2. ssk 속성 패턴 수집 (ID 후보 포함)
    ssk_all = re.findall(r'ssk="([^"]+)"', html)
    ssk_single = re.findall(r"ssk='([^']+)'", html)
    print(f"\n[2] ssk 속성 개수: 큰따옴표={len(ssk_all)}, 작은따옴표={len(ssk_single)}")
    for s in (ssk_all + ssk_single)[:10]:
        print(f"   ssk 원본: {s}")

    # 3. data-id, data-entryid 패턴 수집
    dataid_all = re.findall(r'data-id="([^"]+)"', html)
    print(f"\n[3] data-id 속성 개수: {len(dataid_all)}")
    for d in dataid_all[:10]:
        print(f"   data-id: {d}")

    # 4. 특정 ID (1dNxV48r...)가 HTML 어디에 나오는지 검색
    target_id = "1dNxV48rJE"
    occurrences = [(m.start(), html[max(0,m.start()-80):m.start()+120]) for m in re.finditer(target_id, html)]
    print(f"\n[4] '{target_id}' ID 등장 횟수: {len(occurrences)}")
    for i, (pos, ctx) in enumerate(occurrences[:5]):
        print(f"   --- 등장#{i+1} 위치={pos} ---")
        print(f"   ...{repr(ctx)}...")

    # 5. 전체 ID 길이가 28~40자인 패턴 수집 (드라이브 ID는 33자)
    long_ids = re.findall(r'["\'\s]([a-zA-Z0-9_-]{28,40})["\'\s/]', html)
    unique_ids = list(dict.fromkeys(long_ids))
    print(f"\n[5] 긴 ID(28~40자) 후보 개수(unique): {len(unique_ids)}")
    for i in unique_ids[:15]:
        print(f"   ID: {i}")

    # 6. JSON 형식 배열에서 [id, name, ...] 패턴 추출
    json_arr = re.findall(r'\["([a-zA-Z0-9_-]{20,})","([^"]{1,100})"', html)
    print(f"\n[6] JSON 배열형 [id, name] 패턴 개수: {len(json_arr)}")
    for j in json_arr[:20]:
        print(f"   JSON pair: id={j[0]!r} name={j[1]!r}")


# ── 메인 실행 ──────────────────────────────────────────────
try:
    html_parent = dump_html("PARENT", PARENT_URL, "scratch_gdrive_parent_html.txt")
    analyze("PARENT-FOLDER(upload)", html_parent)
except Exception as e:
    print(f"❌ PARENT 에러: {e}")

print("\n" + "="*60)

try:
    html_child = dump_html("CHILD", CHILD_URL, "scratch_gdrive_child_html.txt")
    analyze("CHILD-FOLDER(내일의요이치)", html_child)
except Exception as e:
    print(f"❌ CHILD 에러: {e}")
