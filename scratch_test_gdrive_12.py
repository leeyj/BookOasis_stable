"""
구글 드라이브 HTML - <tr> 블록 전체 파싱
data-id="..." 를 가진 <tr> 전체 블록(최대 2000자)을 뽑아서
그 안에서 파일명/폴더명/타입 구분자를 찾는 분석 스크립트
"""
import re

def get_tr_blocks(html):
    """data-id를 가진 <tr> 전체 블록 추출 (다음 <tr data까지)"""
    blocks = []
    for m in re.finditer(r'(<tr\s[^>]*data-id="(1[a-zA-Z0-9_-]{20,})"[^>]*>)', html):
        start = m.start()
        end_match = re.search(r'</tr>', html[start:])
        end = start + (end_match.end() if end_match else 2000)
        # 너무 길면 3000자까지만
        block_html = html[start:min(end, start+3000)]
        blocks.append({
            'id': m.group(2),
            'html': block_html
        })
    return blocks


def analyze_tr_blocks(label, path):
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()

    blocks = get_tr_blocks(html)
    print(f"\n{'='*70}")
    print(f"  [{label}] <tr data-id> 블록 상세 분석: {len(blocks)}개")
    print(f"{'='*70}")

    for b in blocks:
        item_id = b['id']
        block = b['html']

        # data-target 추출
        dt = re.search(r'data-target="([^"]+)"', block)
        # aria-label 전체 수집
        aria_labels = re.findall(r'aria-label="([^"]+)"', block)
        # jsname 수집
        jsnames = re.findall(r'jsname="([^"]+)"', block)
        # class 중 아이콘 힌트 (drive-viewer-share-items 등)
        icon_hints = re.findall(r'class="([^"]*(?:icon|Icon|folder|Folder|file|File)[^"]*)"', block)
        # <img> src 또는 data-src
        img_srcs = re.findall(r'(?:src|data-src)="([^"]+(?:folder|file|icon)[^"]*)"', block, re.IGNORECASE)
        # 텍스트 노드에서 파일명 후보 (한글 포함)
        text_candidates = re.findall(r'>([^<]{2,60}(?:\.zip|\.cbz|\.epub|\.pdf|\.yaml|\.xml|[가-힣]{2,})[^<]{0,20})<', block)

        print(f"\n  ── ID: {item_id}")
        print(f"     data-target : {dt.group(1) if dt else 'N/A'}")
        print(f"     aria-labels : {aria_labels[:5]}")
        print(f"     텍스트후보  : {text_candidates[:5]}")
        print(f"     icon_hints  : {icon_hints[:3]}")


analyze_tr_blocks("PARENT(upload 상위폴더)", "scratch_gdrive_parent_html.txt")
analyze_tr_blocks("CHILD(내일의요이치 파일폴더)", "scratch_gdrive_child_html.txt")
