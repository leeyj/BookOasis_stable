// script_loader.js – 전역(클래식) 라이브러리를 필요할 때 불러오는 도우미 (2.9.5)
//
// jszip(98KB)·pdf.js(287KB)는 홈 첫 화면에 필요 없는데 매번 받아 느린 회선에서 첫 화면이 늦었다.
//   - pdf.js: PDF를 열 때(viewer_pdf.js)
//   - jszip: 코어는 쓰지 않지만 플러그인이 window.JSZip을 쓸 수 있어(공식 플러그인 59개) 첫 화면 뒤 한가할 때 불러오고,
//            플러그인 코드에 JSZip/pdfjsLib 이름이 있으면 그 코드를 실행하기 전에 먼저 불러온다(withPluginGlobals).
// 주소(버전 쿼리 포함)는 템플릿이 window.__BO_LIB_URLS로 넘긴다(tab_media_library.html).

const pending = new Map();

function libUrl(name, fallback) {
  const urls = window.__BO_LIB_URLS || {};
  return urls[name] || fallback;
}

export function loadScriptOnce(src) {
  if (pending.has(src)) return pending.get(src);
  const promise = new Promise((resolve, reject) => {
    const el = document.createElement('script');
    el.src = src;
    el.async = true;
    el.onload = () => resolve();
    el.onerror = () => {
      pending.delete(src); // 다음 호출 때 다시 시도
      el.remove();
      reject(new Error(`script load failed: ${src}`));
    };
    document.head.appendChild(el);
  });
  pending.set(src, promise);
  return promise;
}

export async function ensureJSZip() {
  if (!window.JSZip) await loadScriptOnce(libUrl('jszip', '/static/lib/jszip/jszip.min.js'));
  return window.JSZip;
}

const PDFJS_FALLBACK = '/static/lib/pdfjs-6.4.299/pdf.min.mjs';
let pdfJsPromise = null;

// pdf.js 6.x는 ES 모듈이라 import()로 불러온다. 플러그인이 예전처럼 전역 pdfjsLib을 쓸 수 있게 window에도 둔다.
export async function ensurePdfJs() {
  if (!pdfJsPromise) {
    pdfJsPromise = import(libUrl('pdfjs', PDFJS_FALLBACK)).then((mod) => {
      window.pdfjsLib = mod;
      mod.GlobalWorkerOptions.workerSrc = libUrl('pdfjsWorker', '/static/lib/pdfjs-6.4.299/pdf.worker.min.mjs');
      return mod;
    }).catch((err) => {
      pdfJsPromise = null; // 다음 호출 때 다시 시도
      throw err;
    });
  }
  return pdfJsPromise;
}

// cmaps/standard_fonts/wasm/iccs가 들어 있는 pdf.js 폴더 주소(끝에 /)
export function pdfJsAssetBase() {
  return libUrl('pdfjs', PDFJS_FALLBACK).split('?')[0].replace(/[^/]+$/, '');
}

// 플러그인 코드(new Function으로 실행)가 예전처럼 미리 로드된 전역을 기대해도 동작하게 한다.
// 필요한 전역이 이미 있거나 쓰지 않으면 지금처럼 바로(동기) 실행하고, 없을 때만 불러온 뒤 실행한다.
export function withPluginGlobals(source, run) {
  const src = String(source || '');
  const needs = [];
  if (!window.JSZip && /\bJSZip\b/.test(src)) needs.push(ensureJSZip());
  if (!window.pdfjsLib && /\bpdfjsLib\b/.test(src)) needs.push(ensurePdfJs());
  if (!needs.length) return run();
  return Promise.all(needs)
    .catch((err) => console.error('[script_loader] 플러그인용 라이브러리 불러오기 실패:', err))
    .then(() => run());
}
