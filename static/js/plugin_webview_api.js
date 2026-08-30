// plugin_webview_api.js – 플러그인이 사용하는 외부 도메인 웹뷰/다운로드 공개 API
//
// 앱은 어떤 외부 도메인도 기본 제공/추천하지 않는다. 여기서 열거나 다운로드하는 모든 URL은
// 사용자가 [설정 > 외부 도메인] 탭에서 직접 등록한 화이트리스트 안에서만 허용되며,
// 최종 검증은 항상 서버(api/routes/plugin_webview_routes.py)가 수행한다 — 아래 클라이언트
// 사전 체크는 왕복 없이 빠른 안내를 보여주기 위한 UX용일 뿐, 보안 경계가 아니다.

let cachedWhitelistPatterns = null;

async function loadWhitelistCache() {
  if (cachedWhitelistPatterns) return cachedWhitelistPatterns;
  try {
    const res = await fetch('/api/webview/whitelist');
    const data = await res.json();
    if (data.success) {
      cachedWhitelistPatterns = (data.domains || []).map(d => d.pattern);
    }
  } catch (e) {
    console.error('[PluginWebview] 화이트리스트 조회 실패:', e);
  }
  return cachedWhitelistPatterns || [];
}

export function invalidateWebviewWhitelistCache() {
  cachedWhitelistPatterns = null;
}
window.invalidateWebviewWhitelistCache = invalidateWebviewWhitelistCache;

function hostMatchesWhitelist(host, patterns) {
  if (!host) return false;
  host = host.toLowerCase();
  return (patterns || []).some(pattern => {
    pattern = String(pattern).toLowerCase();
    if (pattern.startsWith('*.')) {
      const apex = pattern.slice(2);
      return host !== apex && host.endsWith(pattern.slice(1));
    }
    return host === pattern;
  });
}

function extractHost(url) {
  try {
    const u = new URL(url);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    return u.hostname;
  } catch (e) {
    return null;
  }
}

function showWhitelistPrompt(url) {
  const host = extractHost(url) || url;
  // 정확히 어떤 호스트가 막혔는지 보여준다 — 예: apex(example.com)만 등록해둔 상태에서
  // www.example.com처럼 서브도메인이 요청되면 별개 호스트로 취급되어 거부되는데,
  // 이 사실이 안 보이면 사용자가 뭘 더 등록해야 할지 알 수 없다.
  const message = `허용 목록에 없는 도메인입니다: ${host}\n설정 > 외부 도메인 탭에서 추가해주세요. (서브도메인까지 포함하려면 *.도메인 형태로 등록)`;
  if (typeof window.showToast === 'function') {
    window.showToast(message, 'error');
  }
  console.warn(`[PluginWebview] ${message}`);
}

function ensureWebviewModal() {
  let modal = document.getElementById('plugin-webview-modal');
  if (modal) return modal;

  modal = document.createElement('div');
  modal.id = 'plugin-webview-modal';
  modal.style.cssText = `
    display: none; position: fixed; inset: 0; z-index: 100000;
    background: rgba(0, 0, 0, 0.7); align-items: center; justify-content: center;
  `;
  modal.innerHTML = `
    <div style="width: min(1000px, 92vw); height: min(760px, 88vh); background: #0f172a;
                border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; overflow: hidden;
                display: flex; flex-direction: column;">
      <div style="display: flex; align-items: center; justify-content: space-between;
                  padding: 0.6rem 1rem; background: rgba(30,41,59,0.9); border-bottom: 1px solid rgba(255,255,255,0.08);">
        <span id="plugin-webview-modal-title" style="color: #cbd5e1; font-size: 0.85rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"></span>
        <button type="button" data-role="plugin-webview-close" style="background: none; border: none; color: #94a3b8; font-size: 1.2rem; cursor: pointer; padding: 0 0.3rem;">✕</button>
      </div>
      <div id="plugin-webview-modal-body" style="flex: 1; position: relative; background: #fff;">
        <iframe id="plugin-webview-iframe" style="width: 100%; height: 100%; border: none;"></iframe>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  modal.addEventListener('click', (event) => {
    if (event.target === modal || event.target.closest('[data-role="plugin-webview-close"]')) {
      closeWebviewModal();
    }
  });

  return modal;
}

function closeWebviewModal() {
  const modal = document.getElementById('plugin-webview-modal');
  if (!modal) return;
  modal.style.display = 'none';
  const iframe = document.getElementById('plugin-webview-iframe');
  if (iframe) iframe.src = 'about:blank';
}

/**
 * 플러그인이 외부 URL을 앱 내 모달(서버 프록시 경유)로 연다.
 * @param {string} url - 열려는 대상 URL (사용자가 화이트리스트에 등록한 도메인이어야 함)
 */
export async function openWebview(url) {
  const host = extractHost(url);
  if (!host) {
    if (typeof window.showToast === 'function') window.showToast('URL 형식이 올바르지 않습니다.', 'error');
    return;
  }

  const patterns = await loadWhitelistCache();
  if (!hostMatchesWhitelist(host, patterns)) {
    showWhitelistPrompt(url);
    return;
  }

  const proxyUrl = `/api/webview/proxy?url=${encodeURIComponent(url)}`;

  // 서버 응답을 먼저 프로브해서 JSON 에러 바디를 확인한다 (iframe src만으로는 에러를 못 봄).
  try {
    const probe = await fetch(proxyUrl);
    if (!probe.ok) {
      let message = '외부 페이지를 불러오지 못했습니다.';
      try {
        const errData = await probe.json();
        message = errData.message || message;
      } catch (e) { /* JSON이 아니면 기본 메시지 사용 */ }
      if (typeof window.showToast === 'function') window.showToast(message, 'error');
      return;
    }
  } catch (e) {
    if (typeof window.showToast === 'function') window.showToast('외부 페이지 요청 중 오류가 발생했습니다.', 'error');
    return;
  }

  const modal = ensureWebviewModal();
  const titleEl = document.getElementById('plugin-webview-modal-title');
  if (titleEl) titleEl.textContent = url;
  const iframe = document.getElementById('plugin-webview-iframe');
  if (iframe) iframe.src = proxyUrl;
  modal.style.display = 'flex';
}

/**
 * 화이트리스트 검증 후 일반 프록시(`/api/webview/proxy`) URL 문자열을 돌려준다.
 * 모달을 띄우지 않고 텍스트/JSON 등 작은 리소스를 직접 fetch()하려는 플러그인용.
 * 응답은 15MB로 캡되므로 미디어 스트림에는 쓰지 말 것 — 그 경우 getStreamProxyUrl()을 쓴다.
 * @param {string} url
 * @returns {Promise<string|null>} 화이트리스트에 없거나 URL이 잘못됐으면 null(토스트로 안내)
 */
export async function getProxyUrl(url) {
  const host = extractHost(url);
  if (!host) {
    if (typeof window.showToast === 'function') window.showToast('URL 형식이 올바르지 않습니다.', 'error');
    return null;
  }
  const patterns = await loadWhitelistCache();
  if (!hostMatchesWhitelist(host, patterns)) {
    showWhitelistPrompt(url);
    return null;
  }
  return `/api/webview/proxy?url=${encodeURIComponent(url)}`;
}

/**
 * 화이트리스트 검증 후 HLS/스트림 프록시(`/api/webview/hls-proxy`) URL 문자열을 돌려준다.
 * .m3u8 플레이리스트는 서버가 내부 세그먼트 URL까지 전부 프록시 경유로 재작성해서 돌려주고,
 * 세그먼트(.ts 등)는 버퍼링 없이 그대로 스트리밍된다 — hls.js/mpegts.js/<video src>에 그대로
 * 넘기면 된다. https로 서빙되는 페이지에서 http 스트림을 재생할 때(mixed-content 회피)나
 * 스트림 서버가 CORS를 안 열어준 경우에 이 함수를 쓴다.
 * @param {string} url
 * @returns {Promise<string|null>} 화이트리스트에 없거나 URL이 잘못됐으면 null(토스트로 안내)
 */
export async function getStreamProxyUrl(url) {
  const host = extractHost(url);
  if (!host) {
    if (typeof window.showToast === 'function') window.showToast('URL 형식이 올바르지 않습니다.', 'error');
    return null;
  }
  const patterns = await loadWhitelistCache();
  if (!hostMatchesWhitelist(host, patterns)) {
    showWhitelistPrompt(url);
    return null;
  }
  return `/api/webview/hls-proxy?url=${encodeURIComponent(url)}`;
}

/**
 * 방송사 로고처럼 도메인이 제각각인 외부 이미지를 <img src>에 바로 넣을 수 있는 로컬 캐시
 * URL로 바꿔준다. 화이트리스트 검증을 요구하지 않는다(사설 IP만 서버에서 차단) — 매번
 * 원본을 다시 받지 않도록 서버가 최초 1회만 WebP로 캐싱해서 이후엔 로컬 파일을 서빙한다.
 * http(s) URL이 아니면(빈 값, 상대경로, "None" 등 원본 소스의 placeholder 문자열) null을 반환한다.
 * @param {string} url
 * @returns {string|null}
 */
export function getCachedImageUrl(url) {
  const host = extractHost(url);
  if (!host) return null;
  return `/api/webview/logo-cache?url=${encodeURIComponent(url)}`;
}

/**
 * 플러그인이 외부 URL의 파일을 지정한 라이브러리로 다운로드+임포트한다.
 * @param {string} url
 * @param {{libraryId: number|string, dbType?: string}} options
 */
export async function downloadToLibrary(url, options = {}) {
  const host = extractHost(url);
  if (!host) {
    if (typeof window.showToast === 'function') window.showToast('URL 형식이 올바르지 않습니다.', 'error');
    return { success: false, error: 'invalid_url' };
  }
  if (!options.libraryId) {
    if (typeof window.showToast === 'function') window.showToast('다운로드 대상 라이브러리가 지정되지 않았습니다.', 'error');
    return { success: false, error: 'missing_library_id' };
  }

  const patterns = await loadWhitelistCache();
  if (!hostMatchesWhitelist(host, patterns)) {
    showWhitelistPrompt(url);
    return { success: false, error: 'not_whitelisted' };
  }

  if (typeof window.showToast === 'function') window.showToast('다운로드를 시작합니다...', 'info');

  try {
    const res = await fetch('/api/webview/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url,
        library_id: options.libraryId,
        db_type: options.dbType || 'general'
      })
    });
    const data = await res.json();

    if (!res.ok || !data.success) {
      if (typeof window.showToast === 'function') window.showToast(data.message || '다운로드에 실패했습니다.', 'error');
      return data;
    }

    if (!data.imported_as_book) {
      if (typeof window.showToast === 'function') window.showToast('파일은 저장되었지만 지원되는 도서 형식이 아니어서 목록에 표시되지 않습니다.', 'error');
    } else if (data.scan_error) {
      if (typeof window.showToast === 'function') window.showToast('다운로드는 완료됐지만 자동 스캔에 실패했습니다. 수동 스캔을 실행해주세요.', 'error');
    } else {
      if (typeof window.showToast === 'function') window.showToast(`"${data.filename}" 다운로드 및 등록이 완료되었습니다.`, 'success');
    }
    return data;
  } catch (e) {
    if (typeof window.showToast === 'function') window.showToast('다운로드 요청 중 오류가 발생했습니다.', 'error');
    return { success: false, error: 'request_failed' };
  }
}

window.BookOasisPlugin = window.BookOasisPlugin || {};
window.BookOasisPlugin.openWebview = openWebview;
window.BookOasisPlugin.downloadToLibrary = downloadToLibrary;
window.BookOasisPlugin.getProxyUrl = getProxyUrl;
window.BookOasisPlugin.getStreamProxyUrl = getStreamProxyUrl;
window.BookOasisPlugin.getCachedImageUrl = getCachedImageUrl;
