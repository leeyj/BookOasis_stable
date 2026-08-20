const COVER_THEMES = [
  { bgStart: '#13253a', bgEnd: '#0b1828', border: '#79c2ff', line: '#a7dcff', accent: '#82d9b1' },
  { bgStart: '#2b1f3a', bgEnd: '#15142a', border: '#b79bff', line: '#cab9ff', accent: '#ffd06e' },
  { bgStart: '#3a231e', bgEnd: '#1f1516', border: '#ffaf8f', line: '#ffc5ab', accent: '#ffd66e' },
  { bgStart: '#1b2f3a', bgEnd: '#101924', border: '#8dd3ff', line: '#b7e6ff', accent: '#f8d878' },
  { bgStart: '#3a311d', bgEnd: '#1f1a12', border: '#dfc37e', line: '#f1dcab', accent: '#8cd0ff' },
  { bgStart: '#22263a', bgEnd: '#121625', border: '#9ea8ff', line: '#c0c7ff', accent: '#a4e3b0' }
];

const SVG_CACHE = new Map();

function isAudiobookContext() {
  return Boolean(
    window.location.hash.includes('audiobook') ||
    document.querySelector('.media-tab.active[data-type="audiobook"]') ||
    document.getElementById('audio-player-modal')?.style.display === 'block'
  );
}

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

const AUDIOBOOK_THEME = {
  bgStart: '#1e3a8a',
  bgEnd: '#0f172a',
  border: '#38bdf8',
  line: '#7dd3fc',
  accent: '#60a5fa'
};

function formatLabel(format) {
  const key = String(format || 'text').toLowerCase();
  if ((key === 'text' || !key) && isAudiobookContext()) return 'AUDIO';
  if (key === 'cbz' || key === 'zip') return 'COMIC';
  if (key === 'epub') return 'EPUB';
  if (key === 'pdf') return 'PDF';
  if (key === 'imgdir') return 'IMG';
  if (['audiobook', 'audio', 'm4a', 'm4b', 'mp3', 'aac', 'flac', 'ogg', 'wma'].includes(key)) return 'AUDIO';
  if (key === 'video') return 'VIDEO';
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

function buildLandscapeVideoCoverSvg(normalizedTitle, theme) {
  const lines = splitTitleLines(normalizedTitle, 13, 2);
  const lineYStart = lines.length === 1 ? 214 : 196;
  const lineGap = 40;
  const titleLinesSvg = lines
    .map((line, idx) => `<text x="320" y="${lineYStart + idx * lineGap}" text-anchor="middle" fill="#f8fafc" font-family="sans-serif" font-size="32" font-weight="700">${escapeXml(line)}</text>`)
    .join('');

  return `
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"640\" height=\"360\" viewBox=\"0 0 640 360\" role=\"img\" aria-label=\"${escapeXml(normalizedTitle)}\">
  <defs>
    <linearGradient id=\"bg\" x1=\"0%\" y1=\"0%\" x2=\"100%\" y2=\"100%\">
      <stop offset=\"0%\" stop-color=\"${theme.bgStart}\" />
      <stop offset=\"100%\" stop-color=\"${theme.bgEnd}\" />
    </linearGradient>
  </defs>
  <rect width=\"640\" height=\"360\" rx=\"18\" fill=\"url(#bg)\" />
  <polygon points=\"572,0 640,0 640,40\" fill=\"${theme.accent}\" opacity=\"0.9\" />
  <rect x=\"22\" y=\"20\" width=\"596\" height=\"320\" rx=\"12\" fill=\"none\" stroke=\"${theme.border}\" stroke-width=\"3\" opacity=\"0.95\" />
  <circle cx=\"320\" cy=\"128\" r=\"38\" fill=\"none\" stroke=\"${theme.line}\" stroke-width=\"3\" opacity=\"0.92\" />
  <polygon points=\"308,110 308,146 340,128\" fill=\"${theme.line}\" opacity=\"0.95\" />
  ${titleLinesSvg}
  <text x="320" y="308" text-anchor="middle" fill="#dbe3ea" font-family="monospace" font-size="22" letter-spacing="4" opacity="0.88">VIDEO</text>
</svg>`;
}

export function buildTextCoverDataUri({ title, format, seed } = {}) {
  const normalizedTitle = normalizeTitle(title);
  const label = formatLabel(format);
  const cacheKey = `${normalizedTitle}|${label}|${seed || ''}`;
  if (SVG_CACHE.has(cacheKey)) {
    return SVG_CACHE.get(cacheKey);
  }

  const hash = hashString(seed || normalizedTitle);
  const theme = (label === 'AUDIO') ? AUDIOBOOK_THEME : COVER_THEMES[hash % COVER_THEMES.length];

  let svg;
  if (label === 'VIDEO') {
    // 영상 강좌 그리드는 CSS에서 16:9(object-fit: cover)로 표시되므로, 세로 420x600
    // 책 템플릿을 그대로 쓰면 위아래가 잘려나가 텅 빈 조각만 보인다 - 가로 전용 템플릿 사용
    svg = buildLandscapeVideoCoverSvg(normalizedTitle, theme);
  } else {
    const lines = splitTitleLines(normalizedTitle, 9, 3);
    const lineYStart = lines.length === 1 ? 250 : lines.length === 2 ? 222 : 202;
    const lineGap = 48;
    const titleLinesSvg = lines
      .map((line, idx) => `<text x="210" y="${lineYStart + idx * lineGap}" text-anchor="middle" fill="#f8fafc" font-family="sans-serif" font-size="42" font-weight="700">${escapeXml(line)}</text>`)
      .join('');

    svg = `
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
  <text x="210" y="500" text-anchor="middle" fill="#dbe3ea" font-family="monospace" font-size="28" letter-spacing="4" opacity="0.88">${label}</text>
</svg>`;
  }

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
  if (coverImage && typeof coverImage === 'string') {
    let clean = coverImage.trim();
    if (clean.startsWith('http://') || clean.startsWith('https://') || clean.startsWith('/api/')) {
      return clean;
    }
    clean = clean.replace(/^[\/\\]+/, '');
    if (clean.toLowerCase().startsWith('covers/')) {
      clean = clean.substring(7).replace(/^[\/\\]+/, '');
    }
    const filename = clean.split(/[\/\\]/).pop();
    if (clean && !clean.endsWith('/') && !clean.endsWith('\\') && filename && filename.includes('.')) {
      return `/covers/${clean}`;
    }
  }
  return buildFallbackCoverUrl({ title, format, seed });
}

export function handleCoverError(img, title = '', format = '') {
  if (!img || img.dataset.fallbackApplied === 'true') return;
  img.dataset.fallbackApplied = 'true';
  const altTitle = title || img.getAttribute('alt') || img.dataset.title || 'Book';
  let fmt = format || img.dataset.format || 'text';

  // 현재 미디어 탭이 오디오북이거나 주소창 해시에 audiobook이 포함된 경우 'audiobook' 포맷으로 자동 승격
  const audiobookCtx = isAudiobookContext();
  if ((fmt === 'text' || !fmt) && audiobookCtx) {
    fmt = 'audiobook';
  }

  img.src = buildTextCoverDataUri({ title: altTitle, format: fmt });
}
window.handleCoverError = handleCoverError;
window.buildTextCoverDataUri = buildTextCoverDataUri;
