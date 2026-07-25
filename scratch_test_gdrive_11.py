"""
구글 드라이브 HTML 정밀 분석 - data-id 기반 파일/폴더 구분 확인
핵심: <tr data-id="..." data-target="doc|folder"> 패턴 분석
"""
import re

def analyze_html(label, path):
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()

    print(f"\n{'='*70}")
    print(f"  [{label}] HTML 정밀 분석")
    print(f"{'='*70}")

    # 1. <tr data-id="..." data-target="..."> 패턴 수집 (핵심!)
    tr_items = re.findall(
        r'<tr[^>]+data-selectable[^>]+data-id="([^"]+)"[^>]*data-target="([^"]+)"',
        html
    )
    print(f"\n[A] <tr data-id data-target> 아이템: {len(tr_items)}개")
    for item_id, item_type in tr_items:
        print(f"   type={item_type!r:8s}  id={item_id}")

    # 2. data-target이 tr 반대 순서인 경우
    tr_items2 = re.findall(
        r'<tr[^>]+data-selectable[^>]+data-target="([^"]+)"[^>]*data-id="([^"]+)"',
        html
    )
    print(f"\n[A2] <tr data-target data-id> 역순: {len(tr_items2)}개")
    for item_type, item_id in tr_items2:
        print(f"   type={item_type!r:8s}  id={item_id}")

    # 3. data-id 주변 컨텍스트 100자씩 확인 (전체 패턴 파악)
    data_ids = re.findall(r'data-id="([^"]+)"', html)
    unique_data_ids = list(dict.fromkeys(data_ids))
    print(f"\n[B] 전체 data-id (unique): {len(unique_data_ids)}개")
    for did in unique_data_ids:
        # 드라이브 파일 ID 형식 (1로 시작하는 긴 ID)
        if re.match(r'^1[a-zA-Z0-9_-]{20,}$', did):
            # 주변 컨텍스트에서 data-target 추출
            ctx_matches = re.findall(
                rf'data-id="{re.escape(did)}"[^>]*data-target="([^"]+)"',
                html
            )
            ctx_matches2 = re.findall(
                rf'data-target="([^"]+)"[^>]*data-id="{re.escape(did)}"',
                html
            )
            targets = list(set(ctx_matches + ctx_matches2))
            print(f"   id={did!r:40s}  targets={targets}")

    # 4. <tr>의 aria-label 및 data-id 전체 매핑
    print(f"\n[C] <tr data-id> 전체 발생 위치 및 주변 300자 샘플:")
    for m in re.finditer(r'<tr\s[^>]*data-id="(1[a-zA-Z0-9_-]{20,})"[^>]*>', html):
        item_id = m.group(1)
        ctx = html[m.start():m.start()+400]
        # aria-label 추출
        al = re.search(r'aria-label="([^"]+)"', ctx)
        dt = re.search(r'data-target="([^"]+)"', ctx)
        print(f"   id={item_id}")
        print(f"     data-target: {dt.group(1) if dt else 'N/A'}")
        print(f"     aria-label:  {al.group(1)[:80] if al else 'N/A'}")
        print()

analyze_html("PARENT(upload 상위폴더)", "scratch_gdrive_parent_html.txt")
analyze_html("CHILD(내일의요이치 파일폴더)", "scratch_gdrive_child_html.txt")
