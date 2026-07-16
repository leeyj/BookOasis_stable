export function renderEpubTocPanel({ tocList, txtChunks, onJumpToChapter }) {
  let container = document.getElementById('epub-toc-container');
  let btn = document.getElementById('epub-toc-btn');

  if (!container) {
    container = document.createElement('div');
    container.id = 'epub-toc-container';
    container.className = 'epub-toc-container';
    container.style.cssText = `
      position: fixed;
      top: 0;
      right: -320px;
      width: 300px;
      height: 100%;
      background: var(--bg-color, #1e1e1e);
      color: var(--text-color, #d4d4d4);
      box-shadow: -2px 0 12px rgba(0,0,0,0.5);
      transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      z-index: 9999;
      overflow-y: auto;
      padding: 20px;
      box-sizing: border-box;
      border-left: 1px solid rgba(255,255,255,0.1);
    `;
    document.body.appendChild(container);
  }

  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'epub-toc-btn';
    btn.innerHTML = '<i class="fas fa-list"></i>';
    btn.style.cssText = `
      position: fixed;
      top: 90px;
      right: 20px;
      z-index: 10000;
      background: rgba(0,0,0,0.6);
      color: white;
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 50%;
      width: 44px;
      height: 44px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      backdrop-filter: blur(4px);
      transition: transform 0.2s, background 0.2s;
    `;
    btn.onmouseover = () => {
      btn.style.transform = 'scale(1.05)';
    };
    btn.onmouseout = () => {
      btn.style.transform = 'scale(1)';
    };
    btn.onclick = () => {
      const isClosed = container.style.right.startsWith('-');
      container.style.right = isClosed ? '0px' : '-320px';
    };
    document.body.appendChild(btn);
  }

  const headerEl = document.createElement('h3');
  headerEl.style.cssText = 'margin-top:0; margin-bottom:20px; font-weight:600; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;';
  headerEl.textContent = '목차';

  const ul = document.createElement('ul');
  ul.style.cssText = 'list-style:none; padding:0; margin:0; font-size:0.95rem;';

  const buildItem = (title, chapterIdx, anchor, paddingLeft) => {
    const li = document.createElement('li');
    li.style.cssText = `padding-left:${paddingLeft}px; margin-bottom:12px; line-height:1.4;`;
    const a = document.createElement('a');
    a.href = '#';
    a.style.cssText = 'color:inherit; text-decoration:none; display:block; opacity:0.85; transition:opacity 0.2s;';
    a.textContent = title;
    a.addEventListener('mouseover', () => {
      a.style.opacity = '1';
    });
    a.addEventListener('mouseout', () => {
      a.style.opacity = '0.85';
    });
    a.addEventListener('click', e => {
      e.preventDefault();
      onJumpToChapter(chapterIdx, anchor);
    });
    li.appendChild(a);
    return li;
  };

  if (tocList && tocList.length > 0) {
    tocList.forEach(item => {
      ul.appendChild(buildItem(item.title, item.chapter_idx, item.anchor || '', (item.level - 1) * 16));
    });
  } else {
    txtChunks.forEach((_, idx) => {
      ul.appendChild(buildItem(`청크 ${idx + 1}`, idx, '', 0));
    });
  }

  container.innerHTML = '';
  container.appendChild(headerEl);
  container.appendChild(ul);
}

export function jumpToTxtTocChapter({
  chapterIdx,
  anchor,
  chunkCount,
  setCurrentChunkIdx,
  getScrollMode,
  getScrollWrapper,
  renderCurrentChunk,
  saveProgress,
  activeBookId,
}) {
  if (chapterIdx < 0 || chapterIdx >= chunkCount) return;

  const container = document.getElementById('epub-toc-container');
  if (container) container.style.right = '-320px';

  setCurrentChunkIdx(chapterIdx);

  const scrollMode = getScrollMode();
  if (scrollMode === 'scroll') {
    const scrollWrapper = getScrollWrapper();
    const ratio = chapterIdx / chunkCount;
    if (scrollWrapper) {
      scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
    }
  } else {
    renderCurrentChunk(true);
  }

  saveProgress(activeBookId, chapterIdx, chunkCount);

  if (anchor) {
    setTimeout(() => {
      const targetEl = document.getElementById(anchor);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth' });
      }
    }, 100);
  }
}
