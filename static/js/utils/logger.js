// logger.js – 상태/흐름 디버그 로그를 매번 코드에 추가했다 지웠다 하지 않고, 레벨을 켜고
// 끄는 것만으로 필요할 때 볼 수 있게 하는 경량 로거.
//
// 대상: "prune 몇 건 처리, heightDelta 얼마" 같은 반복적으로 재발할 수 있는 버그를 다시
// 진단할 때 쓰는 상태/흐름 로그. 이런 건 debug 레벨로 코드에 영구히 남겨두고 평소엔 꺼둔다.
//
// 대상 아님: 특정 가설 하나를 검증하려고 그때그때 짜는 실험/계측 도구(예: 스크롤 속도
// 샘플러, ResizeObserver 프로파일러). 그런 건 목적을 다하면 레벨과 무관하게 코드에서
// 통째로 삭제한다 - 로그레벨로 감싸도 다음 세션엔 어차피 다른 가설이라 재사용되지 않는다.
//
// 브라우저 콘솔에서 레벨을 바꾸려면: setLogLevel('debug') 후 새로고침 없이 바로 반영됨
// (또는 localStorage.setItem('LOG_LEVEL', 'debug') 후 새로고침).

const LEVELS = { none: 0, error: 1, warn: 2, info: 3, debug: 4 };
const STORAGE_KEY = 'LOG_LEVEL';
const DEFAULT_LEVEL = 'warn'; // 평소엔 조용히 - 재현 중에만 debug로 올려서 켠다

function readStoredLevel() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw && Object.prototype.hasOwnProperty.call(LEVELS, raw.toLowerCase())) {
      return raw.toLowerCase();
    }
  } catch (e) {
    // localStorage 접근 불가 환경(시크릿 모드 제한 등) - 기본값 사용
  }
  return DEFAULT_LEVEL;
}

let currentLevel = readStoredLevel();

export function setLogLevel(level) {
  const normalized = String(level || '').toLowerCase();
  if (!Object.prototype.hasOwnProperty.call(LEVELS, normalized)) return;
  currentLevel = normalized;
  try {
    localStorage.setItem(STORAGE_KEY, normalized);
  } catch (e) {
    // 무시 - 이번 세션 동안만이라도 currentLevel은 이미 반영됨
  }
}

export function getLogLevel() {
  return currentLevel;
}

function shouldLog(level) {
  return LEVELS[level] <= LEVELS[currentLevel];
}

/**
 * 모듈별 태그가 붙은 로거를 만든다.
 * 예: const log = createLogger('grid_pruning');
 *     log.debug('prune', {...}) -> debug 레벨일 때만 "[grid_pruning] prune {...}" 출력
 */
export function createLogger(tag) {
  const prefix = `[${tag}]`;
  return {
    error: (...args) => { if (shouldLog('error')) console.error(prefix, ...args); },
    warn: (...args) => { if (shouldLog('warn')) console.warn(prefix, ...args); },
    info: (...args) => { if (shouldLog('info')) console.log(prefix, ...args); },
    debug: (...args) => { if (shouldLog('debug')) console.log(prefix, ...args); },
  };
}

if (typeof window !== 'undefined') {
  window.setLogLevel = setLogLevel;
}
