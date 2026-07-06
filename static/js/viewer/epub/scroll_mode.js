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
  isRunCurrent
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

  applyMergedThemeStyles(contentEl, theme, fontCSS, fontSize, lineHeight, paragraphSpacing);

  renderArea.appendChild(contentEl);

  requestAnimationFrame(() => {
    const totalScroll = container.scrollHeight - container.clientHeight;
    container.scrollTop = Math.max(0, totalScroll * ratio);
    updateProgressPercent(ratio * 100);
  });

  return contentEl;
}
