# -*- coding: utf-8 -*-
"""
build_hanja_readings.py - Unicode Unihan의 한국어 음(kHangul)으로 한자→한글 변환표를 만든다.
결과: static/lib/hanja/readings-v1.json  ({"塔": "탑", ...}) — 음성으로 듣기가 한자를 한국식으로 읽게 할 때 쓴다.

읽기 고르는 규칙: 교육용 표준 음(E 표시)을 우선, 없으면 처음 나온 음.
표준 음은 두음법칙 적용 전 형태(女→녀, 流→류)라서 단어 첫머리 변환은 static/js/tts/tts_core.js에서 한다.

실행: python tools/hanja/build_hanja_readings.py [Unihan.zip 경로]
  경로를 안 주면 https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip 을 받는다.
데이터 라이선스: Unicode License V3 (static/lib/hanja/LICENSE — 재배포 시 함께 둔다)
"""
import io
import json
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, 'static', 'lib', 'hanja')
URL = 'https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip'


# 교육용 표준 음이 실제 쓰임과 다른 글자 (車: 표준 거 → 마차·기차처럼 대부분 차. 자전거는 tts_core.js 예외 단어)
OVERRIDES = {'車': '차'}


def initial_law(syl):
    # 두음법칙 (static/js/tts/tts_core.js의 initialLaw와 같은 규칙)
    n = ord(syl) - 0xAC00
    if not 0 <= n <= 11171:
        return syl
    l, v, t = n // 588, (n % 588) // 28, n % 28
    y = {2, 3, 6, 7, 12, 17, 20}
    if l == 2 and v in y and v not in (2, 3):
        l = 11
    elif l == 5:
        l = 11 if v in y else 2
    return chr(0xAC00 + l * 588 + v * 28 + t)


def pick(value):
    readings = [r.split(':')[0] for r in value.split()]
    sources = [r.split(':')[1] if ':' in r else '' for r in value.split()]
    for hangul, src in zip(readings, sources):
        if 'E' in src:
            return hangul
    # 표준 표시가 없으면 두음법칙 전 형태를 고른다 (狼 "낭 랑" → 랑): 단어 첫머리는 코드에서 다시 낭으로 바꾼다
    for hangul in readings:
        if initial_law(hangul) != hangul and initial_law(hangul) in readings:
            return hangul
    return readings[0]


def main():
    data = open(sys.argv[1], 'rb').read() if len(sys.argv) > 1 else urllib.request.urlopen(URL).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = z.read('Unihan_Readings.txt').decode('utf-8')
    table = {}
    for line in text.splitlines():
        parts = line.split('\t')
        if len(parts) == 3 and parts[1] == 'kHangul':
            table[chr(int(parts[0][2:], 16))] = pick(parts[2])
    table.update(OVERRIDES)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'readings-v1.json')  # /static/lib는 1년 immutable 캐시 — 내용을 바꾸면 파일 이름의 버전도 올린다
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(table.items())), f, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(table)}자 → {out} ({os.path.getsize(out) // 1024}KB)')


if __name__ == '__main__':
    main()
