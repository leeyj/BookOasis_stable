export function stripLeadingBracketTags(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';

  // Remove leading tags like [Author] or {Group} while preserving the original value fallback.
  const stripped = raw.replace(/^\s*(?:(?:\[[^\]]+\]|\{[^}]+\})\s*)+/u, '').trim();
  return stripped || raw;
}

/**
 * 썸네일 아래 제목 말줄임 시 권수(01권, v02, #3 등) 및 후반부 식별자가 잘리지 않도록
 * 중간을 말줄임(Middle Truncation)해 주는 헬퍼 함수
 * @param {string} title - 원본 제목
 * @param {number} maxLen - 노출할 최대 글자 수 (기본값 12)
 * @returns {string} 중간 생략 처리된 제목
 */
export function middleTruncateTitle(title, maxLen = 8) {
  const str = String(title || '').trim();
  if (!str || str.length <= maxLen) return str;

  // 권수/숫자/에피소드/확장자 형태 패턴 탐지 (예: 01권, 01, v2, #3, 05화, 33p 등)
  const volMatch = str.match(/(?:\d{1,4}\s*권|\d{1,4}\s*화|v(?:ol\.?)?\s*\d+|#\d+|\b\d{1,4}[a-z]?\b)$/i);

  if (volMatch && volMatch[0]) {
    const volStr = volMatch[0].trim();
    const prefixLen = Math.max(2, maxLen - volStr.length - 1);
    if (str.length > (prefixLen + volStr.length)) {
      return `${str.substring(0, prefixLen)}..${volStr}`;
    }
  }

  // 기본 중간 말줄임 (예: 앞 3자..뒤 3자)
  const frontLen = Math.max(2, Math.floor((maxLen - 2) / 2));
  const backLen = maxLen - 2 - frontLen;
  return `${str.substring(0, frontLen)}..${str.substring(str.length - backLen)}`;
}

