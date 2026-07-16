const COVER_THEMES = [
  { bgStart: '#13253a', bgEnd: '#0b1828', border: '#79c2ff', line: '#a7dcff', accent: '#82d9b1' },
  { bgStart: '#2b1f3a', bgEnd: '#15142a', border: '#b79bff', line: '#cab9ff', accent: '#ffd06e' },
  { bgStart: '#3a231e', bgEnd: '#1f1516', border: '#ffaf8f', line: '#ffc5ab', accent: '#ffd66e' },
  { bgStart: '#1b2f3a', bgEnd: '#101924', border: '#8dd3ff', line: '#b7e6ff', accent: '#f8d878' },
  { bgStart: '#3a311d', bgEnd: '#1f1a12', border: '#dfc37e', line: '#f1dcab', accent: '#8cd0ff' },
  { bgStart: '#22263a', bgEnd: '#121625', border: '#9ea8ff', line: '#c0c7ff', accent: '#a4e3b0' }
];

const SVG_CACHE = new Map();

function hashString(value) {
  const text = String(value || '');
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
  }
  return Math.abs(hash >>> 0);
}

function escapeXml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function normalizeTitle(title) {
  return String(title || '').replace(/\s+/g, ' ').trim() || 'Untitled';
}

function formatLabel(format) {
  const key = String(format || 'text').toLowerCase();
  if (key === 'cbz' || key === 'zip') return 'COMIC';
  if (key === 'epub') return 'EPUB';
  if (key === 'pdf') return 'PDF';
  if (key === 'imgdir') return 'IMG';
  if (key === 'audiobook') return 'AUDIO';
  return 'TEXT';
}

function splitTitleLines(title, maxCharsPerLine = 10, maxLines = 3) {
  const normalized = normalizeTitle(title);
  if (!normalized) return ['Untitled'];

  const chars = Array.from(normalized);
  const lines = [];
  for (let i = 0; i < chars.length && lines.length < maxLines; i += maxCharsPerLine) {
    lines.push(chars.slice(i, i + maxCharsPerLine).join(''));
  }

  if (chars.length > maxCharsPerLine * maxLines && lines.length > 0) {
    const last = lines[lines.length - 1];
    lines[lines.length - 1] = `${last.slice(0, Math.max(0, last.length - 1))}…`;
  }

  return lines;
}

export function buildTextCoverDataUri({ title, format, seed } = {}) {
  const normalizedTitle = normalizeTitle(title);
  const label = formatLabel(format);
  const cacheKey = `${normalizedTitle}|${label}|${seed || ''}`;
  if (SVG_CACHE.has(cacheKey)) {
    return SVG_CACHE.get(cacheKey);
  }

  const hash = hashString(seed || normalizedTitle);
  const theme = COVER_THEMES[hash % COVER_THEMES.length];
  const lines = splitTitleLines(normalizedTitle, 9, 3);

  const lineYStart = lines.length === 1 ? 250 : lines.length === 2 ? 222 : 202;
  const lineGap = 48;
  const titleLinesSvg = lines
    .map((line, idx) => `<text x=\"210\" y=\"${lineYStart + idx * lineGap}\" text-anchor=\"middle\" fill=\"#f8fafc\" font-family=\"'Noto Sans KR', 'Pretendard', sans-serif\" font-size=\"42\" font-weight=\"700\">${escapeXml(line)}</text>`)
    .join('');

  const svg = `
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"420\" height=\"600\" viewBox=\"0 0 420 600\" role=\"img\" aria-label=\"${escapeXml(normalizedTitle)}\">
  <defs>
    <linearGradient id=\"bg\" x1=\"0%\" y1=\"0%\" x2=\"100%\" y2=\"100%\">
      <stop offset=\"0%\" stop-color=\"${theme.bgStart}\" />
      <stop offset=\"100%\" stop-color=\"${theme.bgEnd}\" />
    </linearGradient>
  </defs>
  <rect width=\"420\" height=\"600\" rx=\"20\" fill=\"url(#bg)\" />
  <polygon points=\"366,0 420,0 420,54\" fill=\"${theme.accent}\" opacity=\"0.9\" />
  <rect x=\"28\" y=\"22\" width=\"364\" height=\"556\" rx=\"14\" fill=\"none\" stroke=\"${theme.border}\" stroke-width=\"3.2\" opacity=\"0.95\" />
  <rect x=\"48\" y=\"52\" width=\"324\" height=\"4\" rx=\"2\" fill=\"${theme.line}\" opacity=\"0.92\" />
  ${titleLinesSvg}
  <text x=\"210\" y=\"500\" text-anchor=\"middle\" fill=\"#dbe3ea\" font-family=\"'JetBrains Mono', monospace\" font-size=\"28\" letter-spacing=\"4\" opacity=\"0.88\">${label}</text>
</svg>`;

  const dataUri = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
  SVG_CACHE.set(cacheKey, dataUri);
  return dataUri;
}

export function buildFallbackCoverUrl({ title, format, seed } = {}) {
  const normalizedTitle = normalizeTitle(title);
  const label = formatLabel(format);
  const params = new URLSearchParams();
  params.set('title', normalizedTitle);
  params.set('format', label.toLowerCase());
  if (seed) {
    params.set('seed', String(seed));
  }
  return `/covers/fallback?${params.toString()}`;
}

export function getBookCoverSrc({ coverImage, title, format, seed } = {}) {
  if (coverImage) {
    return `/covers/${coverImage}`;
  }
  return buildFallbackCoverUrl({ title, format, seed });
}
