export function renderTxtChunkView({
  contentArea,
  txtChunks,
  currentChunkIdx,
  scrollMode,
  isEpub,
  initMode,
  formatTxtToHtml,
  emptyText,
}) {
  if (!contentArea) return false;

  if (!Array.isArray(txtChunks) || txtChunks.length === 0) {
    contentArea.textContent = emptyText || '';
    return false;
  }

  if (isEpub) {
    contentArea.style.whiteSpace = 'normal';
    contentArea.style.wordBreak = 'break-word';
  } else {
    contentArea.style.whiteSpace = 'normal';
    contentArea.style.wordBreak = 'break-all';
  }

  if (scrollMode === 'page') {
    if (isEpub) {
      contentArea.innerHTML = `<div class="txt-chunk epub-chunk" data-idx="${currentChunkIdx}" style="height: 100%; box-sizing: border-box;">${txtChunks[currentChunkIdx]}</div>`;
    } else {
      const htmlContent = formatTxtToHtml(txtChunks[currentChunkIdx]);
      contentArea.innerHTML = `<div class="txt-chunk" data-idx="${currentChunkIdx}" style="height: 100%; box-sizing: border-box;">${htmlContent}</div>`;
    }
  } else if (initMode || !contentArea.querySelector('.txt-full-content')) {
    if (isEpub) {
      const wrapped = txtChunks
        .map((ch, idx) => `<div class="txt-scroll-chunk" data-idx="${idx}" style="margin-bottom: 3rem;">${ch}</div>`)
        .join('');
      contentArea.innerHTML = `<div class="txt-full-content epub-full-content">${wrapped}</div>`;
    } else {
      const wrapped = txtChunks
        .map((ch, idx) => `<div class="txt-scroll-chunk" data-idx="${idx}" style="margin-bottom: 3rem;">${formatTxtToHtml(ch)}</div>`)
        .join('');
      contentArea.innerHTML = `<div class="txt-full-content">${wrapped}</div>`;
    }
  }

  return true;
}

export function applyTxtParagraphStyles({ contentArea, localStorage, currentViewerFormat }) {
  if (!contentArea) return;

  const savedParagraphSpacing = localStorage.getItem('viewer_paragraph_spacing') || '1.0';
  const pSpacingRem = parseFloat(savedParagraphSpacing);
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';

  if (currentViewerFormat === 'epub') {
    contentArea.querySelectorAll('img').forEach(img => {
      img.style.maxHeight = scrollMode === 'page' ? '70vh' : '85vh';
      img.style.maxWidth = '100%';
      img.style.objectFit = 'contain';
    });
  }

  contentArea
    .querySelectorAll('p, div.txt-chunk > div, div.txt-full-content > div, h1, h2, h3, h4, h5, h6, blockquote, ul, ol, li, hr, ruby, rt, rp, sup, sub')
    .forEach(el => {
      const tag = el.tagName.toLowerCase();
      if (tag.startsWith('h')) {
        el.style.marginBottom = `${pSpacingRem * 1.5}rem`;
        el.style.marginTop = '1.5rem';
        el.style.fontWeight = 'bold';
      } else if (tag === 'ul' || tag === 'ol') {
        el.style.marginTop = '0';
        el.style.marginBottom = `${pSpacingRem}rem`;
        el.style.paddingLeft = '1.4rem';
      } else if (tag === 'li') {
        el.style.marginTop = '0';
        el.style.marginBottom = `${Math.max(0.2, pSpacingRem * 0.45)}rem`;
      } else if (tag === 'blockquote') {
        el.style.marginTop = '0';
        el.style.marginBottom = `${pSpacingRem}rem`;
        el.style.paddingLeft = '0.9rem';
        el.style.borderLeft = '3px solid rgba(148, 163, 184, 0.45)';
        el.style.opacity = '0.95';
      } else if (tag === 'hr') {
        el.style.marginTop = `${pSpacingRem}rem`;
        el.style.marginBottom = `${pSpacingRem}rem`;
      } else {
        el.style.marginBottom = `${pSpacingRem}rem`;
        el.style.marginTop = '0';
      }
    });
}
