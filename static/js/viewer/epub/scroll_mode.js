export function applyBaseContainerStyles(container, renderArea, theme) {
  container.style.backgroundColor = theme.background;
  container.style.boxSizing = 'border-box';
  container.style.padding = '0';
  container.style.margin = '0';

  renderArea.style.backgroundColor = theme.background;
  renderArea.style.boxSizing = 'border-box';
  renderArea.style.padding = '0';
  renderArea.style.margin = '0';
}

export async function renderScrollMode({
  container,
  renderArea,
  mergedContentEl,
  book,
  ratio,
  buildMergedContent,
  applyMergedThemeStyles,
  themeSettings,
  updateProgressPercent,
  isRunCurrent,
  currentLocationHref
}) {
  container.style.overflowY = 'auto';
  container.style.overflowX = 'hidden';
  container.style.scrollBehavior = 'auto';

  let contentEl = mergedContentEl;
  if (!contentEl) {
    contentEl = await buildMergedContent(book);
  }

  if (!isRunCurrent()) return contentEl;

  const { theme, fontCSS, fontSize, lineHeight, paragraphSpacing } = themeSettings;

  renderArea.innerHTML = '';
  contentEl.className = 'epub-merged-content scrolled-mode';
  contentEl.style.columnWidth = 'auto';
  contentEl.style.columnGap = 'normal';
  contentEl.style.height = 'auto';
  contentEl.style.width = '100%';
  contentEl.style.maxWidth = '800px';
  contentEl.style.margin = '0 auto';
  contentEl.style.padding = '40px 20px';
  contentEl.style.boxSizing = 'border-box';

  applyMergedThemeStyles(contentEl, theme, fontCSS, fontSize, lineHeight, paragraphSpacing);

  renderArea.appendChild(contentEl);

  // 돔 결합 직후 뷰포트 높이 왜곡(0으로 계산됨)으로 인한 스크롤 리셋을 방지하기 위해 100ms 대기 후 복원
  setTimeout(() => {
    if (!isRunCurrent()) return;

    let restored = false;
    
    // 1. 진척도 비율(ratio)이 존재하면 가장 최우선으로 복원 (소수점 단위 정확도)
    if (typeof ratio === 'number' && !isNaN(ratio) && ratio >= 0) {
      const totalScroll = container.scrollHeight - container.clientHeight;
      if (totalScroll > 0) {
        container.scrollTop = totalScroll * ratio;
        updateProgressPercent(ratio * 100);
        console.log('[Viewer-Epub-Scroll] Position restored via exact ratio:', ratio);
        restored = true;
      }
    }

    // 2. 비율이 없거나 복원 실패 시 챕터(href) 기반으로 이동
    if (!restored && currentLocationHref) {
      const cleanHref = currentLocationHref.split('#')[0].split('?')[0].split('/').pop();
      if (cleanHref) {
        const targetEl = renderArea.querySelector(`[data-href$="${cleanHref}"]`);
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: 'auto', block: 'start' });
          restored = true;
          console.log('[Viewer-Epub-Scroll] Position restored via scrollIntoView:', cleanHref);
          const totalScroll = container.scrollHeight - container.clientHeight;
          if (totalScroll > 0) {
            updateProgressPercent((container.scrollTop / totalScroll) * 100);
          }
        }
      }
    }

    if (!restored) {
      console.log('[Viewer-Epub-Scroll] Failed to restore position, default to 0');
    }

    // --- 앵커 텍스트 기반 보정 (모드 전환 오차 완벽 극복) ---
    const anchorText = sessionStorage.getItem('viewer_epub_transition_anchor');
    if (anchorText) {
      sessionStorage.removeItem('viewer_epub_transition_anchor');
      setTimeout(() => {
        try {
          const query = anchorText.substring(0, 30);
          console.log('[Viewer-Epub-Scroll] 🔍 Anchor Restore Started...');
          console.log('  1. Full Saved Anchor:', anchorText);
          console.log('  2. Query String (First 30 chars):', query);

          const walker = document.createTreeWalker(contentEl, NodeFilter.SHOW_TEXT, null, false);
          let node;
          let matchFound = false;
          while (node = walker.nextNode()) {
            if (node.nodeValue.includes(query)) {
              if (node.parentElement) {
                node.parentElement.scrollIntoView({ behavior: 'auto', block: 'start' });
                console.log('✅ [Viewer-Epub-Scroll] Position precisely restored via Text Anchor!');
                matchFound = true;
                const totalScroll = container.scrollHeight - container.clientHeight;
                if (totalScroll > 0) {
                  updateProgressPercent((container.scrollTop / totalScroll) * 100);
                }
                break;
              }
            }
          }
          if (!matchFound) {
            console.log('❌ [Viewer-Epub-Scroll] No match found for the query in this mode.');
          }
        } catch(e) {
          console.warn('[Viewer-Epub-Scroll] Anchor restore failed:', e);
        }
      }, 200);
    }
  }, 100);

  return contentEl;
}
