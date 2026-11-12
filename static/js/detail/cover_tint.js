// cover_tint.js – 시리즈 상세에서 표지의 대표 색 두 개를 뽑아 본문 영역 배경에 은은한 투톤 그라데이션으로 깐다.
// 서버/DB를 건드리지 않고, 이미 불러온 표지 <img>를 canvas로 작게 줄여 브라우저에서 계산한다.
// 색을 못 뽑으면(다른 출처 이미지라 canvas가 막힘, 흑백 표지, 대체 텍스트 표지) 그라데이션 없이 원래 배경을 둔다.
// 섞는 비율·테마별 처리(라이트는 약하게, e-paper는 끔)는 CSS(.library-main-content.has-cover-tint)가 맡는다.

const SAMPLE_SIZE = 40;
let currentToken = 0;

function getMainContent() {
  return document.querySelector('.library-main-content');
}

export function clearCoverTint() {
  currentToken += 1;
  const main = getMainContent();
  if (main) main.classList.remove('has-cover-tint');
}

function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return [h * 60, s, l];
}

function hueDistance(a, b) {
  const d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
}

// 색상(hue) 24칸 히스토그램을 채도 가중치로 쌓아 가장 큰 칸 두 개를 고른다.
// 두 번째 색은 첫 색과 hue가 충분히 떨어진 칸에서 고르고, 없으면 첫 색을 어둡게 돌린 색을 쓴다.
export function extractTintColors(img) {
  const canvas = document.createElement('canvas');
  canvas.width = SAMPLE_SIZE;
  canvas.height = SAMPLE_SIZE;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(img, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
  const { data } = ctx.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE); // 다른 출처 이미지면 SecurityError

  const BINS = 24;
  const bins = Array.from({ length: BINS }, () => ({ w: 0, h: 0, s: 0, l: 0 }));
  let totalWeight = 0;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] < 128) continue;
    const [h, s, l] = rgbToHsl(data[i], data[i + 1], data[i + 2]);
    if (l < 0.08 || l > 0.94 || s < 0.15) continue; // 거의 검정/흰색/회색은 분위기를 만들지 못한다
    const w = s * s * (1 - Math.abs(l - 0.5));
    const bin = bins[Math.floor(h / (360 / BINS)) % BINS];
    // hue 평균은 각도라 단순 평균이 틀어질 수 있지만, 15도 칸 안에서는 무시할 수 있다
    bin.w += w; bin.h += h * w; bin.s += s * w; bin.l += l * w;
    totalWeight += w;
  }
  // 채도 있는 픽셀이 거의 없으면(흑백·무채색 표지) 틴트 생략
  if (totalWeight < SAMPLE_SIZE * SAMPLE_SIZE * 0.01) return null;

  const ranked = bins
    .filter(b => b.w > 0)
    .map(b => ({ w: b.w, h: b.h / b.w, s: b.s / b.w, l: b.l / b.w }))
    .sort((a, b) => b.w - a.w);
  const primary = ranked[0];
  const secondary = ranked.find(c => hueDistance(c.h, primary.h) >= 40 && c.w >= primary.w * 0.12)
    || { h: (primary.h + 30) % 360, s: primary.s, l: primary.l * 0.6 };

  // 배경용으로 정규화: 너무 쨍하거나 너무 어두운 색은 범위 안으로 당긴다
  const norm = (c) => {
    const s = Math.min(Math.max(c.s, 0.35), 0.75);
    const l = Math.min(Math.max(c.l, 0.35), 0.55);
    return `hsl(${Math.round(c.h)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%)`;
  };
  return [norm(primary), norm(secondary)];
}

export function applyCoverTint(img) {
  clearCoverTint();
  if (!img) return;
  const token = currentToken;

  const run = () => {
    if (token !== currentToken) return; // 그 사이 다른 상세/화면으로 바뀜
    const main = getMainContent();
    if (!main) return;
    // 표지가 없어 만든 텍스트 표지는 색이 임의라 쓰지 않는다
    if (img.dataset.fallbackApplied === 'true' || !img.naturalWidth) {
      main.classList.remove('has-cover-tint');
      return;
    }
    let colors = null;
    try {
      colors = extractTintColors(img);
    } catch (err) {
      colors = null; // 다른 출처 표지(canvas taint) 등
    }
    if (!colors) {
      main.classList.remove('has-cover-tint');
      return;
    }
    main.style.setProperty('--cover-tint-a', colors[0]);
    main.style.setProperty('--cover-tint-b', colors[1]);
    main.classList.add('has-cover-tint');
  };

  if (img.complete && img.naturalWidth) run();
  // 표지 교체(업로드·대체 표지)로 다시 load될 때도 따라간다
  img.addEventListener('load', run);
  img.addEventListener('error', () => {
    if (token === currentToken) getMainContent()?.classList.remove('has-cover-tint');
  });
}
