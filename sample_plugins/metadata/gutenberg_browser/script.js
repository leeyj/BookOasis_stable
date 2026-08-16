// gutenberg_browser 플러그인 풀페이지 스크립트
// new Function('pluginId', 'container', ...)로 실행되므로 import 없이 window 전역 API만 사용 가능.

(function () {
  const openBtn = container.querySelector('#gb-open-webview-btn');
  const downloadBtn = container.querySelector('#gb-download-btn');
  const urlInput = container.querySelector('#gb-download-url');
  const librarySelect = container.querySelector('#gb-library-select');
  const statusEl = container.querySelector('#gb-download-status');

  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.textContent = text || '';
    statusEl.style.color = isError ? '#ef4444' : '';
  }

  async function loadLibraries() {
    if (!librarySelect) return;
    try {
      const res = await fetch('/api/media/libraries?type=general');
      const data = await res.json();
      if (data.success && Array.isArray(data.libraries)) {
        data.libraries.forEach(lib => {
          const opt = document.createElement('option');
          opt.value = lib.id;
          opt.textContent = lib.name;
          librarySelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.error('[GutenbergBrowser] 라이브러리 목록 로드 실패:', e);
    }
  }

  if (openBtn) {
    openBtn.addEventListener('click', () => {
      if (window.BookOasisPlugin && typeof window.BookOasisPlugin.openWebview === 'function') {
        window.BookOasisPlugin.openWebview('https://www.gutenberg.org/');
      } else {
        console.error('[GutenbergBrowser] window.BookOasisPlugin.openWebview API를 찾을 수 없습니다.');
      }
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener('click', async () => {
      const url = urlInput ? urlInput.value.trim() : '';
      const libraryId = librarySelect ? librarySelect.value : '';

      if (!url) {
        setStatus('다운로드할 URL을 입력해주세요.', true);
        return;
      }
      if (!libraryId) {
        setStatus('대상 라이브러리를 선택해주세요.', true);
        return;
      }
      if (!window.BookOasisPlugin || typeof window.BookOasisPlugin.downloadToLibrary !== 'function') {
        setStatus('다운로드 API를 사용할 수 없습니다.', true);
        return;
      }

      setStatus('다운로드 중...');
      downloadBtn.disabled = true;
      try {
        const result = await window.BookOasisPlugin.downloadToLibrary(url, {
          libraryId,
          dbType: 'general'
        });
        if (result && result.success) {
          setStatus(`완료: ${result.filename}${result.imported_as_book ? ' (도서로 등록됨)' : ' (지원되지 않는 형식이라 도서로 등록되지 않음)'}`);
        } else {
          setStatus((result && (result.message || result.error)) || '다운로드에 실패했습니다.', true);
        }
      } catch (e) {
        setStatus('다운로드 요청 중 오류가 발생했습니다.', true);
      } finally {
        downloadBtn.disabled = false;
      }
    });
  }

  loadLibraries();
})();
