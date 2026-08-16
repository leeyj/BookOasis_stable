# -*- coding: utf-8 -*-
"""
subtitle_converter.py - SMI/SRT 자막 사이드카를 브라우저 <track>이 지원하는
WebVTT로 변환한다. 외부 의존성 없이 정규식 기반 경량 파서로 처리한다.
"""
import os
import re

# 국내 SMI/SRT 자막은 EUC-KR(CP949)로 저장된 경우가 많아 UTF-8보다 먼저 시도하면
# 깨진 텍스트를 반환할 수 있다. 표준 인코딩부터 순서대로 시도해 가장 먼저 성공하는 것을 사용.
_ENCODING_CANDIDATES = ('utf-8-sig', 'utf-8', 'cp949', 'euc-kr')


def _decode_bytes(raw):
    for enc in _ENCODING_CANDIDATES:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('utf-8', errors='replace')


def _strip_html_tags(text):
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text, flags=re.IGNORECASE)
    return text.strip()


def _ms_to_vtt_time(ms):
    ms = max(0, int(ms))
    hours, rem = divmod(ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


_SMI_SYNC_RE = re.compile(r'<SYNC\s+Start\s*=\s*(\d+)[^>]*>', re.IGNORECASE)


def smi_to_vtt(raw_bytes):
    """SAMI(.smi) 자막을 WebVTT로 변환. 다국어 SMI(KRCC/ENCC 등 여러 Class)의 경우
    첫 번째로 나오는 트랙 하나만 사용한다 - 자막 트랙 선택 UI는 스코프 밖."""
    text = _decode_bytes(raw_bytes)
    matches = list(_SMI_SYNC_RE.finditer(text))
    if not matches:
        return 'WEBVTT\n\n'

    lines = ['WEBVTT', '']
    cue_index = 1
    for i, m in enumerate(matches):
        start_ms = int(m.group(1))
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = _strip_html_tags(text[block_start:block_end])
        if not content or content == '&nbsp;':
            continue
        end_ms = int(matches[i + 1].group(1)) if i + 1 < len(matches) else start_ms + 4000
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        lines.append(str(cue_index))
        lines.append(f"{_ms_to_vtt_time(start_ms)} --> {_ms_to_vtt_time(end_ms)}")
        lines.append(content)
        lines.append('')
        cue_index += 1

    return '\n'.join(lines)


_SRT_TIME_RE = re.compile(
    r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})'
)


def srt_to_vtt(raw_bytes):
    """SubRip(.srt) 자막을 WebVTT로 변환."""
    text = _decode_bytes(raw_bytes).replace('\r\n', '\n').replace('\r', '\n')
    lines = ['WEBVTT', '']
    blocks = re.split(r'\n\s*\n', text.strip())
    for block in blocks:
        block_lines = [l for l in block.split('\n') if l.strip() != '']
        if not block_lines:
            continue

        time_line_idx = next(
            (i for i, l in enumerate(block_lines) if _SRT_TIME_RE.search(l)), None
        )
        if time_line_idx is None:
            continue

        m = _SRT_TIME_RE.search(block_lines[time_line_idx])
        start = f"{m.group(1)}:{m.group(2)}:{m.group(3)}.{m.group(4)}"
        end = f"{m.group(5)}:{m.group(6)}:{m.group(7)}.{m.group(8)}"
        content = _strip_html_tags('\n'.join(block_lines[time_line_idx + 1:]))
        if not content:
            continue

        lines.append(f"{start} --> {end}")
        lines.append(content)
        lines.append('')

    return '\n'.join(lines)


def convert_subtitle_to_vtt(file_path):
    """자막 사이드카 경로를 받아 WebVTT 텍스트를 반환. 미지원 확장자/파일 없음/실패 시 None."""
    if not file_path or not os.path.exists(file_path):
        return None

    ext = os.path.splitext(file_path)[1].lower()
    try:
        with open(file_path, 'rb') as f:
            raw = f.read()
    except Exception:
        return None

    if ext == '.vtt':
        return _decode_bytes(raw)
    if ext == '.smi':
        return smi_to_vtt(raw)
    if ext == '.srt':
        return srt_to_vtt(raw)
    return None
