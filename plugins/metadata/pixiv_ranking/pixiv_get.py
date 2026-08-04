import urllib.request
import urllib.parse
import json
import argparse
import sys
import re

def to_original_url(thumb_url):
    # https://i.pximg.net/c/480x960/img-master/img/2026/08/02/14/53/33/147926455_p0_master1200.jpg
    # ==> https://i.pximg.net/img-original/img/2026/08/02/14/53/33/147926455_p0.jpg
    if not thumb_url:
        return thumb_url
    original = re.sub(r'/c/\d+x\d+/img-master/', '/img-original/', thumb_url)
    original = original.replace('_master1200', '')
    return original
# 사용범
#python pixiv_get.py --mode daily --content all
#python pixiv_get.py --mode weekly --content illust
#python pixiv_get.py --mode monthly --content manga
def get_pixiv_ranking(mode, content):
    # Pixiv는 User-Agent가 없으면 요청을 차단하므로 헤더에 추가해야 합니다.
    url = f"https://www.pixiv.net/ranking.php?mode={mode}&content={content}&format=json"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.pixiv.net/",
        # 1. 비로그인 상태에서는 랭킹 JSON이 정상적으로 내려오지 않는 경우가 많아
        #    로그인 세션 쿠키(PHPSESSID)를 헤더에 실어 보냅니다.
        "Cookie": f"PHPSESSID={PHPSESSID}"
    }
    try:
        # Request 객체 생성
        req = urllib.request.Request(url, headers=headers)
        
        # 데이터 요청 및 응답 읽기
        with urllib.request.urlopen(req) as response:
            result = response.read().decode('utf-8')
            data = json.loads(result)
            
            # 데이터 추출
            contents = data.get('contents', [])
            if not contents:
                print("데이터를 찾을 수 없습니다. mode/content 값을 확인하세요.")
                return
            print(f"[{mode.upper()} / {content.upper()}] 랭킹 목록:")
            for item in contents:
                # 2. 'url' 필드는 썸네일 이미지 URL이므로,
                #    illust_id를 이용해 실제 작품 페이지 URL을 별도로 조립합니다.
                illust_id = item.get('illust_id')
                page_url = f"https://www.pixiv.net/artworks/{illust_id}"
                thumb_url = item.get('url')
                original_url = to_original_url(thumb_url)
                print(f"- {item.get('title')} | 작품: {page_url} | 원본: {original_url}")
            
    except Exception as e:
        print(f"오류 발생: {e}")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pixiv 랭킹 크롤러 (urllib 버전)")
    parser.add_argument("--mode", required=True, help="daily, weekly, monthly, rookie 등")
    parser.add_argument("--content", required=True, help="all, illust, manga, ugoira 등")
    parser.add_argument("--session", required=True, help="로그인 상태의 PHPSESSID 쿠키 값")
    
    args = parser.parse_args()
    PHPSESSID = args.session
    get_pixiv_ranking(args.mode, args.content)
