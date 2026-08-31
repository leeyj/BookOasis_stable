# CHANGELOG
## v2.5.1
- (improvement) PDF 커버를 표지 표시 크기의 2배로 렌더링한 뒤 축소(수퍼샘플링)해 불필요한 대형 비트맵 생성은 피하면서 텍스트 선명도 유지 | improve PDF cover rendering to render at 2x the display size then downscale (supersampling), avoiding unnecessarily large intermediate bitmaps while keeping text crisp
- (breaking) PDF 처리 엔진을 PyMuPDF(AGPL)에서 pypdfium2(Apache-2.0/BSD, 크롬과 동일한 Pdfium 엔진)로 교체 | (breaking) switch PDF engine from PyMuPDF (AGPL) to pypdfium2 (Apache-2.0/BSD, the same Pdfium engine used by Chrome)
- (fix) PDF 뷰어에서 페이지를 넘길 때마다 흰 화면이 잠깐 보였다가 내용이 채워지던 깜빡임 수정 — 새 페이지 렌더링이 끝날 때까지 이전 페이지를 유지 | fix a white-flash-then-fill flicker on every PDF page turn — the previous page now stays visible until the new one finishes rendering
