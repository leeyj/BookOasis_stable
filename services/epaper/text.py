# -*- coding: utf-8 -*-
"""글자 관련 도우미: TXT 인코딩 감지, XML에 못 쓰는 문자 제거, 보이지 않는 문자 정리, 기기 폰트 범위 검사."""
import bisect
import json
import os
import re

# XML 1.0에 쓸 수 없는 제어 문자 (탭·줄바꿈·CR 제외)
_XML_INVALID = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]')


def strip_xml_invalid(text):
    return _XML_INVALID.sub('', text)


def decode_text(data):
    """TXT 바이트 → (str, 감지한 인코딩). BOM → UTF-16(BOM 없음 포함) → UTF-8 → CP949 → CP949(깨진 바이트 대체)."""
    if data.startswith(b'\xef\xbb\xbf'):
        return data[3:].decode('utf-8', errors='replace'), 'utf-8-sig'
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16', errors='replace'), 'utf-16'
    sample = data[:4096]
    if len(sample) >= 4 and sample.count(0) > len(sample) // 4:
        even_zero = sample[0::2].count(0)
        odd_zero = sample[1::2].count(0)
        enc = 'utf-16-le' if odd_zero >= even_zero else 'utf-16-be'
        return data.decode(enc, errors='replace'), enc
    try:
        return data.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        pass
    # BOM 없는 UTF-16 한글은 NUL 바이트가 거의 없다 - 풀었을 때 한글·ASCII가 대부분이면 UTF-16으로 본다
    if len(data) % 2 == 0:
        for enc in ('utf-16-le', 'utf-16-be'):
            try:
                candidate = data.decode(enc)
            except UnicodeDecodeError:
                continue
            if _looks_like_text(candidate):
                return candidate, enc
    try:
        text = data.decode('cp949')
        try:
            data.decode('euc-kr')
            return text, 'euc-kr'
        except UnicodeDecodeError:
            return text, 'cp949'
    except UnicodeDecodeError:
        return data.decode('cp949', errors='replace'), 'cp949-replace'


def _looks_like_text(s, sample=4000):
    s = s[:sample]
    if not s:
        return False
    good = sum(1 for ch in s if ch.isspace() or 0x20 <= ord(ch) < 0x7f or 0xAC00 <= ord(ch) <= 0xD7A3
               or 0x2000 <= ord(ch) <= 0x206F or 0x3000 <= ord(ch) <= 0x303F)
    return good / len(s) > 0.95 and ('\n' in s or len(s) < 200)


# ---- 보이지 않는 문자 정리 (BookOasis 펌웨어 기기 + TXT) ----
# 기기 폰트는 폭 0 문자(ZWSP·LRM·변형 선택자 등)를 빈 글리프로 이미 처리한다. 서버에서 지우는 것은 두 가지뿐이다.
# - RLM·RLE·RLO·RLI: 기기의 양방향 처리가 줄 전체를 오른쪽→왼쪽으로 뒤집는다. 한국어 책에서는 대부분 실수로 들어간 것이라
#   지운다. 단 히브리어·아랍어 등 오른쪽→왼쪽 글자가 있는 문단은 그대로 둔다.
# - IVS(U+E0100-E01EF, 한자 이체자 선택자): BMP 밖이라 기기 폰트에 없어 앞 한자 뒤에 □로 붙는다. 지우면 기본 한자 모양이 된다.
# 다른 글자로 바꾸지는 않는다(서버는 기기에서 고른 폰트를 모르고, 바꾸면 원문이 사라진다).
_RTL_FORCING = re.compile('[%s]' % ''.join(map(chr, (0x200F, 0x202B, 0x202E, 0x2067))))  # RLM RLE RLO RLI
_IVS = re.compile('[%s-%s]' % (chr(0xE0100), chr(0xE01EF)))
_RTL_LETTER = re.compile('[%s]' % ''.join(f'{chr(a)}-{chr(b)}' for a, b in
                                          ((0x0590, 0x08FF), (0xFB1D, 0xFDFF), (0xFE70, 0xFEFC))))  # 히브리·아랍·시리아·타나 등


def has_invisible(s):
    """지울 문자(RLM류·IVS)가 있는가. 대부분의 텍스트는 여기서 끝난다."""
    return bool(s) and bool(_RTL_FORCING.search(s) or _IVS.search(s))


def has_rtl_letters(s):
    return bool(_RTL_LETTER.search(s or ''))


def strip_invisible(s, keep_bidi=False):
    """s에서 IVS를 지우고, keep_bidi가 아니면 RLM·RLE·RLO·RLI도 지운다. (결과, 지운 수)"""
    if not s:
        return s, 0
    out, n = _IVS.subn('', s)
    if not keep_bidi:
        out, m = _RTL_FORCING.subn('', out)
        n += m
    return out, n


def strip_invisible_lines(s):
    """TXT 본문: 줄(문단)마다 정리한다. 오른쪽→왼쪽 글자가 있는 줄은 방향 문자를 남긴다. (결과, 지운 수)"""
    if not has_invisible(s):
        return s, 0
    total = 0
    lines = s.split('\n')
    for i, line in enumerate(lines):
        lines[i], n = strip_invisible(line, keep_bidi=has_rtl_letters(line))
        total += n
    return '\n'.join(lines), total


# ---- 기기 폰트 범위 (BookOasis 펌웨어의 cpfont) ----
# device_fonts.json: 펌웨어 저장소 fonts/device-font-coverage.json 사본. 폰트마다 들어 있는 코드포인트 구간.
# 이 밖의 글자는 기기에서 □(U+FFFD 글리프)로 보인다. 폭 0 문자도 구간에 들어 있어 "없는 글자"로 세지 않는다.
# 기기 폰트를 다시 만들면 이 파일도 바꾼다. 변환 결과는 바뀌지 않으므로 revision은 올리지 않는다.
_FONTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'device_fonts.json')
_IGNORED = frozenset((chr(0xFEFF),))  # BOM: 펌웨어가 걸러 낸다
_fonts = None


def device_fonts():
    """[(이름, 기본 폰트인가, 구간 시작 목록, 구간 끝 목록)]. 기본 폰트가 맨 앞."""
    global _fonts
    if _fonts is None:
        with open(_FONTS_PATH, encoding='utf-8') as f:
            data = json.load(f)
        fonts = []
        for name, info in data['fonts'].items():
            ranges = sorted((int(a), int(b)) for a, b in info['ranges'])
            fonts.append((name, bool(info.get('default')), [a for a, _ in ranges], [b for _, b in ranges]))
        fonts.sort(key=lambda f: not f[1])
        _fonts = fonts
    return _fonts


def _covered(starts, ends, cp):
    i = bisect.bisect_right(starts, cp) - 1
    return i >= 0 and cp <= ends[i]


def _snippet(s, i, width=12):
    a, b = max(0, i - width), min(len(s), i + width + 1)
    return ' '.join(s[a:b].split())


def glyph_report(texts, sample_size=20, location_limit=5):
    """본문 글자 중 기기 폰트에 없는 글자 집계 (폰트별).
    texts: 문자열, 또는 (위치 이름, 문자열) 쌍의 iterable. 맨 위 수치는 기본 폰트 기준이다.
    locations: 기본 폰트에서 □가 되는 첫 몇 곳 (위치 이름, 앞뒤 글자)."""
    fonts = device_fonts()
    total = 0
    counts = {}       # 글자 → 나온 수 (어느 폰트에든 없는 글자만)
    absent = {}       # 글자 → 그 글자가 없는 폰트 번호 tuple
    locations = []
    for item in texts:
        where, s = item if isinstance(item, tuple) else ('', item)
        for i, ch in enumerate(s):
            if ch.isspace() or ch in _IGNORED:
                continue
            total += 1
            miss = absent.get(ch)
            if miss is None:
                cp = ord(ch)
                miss = tuple(n for n, (_, _, starts, ends) in enumerate(fonts) if not _covered(starts, ends, cp))
                absent[ch] = miss
            if not miss:
                continue
            counts[ch] = counts.get(ch, 0) + 1
            if 0 in miss and len(locations) < location_limit and not any(w == where and ch in t for w, t in locations):
                locations.append((where, _snippet(s, i)))
    per_font = {}
    for n, (name, _, _, _) in enumerate(fonts):
        chars = {ch: c for ch, c in counts.items() if n in absent[ch]}
        top = sorted(chars.items(), key=lambda kv: (-kv[1], kv[0]))[:sample_size]
        per_font[name] = {'missing_chars': sum(chars.values()), 'missing_distinct': len(chars),
                          'missing_sample': ''.join(ch for ch, _ in top)}
    default = per_font[fonts[0][0]]
    return {
        'total_chars': total,
        'default_font': fonts[0][0],
        'missing_chars': default['missing_chars'],
        'missing_distinct': default['missing_distinct'],
        'missing_sample': default['missing_sample'],
        'fonts': per_font,
        'locations': [{'where': w, 'text': t} for w, t in locations],
    }
