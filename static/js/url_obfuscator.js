// url_obfuscator.js – 상세 뷰 URL 파라미터 난독화 및 디코딩 모듈

/**
 * 상세 페이지 파라미터 객체를 URL-safe Base64 난독화 토큰으로 인코딩합니다.
 * @param {Object} params { series, libraryId, repBookId, displayTitle }
 * @returns {string} 난독화된 쿼리 스트링 (예: "v=c2VyaWVzP...")
 */
export function encodeDetailParams(params) {
  if (!params || !params.series) return '';
  
  try {
    const payload = {
      s: params.series || '',
      l: params.libraryId || 'all',
      r: params.repBookId || null,
      d: params.displayTitle || null,
      t: params.type || null
    };
    
    const jsonStr = JSON.stringify(payload);
    // UTF-8 인코딩 후 Base64 변환
    const utf8Bytes = new TextEncoder().encode(jsonStr);
    let binary = '';
    utf8Bytes.forEach(b => binary += String.fromCharCode(b));
    const base64 = btoa(binary);
    // URL-safe 변환 (+ -> -, / -> _, = 삭제)
    const urlSafe = base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    return `v=${urlSafe}`;
  } catch (e) {
    console.error('[URL-Obfuscator] Encode failed:', e);
    // Fallback: 인코딩 실패 시 명시적 파라미터 사용
    return `series=${encodeURIComponent(params.series || '')}&libraryId=${encodeURIComponent(params.libraryId || 'all')}&type=${encodeURIComponent(params.type || '')}`;
  }
}

/**
 * URL 해시 또는 쿼리 스트링에서 파라미터 객체를 디코딩하여 복원합니다.
 * 기존 ?series=... 명시적 파라미터도 100% 하위 호환합니다.
 * @param {string} hashString window.location.hash
 * @returns {Object} { series, libraryId, repBookId, displayTitle, type }
 */
export function decodeDetailParams(hashString) {
  if (!hashString || !hashString.includes('?')) return {};
  
  const queryString = hashString.split('?')[1] || '';
  if (!queryString) return {};

  const urlParams = new URLSearchParams(queryString);
  const token = urlParams.get('v');

  // 1) v=... 난독화 토큰 복원
  if (token) {
    try {
      // URL-safe Base64 복원
      let base64 = token.replace(/-/g, '+').replace(/_/g, '/');
      while (base64.length % 4 !== 0) {
        base64 += '=';
      }
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const jsonStr = new TextDecoder().decode(bytes);
      const payload = JSON.parse(jsonStr);

      return {
        series: payload.s || '',
        libraryId: payload.l || 'all',
        repBookId: payload.r || null,
        displayTitle: payload.d || null,
        type: payload.t || null
      };
    } catch (e) {
      console.warn('[URL-Obfuscator] Token decode failed, fallbacking:', e);
    }
  }

  // 2) 하위 호환: 기존 ?series=... 명시적 파라미터 복원
  const series = urlParams.get('series') ? decodeURIComponent(urlParams.get('series')) : '';
  const libraryId = urlParams.get('libraryId') ? decodeURIComponent(urlParams.get('libraryId')) : 'all';
  const repBookId = urlParams.get('repBookId') ? decodeURIComponent(urlParams.get('repBookId')) : null;
  const displayTitle = urlParams.get('displayTitle') ? decodeURIComponent(urlParams.get('displayTitle')) : null;
  const type = urlParams.get('type') ? decodeURIComponent(urlParams.get('type')) : null;

  return {
    series,
    libraryId,
    repBookId,
    displayTitle,
    type
  };
}

if (typeof window !== 'undefined') {
  window.encodeDetailParams = encodeDetailParams;
  window.decodeDetailParams = decodeDetailParams;
}
