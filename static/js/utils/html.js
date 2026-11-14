// HTML 이스케이프·플러그인 HTML 정화 공용 유틸.
// 예전에는 모듈마다 escapeHtml 사본(28벌)이 있었고 null·0·작은따옴표 처리가 제각각이었다.
// 클래식 스크립트(tv.js, settings_trash.js)는 import할 수 없어 로컬 사본을 유지한다.

/**
 * 텍스트를 HTML 본문/속성 어디에 넣어도 안전하도록 이스케이프한다.
 * null/undefined → '', 숫자 0 → '0'.
 */
export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** 속성값용 별칭 (escapeHtml이 따옴표까지 처리하므로 동일) */
export const escapeAttr = escapeHtml;

const DANGEROUS_TAGS = /(<\s*\/?(script|iframe|object|embed|form|input|button|select|textarea|style|link|meta|base|svg|math)[^>]*>)/gi;
const ALLOWED_TAGS = new Set(['b', 'i', 'em', 'strong', 'br', 'span', 'a', 'ul', 'ol', 'li', 'p', 'small', 'mark', 'code']);
const SAFE_SPAN_STYLE = /^\s*(color|font-weight|font-style|font-size|text-decoration)\s*:/i;

/**
 * 플러그인 콘텐츠용 제한적 HTML 허용.
 * 허용 태그: b, i, em, strong, br, span(style 일부), a(href/title), ul, ol, li, p, small, mark, code
 * description 같은 플러그인 콘텐츠 필드에만 쓴다. title/author 같은 고유명사는 escapeHtml.
 */
export function sanitizePluginHtml(value) {
  let sanitized = String(value ?? '').replace(DANGEROUS_TAGS, '');
  // on* 이벤트 속성 제거
  sanitized = sanitized.replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '');
  // javascript: 프로토콜 제거
  sanitized = sanitized.replace(/(href|src)\s*=\s*["']?\s*javascript:[^"'>]*/gi, '$1="#"');

  return sanitized.replace(/<(\/?)(\w+)([^>]*)>/g, (match, slash, tag, attrs) => {
    const lowerTag = tag.toLowerCase();
    if (!ALLOWED_TAGS.has(lowerTag)) {
      return match.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    // 닫는 태그는 속성 없이 그대로 닫는다 (예전 사본은 </a>를 <a ...>로 바꿔 링크가 닫히지 않았다)
    if (slash) return `</${lowerTag}>`;
    if (lowerTag === 'a') {
      const hrefMatch = attrs.match(/href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]*))/i);
      const titleMatch = attrs.match(/title\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      const href = hrefMatch ? (hrefMatch[1] || hrefMatch[2] || hrefMatch[3] || '#') : '#';
      const title = titleMatch ? ` title="${escapeHtml(titleMatch[1] || titleMatch[2] || '')}"` : '';
      const safeHref = /^(https?:\/\/|\/)/.test(href) ? href : '#';
      return `<a href="${escapeHtml(safeHref)}"${title} target="_blank" rel="noopener noreferrer">`;
    }
    if (lowerTag === 'span') {
      const styleMatch = attrs.match(/style\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      if (styleMatch) {
        const safeStyle = (styleMatch[1] || styleMatch[2] || '')
          .split(';')
          .filter((rule) => SAFE_SPAN_STYLE.test(rule))
          .join(';');
        if (safeStyle) return `<span style="${escapeHtml(safeStyle)}">`;
      }
      return '<span>';
    }
    return `<${lowerTag}>`;
  });
}
