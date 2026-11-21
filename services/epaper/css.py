# -*- coding: utf-8 -*-
"""CSS 정리 (프로필 v1): 허용 목록에 있는 속성과 단순한 선택자만 남긴다.

빠지는 것: @font-face·@media·@import 등 모든 at-rule, 폰트 지정, 고정 크기(px·pt 등) 글자 크기,
여백(margin·padding), float·position·크기·색·배경·테두리, 복잡한 선택자(자손·자식·속성·가상 클래스).
남는 것: 정렬, 굵게·기울임·밑줄, 상대 글자 크기(em·%·키워드), em/% 들여쓰기, 위·아래 첨자, 쪽 나눔, display none/block/inline.
결과는 고정된 형식으로 다시 쓴다(결정적).
"""
import re

_COMMENT = re.compile(r'/\*.*?\*/', re.S)
_SIMPLE_SELECTOR = re.compile(r'^(?:[a-zA-Z][a-zA-Z0-9-]*|\*)?(?:\.[A-Za-z_][\w-]*)?$')
_RELATIVE_LENGTH = re.compile(r'^-?(?:\d+|\d*\.\d+)(?:em|rem|%)$|^0$')
_FONT_SIZE_KEYWORDS = {'smaller', 'larger', 'small', 'medium', 'large', 'x-small', 'x-large', 'inherit'}

_ALLOWED = {
    'text-align': lambda v: v in ('left', 'right', 'center', 'justify', 'start', 'end'),
    'font-weight': lambda v: v in ('bold', 'bolder', 'normal', 'lighter') or re.fullmatch(r'[1-9]00', v) is not None,
    'font-style': lambda v: v in ('italic', 'oblique', 'normal'),
    'text-decoration': lambda v: all(p in ('underline', 'line-through', 'overline', 'none') for p in v.split()),
    'font-size': lambda v: v in _FONT_SIZE_KEYWORDS or _RELATIVE_LENGTH.match(v) is not None,
    'text-indent': lambda v: _RELATIVE_LENGTH.match(v) is not None,
    'vertical-align': lambda v: v in ('super', 'sub', 'baseline'),
    'display': lambda v: v in ('none', 'block', 'inline'),
    'page-break-before': lambda v: v in ('always', 'avoid', 'auto'),
    'page-break-after': lambda v: v in ('always', 'avoid', 'auto'),
    'break-before': lambda v: v in ('page', 'avoid', 'auto'),
    'break-after': lambda v: v in ('page', 'avoid', 'auto'),
}


def filter_declarations(text):
    """'a: b; c: d' → 허용된 선언만 [(속성, 값)] (원래 순서, 같은 속성은 마지막 값)."""
    result = {}
    order = []
    for part in text.split(';'):
        if ':' not in part:
            continue
        prop, value = part.split(':', 1)
        prop = prop.strip().lower()
        value = re.sub(r'\s*!important\s*$', '', value.strip(), flags=re.I).strip()
        value_l = value.lower()
        check = _ALLOWED.get(prop)
        if not check or not value_l or not check(value_l):
            continue
        if prop not in result:
            order.append(prop)
        result[prop] = value_l
    return [(p, result[p]) for p in order]


def filter_inline_style(text):
    """style 속성 값 → 정리된 값 ('' 이면 속성을 지운다)."""
    decls = filter_declarations(_COMMENT.sub('', text or ''))
    return '; '.join(f'{p}: {v}' for p, v in decls)


def _skip_block(css, i):
    """css[i] == '{' 일 때 짝이 맞는 '}' 다음 위치."""
    depth = 0
    n = len(css)
    while i < n:
        ch = css[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        elif ch in '"\'':
            end = css.find(ch, i + 1)
            i = n if end < 0 else end
        i += 1
    return n


def filter_stylesheet(css):
    """스타일시트 문자열 → 정리된 스타일시트 문자열."""
    css = _COMMENT.sub('', css or '').replace('\r', '')
    out = []
    i, n = 0, len(css)
    while i < n:
        brace = css.find('{', i)
        semi = css.find(';', i)
        head_end = brace if brace >= 0 else n
        head = css[i:head_end].strip()
        if head.startswith('@') and (semi >= 0 and (brace < 0 or semi < brace)):
            i = semi + 1          # @import, @charset, @namespace ...;
            continue
        if brace < 0:
            break
        block_end = _skip_block(css, brace)
        if head.startswith('@'):
            i = block_end         # @font-face, @media, @page ... 전부 버린다
            continue
        body = css[brace + 1:block_end - 1]
        i = block_end
        selectors = []
        for sel in head.split(','):
            sel = ' '.join(sel.split())
            if sel and _SIMPLE_SELECTOR.match(sel):
                selectors.append(sel)
        if not selectors:
            continue
        decls = filter_declarations(body)
        if not decls:
            continue
        out.append(f"{', '.join(selectors)} {{ {'; '.join(f'{p}: {v}' for p, v in decls)}; }}")
    return '\n'.join(out) + ('\n' if out else '')
