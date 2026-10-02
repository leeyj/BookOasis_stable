// cover_ratio.js - 카테고리 그리드 커버 비율 판단 (사이드바 항목 dataset 기준, 순수 함수)
//
// 허용 값: '4:3'(기본, 실제 프레임은 책 표지 세로형) / '16:9'(와이드) / '1:1'(정사각).
// 오디오북 세션의 '음악' 속성 카테고리는 앨범 아트가 정사각이라 설정과 무관하게 항상 '1:1'.

export const COVER_ASPECT_RATIOS = ['4:3', '16:9', '1:1'];

export function normalizeCoverAspectRatio(value) {
  return COVER_ASPECT_RATIOS.includes(value) ? value : '4:3';
}

export function resolveCoverAspectRatio(dataset, libraryType) {
  if (!dataset) return '4:3';
  if (libraryType === 'audiobook' && dataset.contentKind === 'music') return '1:1';
  return normalizeCoverAspectRatio(dataset.coverAspectRatio);
}

// 카드 data-cover-ratio 값 ('16:9' -> '16-9')
export function coverRatioAttr(ratio) {
  return normalizeCoverAspectRatio(ratio).replace(':', '-');
}
