# -*- coding: utf-8 -*-
"""
rss_epub_news.py - RSS 피드를 하루 한 번 수집해 EPUB 한 권으로 만들고, 라이브러리 폴더에 저장한 뒤
일반 스캔 큐(scanner_queue)로 등록시키는 샘플 플러그인.

설계 메모
- 플러그인의 서버측 HTTP 요청에는 "외부 도메인" 화이트리스트가 적용되지 않는다(그건 브라우저 웹뷰
  프록시 전용). 대신 사용자가 피드 URL을 직접 입력하므로 services/ssrf_guard.py의
  fetch_public_url_with_redirect_revalidation(사설/루프백 IP + 리다이렉트 재검증)을 쓴다.
- 본문은 피드가 주는 만큼만 쓴다: content:encoded(전문) > description(요약) + 원문 링크.
  구글 뉴스 RSS처럼 제목/링크만 주는 피드는 "헤드라인 브리핑"이 된다. 기사 원문 스크래핑은 하지 않는다.
- 외부 HTML은 허용 태그 화이트리스트로 정제(script/style/iframe/이벤트 속성 제거)해 XHTML로 만든다.
- 저장 위치: <라이브러리 첫 로컬 루트>/<피드이름>/<피드이름>_<YYYY-MM-DD>.epub (폴더 = 시리즈).
  MERGE_FEEDS를 켜면 모든 피드를 하루 한 권('오늘의 브리핑')으로 합친다(목차에 [피드이름] 접두).

주의(플러그인 개발자용)
- 이 플러그인은 코어 내부(scanner_queue, CategoryRepository, ssrf_guard)를 직접 import한다.
  공식 플러그인 계약이 아니라 샘플 편의이므로 코어 버전 변경에 영향받을 수 있다.
- settings.html이 있으면 config_schema 필드는 자동 렌더링되지 않는다: 입력창을 settings.html에 직접
  name=KEY로 넣어야 하고, 저장은 input/select만 수집한다(textarea 불가).
- 스케줄: start_background_service()가 데몬 스레드를 띄우고, 워커가 여러 개여도 하루 한 번만
  실행되도록 날짜별 lock 파일을 O_EXCL로 선점한다.
"""
import html
import json
import os
import re
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

from flask import session

from plugins.metadata.base import BaseMetadataProvider

FEED_MAX_BYTES = 5 * 1024 * 1024
IMAGE_MAX_BYTES = 2 * 1024 * 1024
MAX_IMAGES_PER_BOOK = 150
FEED_USER_AGENT = "BookOasis-RSS/1.0 (feed reader)"
IMAGE_TYPES = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
    "image/gif": "gif", "image/webp": "webp",
}
STATUS_KEY = "PLUGIN_rss_epub_news_STATUS"

_NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}
_UNSAFE_NAME_RE = re.compile(r'[\\/\x00-\x1f:*?"<>|]')


# ----------------------------------------------------------------------
# 순수 함수: 파싱 / 정제 / EPUB 생성 (Flask/DB 없이 단독 테스트 가능)
# ----------------------------------------------------------------------

def safe_name(text, fallback="news"):
    name = _UNSAFE_NAME_RE.sub("_", str(text or "")).strip(" .")
    return (name or fallback)[:80]


def _text(el, path):
    found = el.find(path, _NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def _fmt_date(raw):
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw.strip()


def parse_feed(xml_bytes):
    """RSS 2.0 / Atom 피드를 {'title', 'items': [{title, link, date, author, body_html, image}]}로 파싱.
    RSS가 아닌 응답(HTML 홈페이지 등)이면 ValueError."""
    head = xml_bytes[:512].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        raise ValueError("RSS가 아니라 HTML 페이지입니다. 피드 주소(rel=alternate)를 확인하세요.")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"피드 XML 파싱 실패: {e}")

    items = []
    if root.tag.endswith("feed"):  # Atom
        title = _text(root, "atom:title") or _text(root, "{http://www.w3.org/2005/Atom}title")
        for e in root.findall("{http://www.w3.org/2005/Atom}entry"):
            link_el = e.find("{http://www.w3.org/2005/Atom}link")
            body = e.find("{http://www.w3.org/2005/Atom}content")
            summary = e.find("{http://www.w3.org/2005/Atom}summary")
            raw_body = (body.text if body is not None else None) or (summary.text if summary is not None else "") or ""
            items.append({
                "title": (e.findtext("{http://www.w3.org/2005/Atom}title") or "").strip(),
                "link": (link_el.get("href") if link_el is not None else "") or "",
                "date": _fmt_date(e.findtext("{http://www.w3.org/2005/Atom}updated") or ""),
                "author": "",
                "body_html": raw_body,
                "has_full": body is not None,
                "image": "",
            })
    else:  # RSS 2.0
        channel = root.find("channel")
        if channel is None:
            raise ValueError("지원하지 않는 피드 형식입니다.")
        title = (channel.findtext("title") or "").strip()
        for it in channel.findall("item"):
            full = it.find("content:encoded", _NS)
            desc = it.findtext("description") or ""
            media = it.find("media:content", _NS)
            enclosure = it.find("enclosure")
            image = ""
            if media is not None and (media.get("medium") in (None, "image") or "image" in (media.get("type") or "")):
                image = media.get("url") or ""
            elif enclosure is not None and (enclosure.get("type") or "").startswith("image/"):
                image = enclosure.get("url") or ""
            items.append({
                "title": (it.findtext("title") or "").strip(),
                "link": (it.findtext("link") or "").strip(),
                "date": _fmt_date(it.findtext("pubDate") or ""),
                "author": _text(it, "dc:creator") or (it.findtext("author") or "").strip(),
                "body_html": (full.text if full is not None and full.text else desc) or "",
                "has_full": bool(full is not None and full.text),
                "image": image,
            })
    return {"title": title, "items": [i for i in items if i["title"]]}


_ALLOWED_TAGS = {
    "p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "em", "i", "u", "blockquote",
    "ul", "ol", "li", "a", "img", "figure", "figcaption", "hr", "sub", "sup",
}
_DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "noscript", "svg", "form", "head", "title"}
_VOID_TAGS = {"br", "img", "hr"}
_BLOCK_AS_P = {"div", "section", "article", "span", "table", "tr", "td", "th", "tbody", "thead"}


class _Sanitizer(HTMLParser):
    """허용 태그만 남기고 XHTML(self-closing 포함)로 다시 쓴다. img src는 base_url 기준 절대 URL로 변환."""

    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.out = []
        self.stack = []
        self.skip_depth = 0
        self.images = []

    def handle_starttag(self, tag, attrs):
        if self.skip_depth:
            if tag in _DROP_CONTENT_TAGS:
                self.skip_depth += 1
            return
        if tag in _DROP_CONTENT_TAGS:
            self.skip_depth = 1
            return
        if tag in _BLOCK_AS_P:
            tag = "p" if tag in ("div", "section", "article") else None
            if tag is None:
                return
        if tag not in _ALLOWED_TAGS:
            return
        attrd = dict(attrs)
        if tag == "img":
            src = (attrd.get("src") or attrd.get("data-src") or "").strip()
            if not src:
                return
            abs_src = urljoin(self.base_url, src)
            if urlsplit(abs_src).scheme not in ("http", "https"):
                return
            self.images.append(abs_src)
            alt = html.escape(attrd.get("alt") or "", quote=True)
            self.out.append(f'<img src="{html.escape(abs_src, quote=True)}" alt="{alt}"/>')
            return
        if tag == "a":
            href = urljoin(self.base_url, (attrd.get("href") or "").strip())
            if urlsplit(href).scheme not in ("http", "https"):
                self.stack.append("~a")  # 위험한 링크: 태그는 버리고 내용만 남김
                return
            self.out.append(f'<a href="{html.escape(href, quote=True)}">')
            self.stack.append("a")
            return
        if tag in _VOID_TAGS:
            self.out.append(f"<{tag}/>")
            return
        if tag == "p" and "p" in self.stack:  # <p> 안에 <p> 중첩 방지(div→p 변환 포함)
            while self.stack:
                t = self.stack.pop()
                if not t.startswith("~"):
                    self.out.append(f"</{t}>")
                if t == "p":
                    break
        self.out.append(f"<{tag}>")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.skip_depth:
            if tag in _DROP_CONTENT_TAGS:
                self.skip_depth -= 1
            return
        if tag in ("div", "section", "article"):
            tag = "p"
        if tag in _VOID_TAGS or tag not in _ALLOWED_TAGS:
            return
        if tag in self.stack or ("~" + tag) in self.stack:
            while self.stack:
                t = self.stack.pop()
                if not t.startswith("~"):
                    self.out.append(f"</{t}>")
                if t.lstrip("~") == tag:
                    break

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(html.escape(data, quote=False))

    def result(self):
        while self.stack:
            t = self.stack.pop()
            if not t.startswith("~"):
                self.out.append(f"</{t}>")
        return "".join(self.out)


def sanitize_html(raw, base_url=""):
    """외부 HTML 조각 -> 안전한 XHTML 조각 + 포함된 이미지 URL 목록."""
    s = _Sanitizer(base_url)
    try:
        s.feed(raw or "")
        s.close()
    except Exception:
        return html.escape(re.sub(r"<[^>]+>", " ", raw or "")), []
    return s.result(), s.images


_CSS = """body{font-family:serif;line-height:1.7;margin:0 .6em}
h1{font-size:1.3em;margin:.6em 0 .2em}.meta{color:#666;font-size:.85em;margin:0 0 1em}
img{max-width:100%;height:auto}a{color:#1a5fb4}.src{margin-top:1.5em;font-size:.85em}
li{margin:.4em 0}"""


def _xhtml(title, body):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ko">'
            f'<head><meta charset="utf-8"/><title>{html.escape(title)}</title>'
            '<link rel="stylesheet" type="text/css" href="style.css"/></head>'
            f"<body>{body}</body></html>")


def build_epub(dest_path, book_title, chapters, images, lang="ko"):
    """chapters: [{'title','body'(xhtml 조각)}], images: {파일명: (bytes, mime)}. 첫 이미지를 표지로 쓴다."""
    uid = f"urn:uuid:{uuid.uuid4()}"
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    cover_name = next(iter(images), None)

    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="css" href="style.css" media-type="text/css"/>']
    spine, nav_li, ncx_pts = [], [], []
    for i, ch in enumerate(chapters, 1):
        manifest.append(f'<item id="c{i}" href="c{i}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
        t = html.escape(ch["title"])
        nav_li.append(f'<li><a href="c{i}.xhtml">{t}</a></li>')
        ncx_pts.append(f'<navPoint id="n{i}" playOrder="{i}"><navLabel><text>{t}</text></navLabel>'
                       f'<content src="c{i}.xhtml"/></navPoint>')
    for j, (name, (_data, mime)) in enumerate(images.items(), 1):
        prop = ' properties="cover-image"' if name == cover_name else ""
        manifest.append(f'<item id="img{j}" href="images/{name}" media-type="{mime}"{prop}/>')

    opf = ('<?xml version="1.0" encoding="utf-8"?>'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:identifier id="uid">{uid}</dc:identifier><dc:title>{html.escape(book_title)}</dc:title>'
           f'<dc:language>{lang}</dc:language><dc:creator>RSS</dc:creator>'
           f'<meta property="dcterms:modified">{now}</meta></metadata>'
           f'<manifest>{"".join(manifest)}</manifest><spine toc="ncx">{"".join(spine)}</spine></package>')
    nav = _xhtml("목차", f'<nav epub:type="toc"><h1>목차</h1><ol>{"".join(nav_li)}</ol></nav>')
    ncx = ('<?xml version="1.0" encoding="utf-8"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{uid}"/></head><docTitle><text>{html.escape(book_title)}</text></docTitle>'
           f'<navMap>{"".join(ncx_pts)}</navMap></ncx>')
    container = ('<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')

    tmp_path = dest_path + ".tmp"
    with zipfile.ZipFile(tmp_path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", _CSS, compress_type=zipfile.ZIP_DEFLATED)
        for i, ch in enumerate(chapters, 1):
            z.writestr(f"OEBPS/c{i}.xhtml", _xhtml(ch["title"], ch["body"]), compress_type=zipfile.ZIP_DEFLATED)
        for name, (data, _mime) in images.items():
            z.writestr(f"OEBPS/images/{name}", data, compress_type=zipfile.ZIP_STORED)
    os.replace(tmp_path, dest_path)


def _read_capped(resp, limit):
    from services.ssrf_guard import read_capped
    return read_capped(resp, limit)


def fetch_bytes(url, limit):
    """SSRF 가드(사설 IP 차단 + 리다이렉트 재검증)를 거쳐 가져온다. 화이트리스트는 쓰지 않는다."""
    from services.ssrf_guard import fetch_public_url_with_redirect_revalidation
    resp = fetch_public_url_with_redirect_revalidation(url, extra_headers={"User-Agent": FEED_USER_AGENT})
    try:
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")
        return _read_capped(resp, limit), (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    finally:
        resp.close()


def build_book_from_feed(feed, max_items, include_images, fetch=fetch_bytes, state=None, prefix=""):
    """파싱된 피드 -> (chapters, images). fetch는 테스트에서 교체 가능.
    state={'images':{}, 'url_to_name':{}}를 넘기면 여러 피드가 한 권에 합쳐질 때 이미지 번호/캐시를 공유한다.
    prefix는 목차에서 피드를 구분하기 위해 챕터 제목 앞에 붙인다."""
    state = state if state is not None else {"images": {}, "url_to_name": {}}
    images = state["images"]            # 파일명 -> (bytes, mime)
    url_to_name = state["url_to_name"]  # 원본 URL -> 파일명 (실패는 None)

    def _get_image(url):
        if url in url_to_name:
            return url_to_name[url]
        name = None
        if len(images) < MAX_IMAGES_PER_BOOK:
            try:
                data, ctype = fetch(url, IMAGE_MAX_BYTES)
                ext = IMAGE_TYPES.get(ctype)
                if ext and data:
                    name = f"img{len(images) + 1}.{ext}"
                    images[name] = (data, "image/jpeg" if ext == "jpg" else f"image/{ext}")
            except Exception:
                name = None
        url_to_name[url] = name
        return name

    chapters = []
    for item in feed["items"][:max_items]:
        body, imgs = sanitize_html(item["body_html"], item["link"])
        if include_images:
            for u in dict.fromkeys(imgs):
                name = _get_image(u)
                if name:
                    body = body.replace(f'src="{html.escape(u, quote=True)}"', f'src="images/{name}"')
                else:
                    body = re.sub(r'<img src="%s"[^>]*/>' % re.escape(html.escape(u, quote=True)), "", body)
            if not imgs and item["image"]:
                name = _get_image(item["image"])
                if name:
                    body = f'<p><img src="images/{name}" alt=""/></p>' + body
        else:
            body = re.sub(r"<img [^>]*/>", "", body)
        meta = " · ".join(x for x in (item["date"], item["author"]) if x)
        link = item["link"]
        src = (f'<p class="src"><a href="{html.escape(link, quote=True)}">원문 보기</a></p>' if link else "")
        chapters.append({
            "title": f"{prefix}{item['title']}",
            "body": f'<h1>{html.escape(item["title"])}</h1><p class="meta">{html.escape(meta)}</p>{body}{src}',
        })
    return chapters, (images if include_images else {})


def run_feed(feed_name, url, dest_dir, max_items, include_images, force=False, fetch=fetch_bytes):
    """피드 하나를 EPUB으로 만든다. 반환: (경로, 기사 수) 또는 (None, 0)=이미 존재해 건너뜀."""
    xml_bytes, _ctype = fetch(url, FEED_MAX_BYTES)
    feed = parse_feed(xml_bytes)
    if not feed["items"]:
        raise ValueError("피드에 기사가 없습니다.")
    name = safe_name(feed_name or feed["title"])
    today = datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(dest_dir, name)
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"{name}_{today}.epub")
    if os.path.exists(dest) and not force:
        return None, 0
    chapters, images = build_book_from_feed(feed, max_items, include_images, fetch=fetch)
    build_epub(dest, f"{feed_name or feed['title']} {today}", chapters, images)
    return dest, len(chapters)


_APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_COVER_FONTS = ("Pretendard-Regular.woff2", "NanumGothic.woff2")  # static/fonts (앱 번들, OFL)


def build_cover(title, date_str, labels):
    """합친 책용 표지(JPEG bytes). 날짜마다 색이 달라 서재에서 호수를 구분할 수 있다.
    Pillow나 번들 폰트를 쓸 수 없으면 None -> 호출부가 첫 기사 이미지로 폴백한다."""
    try:
        import colorsys
        import io
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    font_path = next((p for p in (os.path.join(_APP_ROOT, "static", "fonts", f) for f in _COVER_FONTS)
                      if os.path.exists(p)), None)
    if not font_path:
        return None
    try:
        W, H = 600, 900
        ordinal = datetime.strptime(date_str, "%Y-%m-%d").toordinal()
        hue = (ordinal * 0.137) % 1.0

        def rgb(h, s, v):
            return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))

        img = Image.new("RGB", (W, H), rgb(hue, 0.55, 0.22))
        d = ImageDraw.Draw(img)
        accent = rgb(hue, 0.45, 0.95)
        d.rectangle([0, 0, W, 14], fill=accent)
        d.rectangle([56, 120, 56 + 72, 126], fill=accent)

        def font(size):
            return ImageFont.truetype(font_path, size)

        # 번들 폰트는 서브셋이라 공백 글리프가 없어 "≡"로 깨진다 -> 단어별로 그리고 간격은 직접 계산
        def text_w(text, f):
            gap = f.size * 0.3
            words = text.split(" ")
            return sum(f.getlength(w) for w in words) + gap * (len(words) - 1)

        def draw_text(x, y, text, f, fill):
            gap = f.size * 0.3
            for w in text.split(" "):
                d.text((x, y), w, font=f, fill=fill)
                x += f.getlength(w) + gap

        def wrap(text, f, max_w):
            # 단어 단위 탐욕 줄바꿈. 한 단어가 한 줄보다 길 때만 글자 단위로 쪼갠다.
            lines, cur = [], ""
            for word in text.split():
                if text_w(word, f) > max_w:
                    pieces, piece = [], ""
                    for ch in word:
                        if text_w(piece + ch, f) > max_w and piece:
                            pieces.append(piece)
                            piece = ch
                        else:
                            piece += ch
                    if cur:
                        lines.append(cur)
                    lines.extend(pieces)
                    cur = piece
                    continue
                trial = f"{cur} {word}" if cur else word
                if text_w(trial, f) > max_w and cur:
                    lines.append(cur)
                    cur = word
                else:
                    cur = trial
            return lines + ([cur] if cur else [])

        y = 160
        tf = font(78)
        for line in wrap(title, tf, W - 112)[:3]:
            draw_text(56, y, line, tf, (255, 255, 255))
            y += 98
        draw_text(56, y + 18, date_str, font(44), accent)

        lf = font(26)
        y = H - 90
        for label in reversed(labels[:6]):
            draw_text(56, y, f"· {label}"[:28], lf, (255, 255, 255))
            y -= 38
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=88)
        return buf.getvalue()
    except Exception:
        return None


def run_digest(entries, dest_dir, book_name, max_items, include_images, force=False, fetch=fetch_bytes):
    """여러 피드를 한 권('오늘의 브리핑')으로 합친다. 일부 피드가 실패해도 나머지로 만든다.
    반환: (경로 또는 None=이미 존재, [피드별 결과 dict])."""
    name = safe_name(book_name, "briefing")
    today = datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(dest_dir, name)
    dest = os.path.join(folder, f"{name}_{today}.epub")
    if os.path.exists(dest) and not force:
        return None, [{"feed": n or u, "ok": True, "skipped": "오늘 분이 이미 있음"} for n, u in entries]

    state = {"images": {}, "url_to_name": {}}
    chapters, results = [], []
    for feed_name, url in entries:
        try:
            xml_bytes, _ctype = fetch(url, FEED_MAX_BYTES)
            feed = parse_feed(xml_bytes)
            label = feed_name or feed["title"] or url
            ch, _imgs = build_book_from_feed(feed, max_items, include_images, fetch=fetch,
                                             state=state, prefix=f"[{label}] ")
            if not ch:
                raise ValueError("피드에 기사가 없습니다.")
            chapters.extend(ch)
            results.append({"feed": label, "ok": True, "articles": len(ch), "file": os.path.basename(dest)})
        except Exception as e:
            results.append({"feed": feed_name or url, "ok": False, "error": str(e)})
    if not chapters:
        return None, results

    os.makedirs(folder, exist_ok=True)
    images = dict(state["images"]) if include_images else {}
    cover = build_cover(book_name, today, [r["feed"] for r in results if r.get("ok")])
    if cover:  # 첫 항목이 표지가 된다(build_epub 규칙)
        images = {"cover.jpg": (cover, "image/jpeg"), **images}
    build_epub(dest, f"{book_name} {today}", chapters, images)
    return dest, results


def parse_feed_lines(raw):
    """'이름|URL' 또는 'URL'을 줄바꿈 또는 ';'로 구분. 빈 항목/#주석 무시.
    (플러그인 설정 화면은 단일 행 input만 저장하므로 ';' 구분을 기본으로 안내한다.)"""
    feeds = []
    for line in re.split(r"[\n;]", str(raw or "").replace("\r", "")):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            n, u = line.split("|", 1)
            feeds.append((n.strip(), u.strip()))
        else:
            feeds.append(("", line))
    return feeds


# ----------------------------------------------------------------------
# 플러그인
# ----------------------------------------------------------------------

class RssEpubNewsProvider(BaseMetadataProvider):
    """RSS -> EPUB 일일 수집 플러그인."""

    id = "rss_epub_news"
    name = "RSS 뉴스 EPUB 수집"
    is_searchable = False
    config_schema = [
        {"key": "ENABLED", "label": "자동 수집 활성화", "type": "checkbox", "default": False,
         "description": "켜면 매일 지정한 시각 이후 한 번 수집합니다. (수동 실행 버튼은 항상 사용 가능)"},
        {"key": "FEEDS", "label": "RSS 피드 목록", "type": "text", "required": True,
         "description": "';'로 구분. '이름|URL' 또는 URL만. 예: 내 피드|https://example.com/feed.xml"},
        {"key": "LIBRARY_ID", "label": "저장할 라이브러리 ID", "type": "number", "required": True,
         "description": "일반 도서 라이브러리 중 로컬 경로를 가진 것의 ID. (GDrive 전용 라이브러리는 불가)"},
        {"key": "RUN_HOUR", "label": "수집 시각(시, 0~23)", "type": "number", "default": 6},
        {"key": "MAX_ITEMS", "label": "피드당 최대 기사 수", "type": "number", "default": 30},
        {"key": "INCLUDE_IMAGES", "label": "이미지 포함", "type": "checkbox", "default": True,
         "description": "끄면 텍스트만 수록합니다 (용량 절약)."},
        {"key": "MERGE_FEEDS", "label": "모든 피드를 한 권으로 합치기", "type": "checkbox", "default": False,
         "description": "켜면 피드마다 한 권 대신 하루 한 권('오늘의 브리핑')으로 묶고, 목차에서 [피드이름]으로 구분합니다."},
        {"key": "DIGEST_NAME", "label": "합친 책 이름", "type": "text", "default": "오늘의 브리핑"},
    ]

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 메타데이터 적용을 지원하지 않습니다."

    # --- 설정 -----------------------------------------------------------

    def _cfg(self):
        cfg = self.get_plugin_config("general", default={}) or {}

        def as_bool(v, default):
            if v is None:
                return default
            return v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "y", "yes", "on")

        def as_int(v, default, lo, hi):
            try:
                return max(lo, min(hi, int(v)))
            except Exception:
                return default

        return {
            "enabled": as_bool(cfg.get("ENABLED"), False),
            "feeds": parse_feed_lines(cfg.get("FEEDS")),
            "library_id": as_int(cfg.get("LIBRARY_ID"), 0, 0, 10 ** 9),
            "run_hour": as_int(cfg.get("RUN_HOUR"), 6, 0, 23),
            "max_items": as_int(cfg.get("MAX_ITEMS"), 30, 1, 200),
            "include_images": as_bool(cfg.get("INCLUDE_IMAGES"), True),
            "merge_feeds": as_bool(cfg.get("MERGE_FEEDS"), False),
            "digest_name": str(cfg.get("DIGEST_NAME") or "").strip() or "오늘의 브리핑",
        }

    # --- 상태 -----------------------------------------------------------

    def _set_status(self, data):
        self.get_db_gateway("general").set_setting(STATUS_KEY, json.dumps(data, ensure_ascii=False))

    def _get_status(self):
        raw = self.get_db_gateway("general").get_setting(STATUS_KEY)
        if not raw:
            return {"success": True, "status": "never_run"}
        try:
            data = json.loads(raw["value"] if isinstance(raw, dict) else raw)
        except Exception:
            return {"success": True, "status": "never_run"}
        data["success"] = True
        return data

    # --- 실행 -----------------------------------------------------------

    def _collect(self, force):
        cfg = self._cfg()
        if not cfg["feeds"]:
            raise ValueError("피드가 설정되지 않았습니다.")
        if not cfg["library_id"]:
            raise ValueError("저장할 라이브러리 ID가 설정되지 않았습니다.")

        from repositories.category_repository import CategoryRepository
        lib = CategoryRepository.get_library_by_id("general", cfg["library_id"])
        if not lib:
            raise ValueError(f"라이브러리를 찾을 수 없습니다: {cfg['library_id']}")
        from utils.drive_helper import is_gdrive_url
        roots = [p.strip() for p in str(lib.get("physical_path") or "").replace("\r", "").split("\n") if p.strip()]
        dest_dir = next((r for r in roots if not is_gdrive_url(r) and os.path.isdir(r)), None)
        if not dest_dir:
            raise ValueError("이 라이브러리에는 쓸 수 있는 로컬 경로가 없습니다 (원격/GDrive 전용).")

        results, created = [], 0
        if cfg["merge_feeds"]:
            path, results = run_digest(cfg["feeds"], dest_dir, cfg["digest_name"], cfg["max_items"],
                                       cfg["include_images"], force=force)
            created = 1 if path else 0
        else:
            for name, url in cfg["feeds"]:
                try:
                    path, count = run_feed(name, url, dest_dir, cfg["max_items"], cfg["include_images"], force=force)
                    if path:
                        created += 1
                        results.append({"feed": name or url, "ok": True, "articles": count, "file": os.path.basename(path)})
                    else:
                        results.append({"feed": name or url, "ok": True, "skipped": "오늘 분이 이미 있음"})
                except Exception as e:
                    results.append({"feed": name or url, "ok": False, "error": str(e)})

        if created:
            self._enqueue_scan(lib, cfg["library_id"])
        return results

    @staticmethod
    def _enqueue_scan(lib, library_id):
        """api의 일반 라이브러리 스캔(trigger_library_scan)과 같은 큐 경로로 등록한다."""
        try:
            import database
            from services.scanner_queue import scanner_queue
            scanner_queue.enqueue(
                "library_scan", db_type="general", db_path=database.get_db_path("general"),
                library_id=library_id, physical_path=lib["physical_path"], force=False,
                force_requeue=True, trigger_type="manual", is_cron=False,
            )
        except Exception as e:
            print(f"[rss_epub_news] 스캔 큐 등록 실패(다음 정기 스캔에서 반영됨): {e}")

    def _run_job(self, force):
        started = time.time()
        self._set_status({"status": "running", "started_at": started})
        try:
            results = self._collect(force)
            failed = [r for r in results if not r.get("ok")]
            self._set_status({"status": "success" if not failed else "partial", "started_at": started,
                              "finished_at": time.time(), "results": results})
            if failed:
                self.report_problem("rss_epub_feed_failed", title="RSS EPUB 수집 일부 실패",
                                    detail="; ".join(f"{r['feed']}: {r['error']}" for r in failed))
            else:
                self.resolve_problem("rss_epub_feed_failed")
        except Exception as e:
            self._set_status({"status": "error", "started_at": started, "finished_at": time.time(), "error": str(e)})
            self.report_problem("rss_epub_feed_failed", title="RSS EPUB 수집 실패", detail=str(e))

    # --- 스케줄 (워커가 여러 개여도 하루 한 번) ----------------------------

    @staticmethod
    def _claim_today():
        d = os.path.join(tempfile.gettempdir(), "bookoasis_rss_epub")
        os.makedirs(d, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        for old in os.listdir(d):  # 지난 날짜 lock 정리
            if not old.startswith(today):
                try:
                    os.remove(os.path.join(d, old))
                except OSError:
                    pass
        try:
            fd = os.open(os.path.join(d, f"{today}.lock"), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            return False

    def _scheduler_loop(self):
        while True:
            try:
                cfg = self._cfg()
                if cfg["enabled"] and datetime.now().hour >= cfg["run_hour"] and self._claim_today():
                    self._run_job(force=False)
            except Exception as e:
                print(f"[rss_epub_news] 스케줄러 오류: {e}")
            time.sleep(60)

    def start_background_service(self, db_type):
        threading.Thread(target=self._scheduler_loop, daemon=True, name="rss_epub_news").start()

    # --- 설정 화면의 수동 실행/상태 조회 ------------------------------------

    @staticmethod
    def _is_admin():
        try:
            return session.get("role") == "admin"
        except Exception:
            return False

    def run_context_menu_action(self, db_type, action_id, context):
        if action_id == "status":
            return self._get_status()
        if action_id == "run_now":
            if not self._is_admin():
                return {"success": False, "error": "관리자만 실행할 수 있습니다."}
            if self._get_status().get("status") == "running":
                return {"success": False, "error": "이미 실행 중입니다."}
            threading.Thread(target=self._run_job, args=(True,), daemon=True).start()
            return {"success": True, "message": "수집을 시작했습니다."}
        return {"success": False, "error": f"알 수 없는 액션: {action_id}"}
