# -*- coding: utf-8 -*-
"""글자 관련 도우미: TXT 인코딩 감지, XML에 못 쓰는 문자 제거, 기기 폰트 범위 검사."""
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


# ---- 기기 폰트 범위 (리디바탕 + KS X 1001 한자 4,888자) ----

def _ksx1001_hanja():
    chars = set()
    for lead in range(0xCA, 0xFE):  # KS X 1001 한자 영역: 0xCAA1 ~ 0xFDFE
        for trail in range(0xA1, 0xFF):
            try:
                ch = bytes((lead, trail)).decode('euc-kr')
            except UnicodeDecodeError:
                continue
            chars.add(ch)
    return frozenset(chars)


_HANJA = None


def _in_font(ch):
    cp = ord(ch)
    if cp < 0x80 or 0xA0 <= cp <= 0xFF:          # 기본 라틴 + Latin-1
        return True
    if 0xAC00 <= cp <= 0xD7A3:                      # 한글 음절 11,172자
        return True
    if 0x3130 <= cp <= 0x318F:                      # 호환용 자모
        return True
    if 0x2000 <= cp <= 0x206F or 0x3000 <= cp <= 0x303F or 0xFF00 <= cp <= 0xFFEF:
        return True                                 # 일반 구두점, CJK 기호, 전각
    global _HANJA
    if _HANJA is None:
        _HANJA = _ksx1001_hanja()
    return ch in _HANJA


def glyph_report(texts, sample_size=20):
    """본문 글자 중 기기 폰트에 없는 글자 집계. texts: 문자열 iterable."""
    total = 0
    missing = {}
    for text in texts:
        for ch in text:
            if ch.isspace():
                continue
            total += 1
            if not _in_font(ch):
                missing[ch] = missing.get(ch, 0) + 1
    missing_count = sum(missing.values())
    top = sorted(missing.items(), key=lambda kv: (-kv[1], kv[0]))[:sample_size]
    return {
        'total_chars': total,
        'missing_chars': missing_count,
        'missing_distinct': len(missing),
        'missing_sample': ''.join(ch for ch, _ in top),
    }
