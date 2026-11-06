export function chunkText(text, chunkSize = 4000) {
  const chunks = [];
  let start = 0;
  while (start < text.length) {
    if (start + chunkSize >= text.length) {
      chunks.push(text.slice(start));
      break;
    }
    let end = start + chunkSize;
    const nextNewline = text.indexOf('\n', end);
    if (nextNewline !== -1 && nextNewline - end < 500) {
      end = nextNewline + 1;
    }
    chunks.push(text.slice(start, end));
    start = end;
  }
  return chunks;
}

export function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function stripHtml(html) {
  if (!html) return '';
  return html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
}

// Read anchors must match rendered EPUB text. Decode character references after stripping tags,
// without changing stripHtml's existing source-coordinate behavior for its other callers.
export function decodeHtmlEntities(text) {
  if (!text) return '';
  if (typeof document === 'undefined') return String(text);
  const textarea = document.createElement('textarea');
  // textarea parses character references as text; escaping literal '<' also prevents markup
  // interpretation, script execution, or resource loads from untrusted EPUB content.
  textarea.innerHTML = String(text).replace(/</g, '&lt;');
  return textarea.value;
}

export function stripHtmlForAnchor(html) {
  return decodeHtmlEntities(stripHtml(html)).replace(/\s+/g, ' ').trim();
}

export function formatTxtToHtml(rawText) {
  const lines = rawText.split('\n');
  const htmlParts = [];
  let prevWasEmpty = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      // 연속된 빈 줄(여러 개의 엔터)은 1개만 출력 — 행간을 넓혀도 문단 사이가 과도하게 벌어지는 문제 방지
      if (prevWasEmpty) continue;
      prevWasEmpty = true;
      htmlParts.push('<p class="txt-paragraph txt-empty-line" style="margin: 0; min-height: 1rem;">&nbsp;</p>');
    } else {
      prevWasEmpty = false;
      htmlParts.push(`<p class="txt-paragraph" style="margin: 0;">${escapeHtml(line)}</p>`);
    }
  }

  return htmlParts.join('');
}
