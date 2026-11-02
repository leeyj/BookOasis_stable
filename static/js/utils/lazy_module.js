// lazy_module.js – 홈 화면에 필요 없는 모듈(뷰어·상세·설정·플레이어 등)을 처음 쓸 때 불러오는 도우미 (2.9.5)
//
// 홈 진입 때 ES 모듈 134개를 한꺼번에 받아 HTTP/1.1(연결 6개)에서 줄이 생겼다(느린 회선 DCL 6.7초).
// import()는 호출한 모듈 기준으로 경로를 풀기 때문에 로더 함수는 호출하는 쪽에서 만든다:
//   const loadViewer = lazyModule(() => import('../viewer.js'));
//   (await loadViewer()).openReader(...)

function notifyLoadFailure() {
  try {
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('common.module_load_failed'), 'error');
    }
  } catch (e) {}
}

// 한 번만 불러오고(같은 Promise 공유), 실패하면 한 번 다시 시도한다 - 모바일 불안정 회선에서
// 동적 import 실패가 관측됐다(2026-10-10). 그래도 실패하면 다음 호출 때 다시 시도할 수 있게 비워 둔다.
export function lazyModule(loader) {
  let promise = null;
  let loadedModule = null;
  const load = () => {
    if (!promise) {
      promise = loader()
        .catch(() => loader())
        .then((mod) => {
          loadedModule = mod;
          return mod;
        })
        .catch((err) => {
          promise = null;
          console.error('[lazyModule] 모듈 불러오기 실패:', err);
          notifyLoadFailure();
          throw err;
        });
    }
    return promise;
  };
  // 이미 불러온 모듈(없으면 null) - "아직 안 불러왔으면 할 일이 없다"는 호출(닫기·진행률 저장 등)에 쓴다
  load.peek = () => loadedModule;
  return load;
}

// 인라인 onclick·다른 모듈이 부르는 window 함수를 부팅 때부터 유지한다. 처음 호출되면 모듈을 불러온 뒤
// 같은 이름의 실제 함수(모듈 export 또는 모듈이 스스로 등록한 window 함수)로 바꿔 끼우고 호출한다.
export function bindLazyGlobals(load, names) {
  names.forEach((name) => {
    if (typeof window[name] === 'function') return;
    const stub = async (...args) => {
      const mod = await load();
      const real = typeof mod[name] === 'function' ? mod[name] : window[name];
      if (typeof real !== 'function' || real === stub) {
        console.warn(`[lazyModule] '${name}' 함수를 찾지 못했습니다.`);
        return undefined;
      }
      window[name] = real;
      return real(...args);
    };
    window[name] = stub;
  });
}

// 첫 화면을 그린 뒤 브라우저가 한가할 때 실행 (미리 받기·부팅 후 부작용 모듈용)
export function whenIdle(fn, timeout = 2000) {
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(() => fn(), { timeout });
  } else {
    setTimeout(fn, 200);
  }
}
