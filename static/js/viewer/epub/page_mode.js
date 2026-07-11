export async function activateRenditionPageMode({
  renderArea,
  ratio,
  themeSettings,
  book,
  getViewportSize,
  getEpubPageStep,
  getEffectivePageStep,
  syncPageStepUI,
  currentRendition,
  destroyRendition,
  bindRenditionInteractionHandlers,
  getScrollMode,
  goBackward,
  goForward,
  toggleOverlay,
  ensureLocations,
  locationsChars,
  applyRenditionTheme,
  safeRenditionDisplay,
  currentLocationCfi,
  currentLocationHref,
  setCurrentLocation,
  setRenditionAtEnd,
  updateProgressPercent,
  isRunCurrent
}) {
  if (!renderArea || !renderArea.isConnected) return currentRendition;
  if (!isRunCurrent()) return currentRendition;

  const { theme, fontCSS, fontSize, lineHeight, paragraphSpacing } = themeSettings;
  const { width, height } = getViewportSize(renderArea);
  const pageStep = getEffectivePageStep(width, getEpubPageStep());
  const forcedSinglePage = pageStep === 1 && getEpubPageStep() === 2;
  syncPageStepUI(pageStep, forcedSinglePage);

  renderArea.innerHTML = '';
  const host = document.createElement('div');
  host.id = 'epub-rendition-host';
  host.style.width = '100%';
  host.style.height = '100%';
  host.style.background = theme.background;
  renderArea.appendChild(host);

  if (currentRendition) {
    await destroyRendition();
  }

  if (!renderArea || !renderArea.isConnected) return null;
  if (!isRunCurrent()) return null;

  const rendition = book.renderTo(host, {
    width,
    height,
    flow: 'paginated',
    manager: 'default',
    spread: pageStep === 2 ? 'always' : 'none',
    minSpreadWidth: pageStep === 2 ? 0 : 99999
  });

  rendition.hooks.content.register(function(contents) {
    const customFonts = window.customFonts || [];
    let styleContent = '';
    customFonts.forEach(f => {
      const fontFaceName = `CustomFont_${f.name.replace(/\s+/g, '_')}`;
      styleContent += `@font-face { font-family: '${fontFaceName}'; src: url("${f.url}"); }\n`;
    });
    if (styleContent) {
      const style = contents.document.createElement('style');
      style.innerHTML = styleContent;
      contents.document.head.appendChild(style);
    }
  });

  bindRenditionInteractionHandlers({
    rendition,
    getScrollMode,
    goBackward,
    goForward,
    toggleOverlay
  });

  rendition.on('relocated', async location => {
    const cfi = location && location.start ? location.start.cfi : null;
    const href = location && location.start ? location.start.href : null;
    const index = (location && location.start && Number.isInteger(location.start.index)) ? location.start.index : null;
    setCurrentLocation({ cfi, href, index });
    setRenditionAtEnd(!!(location && location.atEnd));

    try {
      let resolvedPercent = null;

      // 1. CFI를 이용한 정밀 백분율 계산 시도
      if (cfi && book.locations && book.locations.length) {
        const ratioFromCfi = book.locations.percentageFromCfi(cfi);
        if (Number.isFinite(ratioFromCfi) && ratioFromCfi >= 0) {
          resolvedPercent = ratioFromCfi * 100;
        }
      }

      // 2. 정밀 계산 실패 시, 스파인(Spine) 인덱스 비율 기반 폴백 계산
      if (resolvedPercent === null) {
        const items = (book.spine && book.spine.spineItems) ? book.spine.spineItems.filter(item => item && item.linear !== 'no') : [];
        if (items.length > 0) {
          let targetIdx = index;
          if (!Number.isInteger(targetIdx) && href) {
            const normHref = href.split('#')[0];
            targetIdx = items.findIndex(item => item.href && item.href.split('#')[0] === normHref);
          }
          if (Number.isInteger(targetIdx) && targetIdx >= 0) {
            resolvedPercent = (targetIdx / items.length) * 100;
            console.log(`[Viewer-Epub-Progress] percentageFromCfi failed, fallback to spine ratio: index=${targetIdx}/${items.length} (${resolvedPercent.toFixed(1)}%)`);
          }
        }
      }

      // 3. 계산된 진행률이 있으면 즉시 시크바 동기화 호출
      if (resolvedPercent !== null) {
        updateProgressPercent(resolvedPercent);
      }

      ensureLocations(book, locationsChars).then(() => {
        if (cfi && book.locations && book.locations.length) {
          const ratioFromCfi = book.locations.percentageFromCfi(cfi);
          if (Number.isFinite(ratioFromCfi) && ratioFromCfi >= 0) {
            updateProgressPercent(ratioFromCfi * 100);
          }
        }
      }).catch(() => {});
    } catch (err) {
      console.warn('[Viewer-Epub] Relocated progress sync failed:', err);
    }
  });

  applyRenditionTheme(rendition, theme, fontCSS, fontSize, lineHeight, paragraphSpacing);

  if (!isRunCurrent()) return rendition;

  // 1. 읽던 위치 또는 대략 비율 위치를 먼저 즉시 화면에 렌더링 (await 로딩 블로킹 제거)
  const displayPromise = (async () => {
    if (currentLocationCfi) {
      console.log('[Viewer-Epub] Displaying currentLocationCfi immediately:', currentLocationCfi);
      await safeRenditionDisplay(rendition, currentLocationCfi);
    } else if (currentLocationHref) {
      console.log('[Viewer-Epub] Displaying currentLocationHref immediately:', currentLocationHref);
      await safeRenditionDisplay(rendition, currentLocationHref);
    } else if (ratio !== null && ratio !== undefined) {
      if (book.locations && book.locations.length) {
        // 이미 Locations 연산이 끝났다면, 완벽하고 정밀한 cfi 계산 가능
        const preciseCfi = book.locations.cfiFromPercentage(ratio);
        console.log(`[Viewer-Epub] Displaying ratio via precise locations CFI: ${ratio}`);
        await safeRenditionDisplay(rendition, preciseCfi);
      } else {
        // Locations 계산 전이므로, locations가 필요 없는 Spine 기반 비율 이동 폴백 제공
        const items = (book.spine && book.spine.spineItems) ? book.spine.spineItems.filter(item => item && item.linear !== 'no') : [];
        let targetCfi = null;
        if (items.length > 0) {
          const targetIndex = Math.min(items.length - 1, Math.floor(items.length * ratio));
          targetCfi = items[targetIndex].href;
          console.log(`[Viewer-Epub] Displaying ratio via spine fallback: ${targetIndex}/${items.length} ratio=${ratio}`);
        }
        await safeRenditionDisplay(rendition, targetCfi);
      }
    } else {
      console.log('[Viewer-Epub] Displaying first page default (null)');
      await safeRenditionDisplay(rendition, null);
    }

    // --- 앵커 텍스트 기반 보정 (모드 전환 오차 완벽 극복) ---
    const anchorText = sessionStorage.getItem('viewer_epub_transition_anchor');
    if (anchorText) {
      sessionStorage.removeItem('viewer_epub_transition_anchor');
      setTimeout(() => {
        try {
          const query = anchorText.substring(0, 30);
          console.log('[Viewer-Epub] 🔍 Anchor Restore Started...');
          console.log('  1. Full Saved Anchor:', anchorText);
          console.log('  2. Query String (First 30 chars):', query);

          if (book && typeof book.find === 'function') {
            book.find(query).then(results => {
              console.log(`  3. book.find results count: ${results ? results.length : 0}`);
              if (results && results.length > 0) {
                let bestMatch = results[0];
                const loc = rendition.currentLocation();
                if (loc && loc.start && loc.start.href) {
                  const cleanHref = loc.start.href.split('#')[0].split('?')[0].split('/').pop();
                  const sameChapterMatch = results.find(r => r.cfi.includes(cleanHref));
                  if (sameChapterMatch) {
                    bestMatch = sameChapterMatch;
                    console.log(`  4. Best Match Selected (Same Chapter [${cleanHref}]):`, bestMatch.cfi);
                  } else {
                    console.log(`  4. Best Match Selected (First Result):`, bestMatch.cfi);
                  }
                }
                console.log('✅ [Viewer-Epub] Page mode precise position restored!');
                safeRenditionDisplay(rendition, bestMatch.cfi);
              } else {
                console.log('❌ [Viewer-Epub] No match found for the query in this book.');
              }
            }).catch(err => console.warn('book.find failed:', err));
          }
        } catch(e) {
          console.warn('[Viewer-Epub] Anchor restore failed:', e);
        }
      }, 300);
    }
  })();

  // 2. locations 연산은 백그라운드 비동기로 위임하여 슬라이더 잠금 예방
  ensureLocations(book, locationsChars).then(() => {
    console.log('[Viewer-Epub] Background locations generation complete.');
    // locations 연산이 완료된 시점에 슬라이더 UI 동기화
    try {
      if (rendition && rendition.manager && typeof rendition.currentLocation === 'function') {
        const loc = rendition.currentLocation();
        const cfi = loc && loc.start ? loc.start.cfi : null;
        if (cfi && book.locations && book.locations.length) {
          const ratioFromCfi = book.locations.percentageFromCfi(cfi);
          if (Number.isFinite(ratioFromCfi) && ratioFromCfi >= 0) {
            console.log('[Viewer-Epub] Updating progress after background locations calculated:', ratioFromCfi);
            updateProgressPercent(ratioFromCfi * 100);
          }
        }
      }
    } catch (e) {
      console.warn('[Viewer-Epub] Safe location sync after locations calculation failed:', e);
    }
  }).catch(err => {
    console.warn('[Viewer-Epub] Background locations generation failed:', err);
  });

  await displayPromise;

  return rendition;
}
