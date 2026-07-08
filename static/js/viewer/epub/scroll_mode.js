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
    if (currentLocationHref) {
      const cleanHref = currentLocationHref.split('#')[0].split('?')[0].split('/').pop();
      if (cleanHref) {
        const targetEl = renderArea.querySelector(`[data-href$="${cleanHref}"]`);
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: 'auto', block: 'start' });
          restored = true;
          console.log('[Viewer-Epub-Scroll] Position restored via scrollIntoView:', cleanHref);
          // 복원된 실제 위치의 비율을 계산하여 시크바와 동기화
          const totalScroll = container.scrollHeight - container.clientHeight;
          if (totalScroll > 0) {
            updateProgressPercent((container.scrollTop / totalScroll) * 100);
          }
        }
      }
    }

    if (!restored) {
      const totalScroll = container.scrollHeight - container.clientHeight;
      container.scrollTop = Math.max(0, totalScroll * ratio);
      updateProgressPercent(ratio * 100);
      console.log('[Viewer-Epub-Scroll] Position restored via fallback ratio:', ratio);
    }
  }, 100);

  return contentEl;
}
