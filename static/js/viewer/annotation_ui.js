// annotation_ui.js — "형광펜 모드" 토글 버튼(뷰어 우측 고정) + 선택→추가 플로팅 버튼
// + 하이라이트 클릭 삭제.
//
// 페이지 모드에서는 #common-viewer-hotspot(3분할 페이지 넘김 오버레이, z-index 10002)가
// 콘텐츠 전체를 덮고 있어 드래그 선택 자체가 시작되지 않는다(mousedown이 hotspot에서
// 끝나버림). 매 mousedown/touchstart마다 임시로 풀어주는 휴리스틱 대신, 사용자가
// "형광펜 모드"를 명시적으로 켜고 끄는 방식을 쓴다 — 켜져 있는 동안만 hotspot의
// pointer-events를 꺼서 선택/하이라이트 클릭이 콘텐츠에 닿게 하고, 끄면 원래 페이지
// 넘김 동작으로 복귀한다. 스크롤 모드는 원래 hotspot이 없어 문제 없었지만, 우발적
// 선택으로 팝업이 뜨는 걸 막기 위해 동일하게 모드 게이팅을 적용한다.
import { state } from '../state.js';
import { getViewerPlatformProfile } from './platform_profile.js';
import { positionMenuAtPoint, hideFloatingMenu } from '../context_menu_manager.js';
import { encodeRange, wrapRangeWithMark } from './annotation_anchor.js';
import { addAnnotationLocal, removeAnnotationLocal, getAnnotationById } from './annotation_state.js';
import { rawChunkStartOffset } from './annotation_render.js';
import {
  configureAnnotationContextMenu,
  showAnnotationContextMenu,
  hideAnnotationContextMenu,
} from './annotation_context_menu.js';

const BUTTON_ID = 'annotation-add-btn';
const TOGGLE_ID = 'annotation-mode-toggle';
const LONG_PRESS_MS = 500;
const LONG_PRESS_MOVE_THRESHOLD = 10;

let bound = false;
let getTxtChunksFn = () => [];
let pending = null; // { range, chunkEl }
let highlightModeActive = false;
let longPressTimer = null;
let longPressStartX = 0;
let longPressStartY = 0;
let suppressClickUntil = 0;

function getModalRoot() {
  return document.getElementById('media-viewer-modal') || document.body;
}

function ensureToggleButton() {
  let btn = document.getElementById(TOGGLE_ID);
  if (btn) return btn;
  btn = document.createElement('button');
  btn.id = TOGGLE_ID;
  btn.type = 'button';
  btn.title = '형광펜 모드 켜기/끄기';
  btn.textContent = '🖍️';
  btn.style.cssText = [
    // 우측 중앙에 크게 떠 있으면 태블릿 해상도에서 본문을 가려 읽기 방해가 크므로 작은
    // 아이콘으로 배치한다. 전체화면 닫기 버튼(.floating-close-btn: top 56px+safe-area,
    // right 20px+safe-area, 44px)과 "같은 줄 왼쪽"에 두면 74px만큼 안쪽으로 들어와
    // 실제 줄바꿈된 본문 텍스트 칼럼 한가운데를 덮어버린다(2026-08-22 실사용자 리포트로
    // 확인 — 모바일에서 글자를 가림). 텍스트가 거의 화면 끝까지 채워지더라도 줄바꿈
    // 특성상 가장 바깥쪽 우측 여백(닫기 버튼이 이미 쓰고 있는 그 자리)만큼은 거의 항상
    // 비어 있으므로, 닫기 버튼과 같은 right 값으로 "그 아래"에 세로로 쌓아 같은 안전
    // 여백을 재사용한다.
    'position:fixed', 'right:calc(20px + env(safe-area-inset-right, 0px))',
    'top:calc(108px + env(safe-area-inset-top, 0px))',
    'width:20px', 'height:20px', 'border-radius:50%', 'z-index:10004',
    'background:rgba(15,23,42,0.7)', 'border:1px solid rgba(255,255,255,0.15)',
    'color:#fff', 'font-size:0.7rem', 'cursor:pointer', 'backdrop-filter:blur(8px)',
    'display:flex', 'align-items:center', 'justify-content:center', 'transition:all 0.2s ease',
    'padding:0',
  ].join(';');
  getModalRoot().appendChild(btn);
  btn.addEventListener('click', () => setHighlightMode(!highlightModeActive));
  return btn;
}

function syncToggleButtonVisual() {
  const btn = document.getElementById(TOGGLE_ID);
  if (!btn) return;
  if (highlightModeActive) {
    btn.style.background = '#fbbf24';
    btn.style.borderColor = '#fbbf24';
    btn.style.color = '#1e293b';
    btn.style.boxShadow = '0 0 0 3px rgba(251,191,36,0.35)';
  } else {
    btn.style.background = 'rgba(15,23,42,0.7)';
    btn.style.borderColor = 'rgba(255,255,255,0.15)';
    btn.style.color = '#fff';
    btn.style.boxShadow = 'none';
  }
}

export function setHighlightMode(active) {
  // 모바일은 기능 자체가 비활성화 상태(initAnnotationSelectionUI에서 이벤트 바인딩을
  // 아예 건너뜀) — 실제로 켜져도 선택/추가/삭제가 하나도 안 먹는 반쪽짜리 상태가 되는
  // 걸 막기 위해, 켜는 시도 자체를 여기서 한 번 더 막는다(방어적 게이트).
  if (active && getViewerPlatformProfile().isMobileDevice) return;
  highlightModeActive = !!active;
  const hotspot = document.getElementById('common-viewer-hotspot');
  if (hotspot) hotspot.style.pointerEvents = highlightModeActive ? 'none' : 'auto';
  syncToggleButtonVisual();
  if (!highlightModeActive) {
    hideButton();
    hideAnnotationContextMenu();
    window.getSelection()?.removeAllRanges();
  }
  if (typeof window.showToast === 'function') {
    window.showToast(
      highlightModeActive ? '형광펜 모드 켜짐 — 텍스트를 드래그해 선택하세요' : '형광펜 모드 꺼짐',
      'info'
    );
  }
}

export function resetHighlightMode() {
  highlightModeActive = false;
  const hotspot = document.getElementById('common-viewer-hotspot');
  if (hotspot) hotspot.style.pointerEvents = 'auto';
  syncToggleButtonVisual();
  hideButton();
  hideAnnotationContextMenu();
}

export function toggleHighlightMode() {
  setHighlightMode(!highlightModeActive);
}
// input_controller.js의 키보드 핸들러(단축키 H)가 이 모듈을 직접 import하지 않고도
// 다른 뷰어 토글(window.toggleComicPageStep 등)과 동일한 관례로 호출할 수 있도록 노출.
window.toggleHighlightMode = toggleHighlightMode;

// 형광펜 모드는 TXT/EPUB 전용 기능(zip/cbz/pdf 등에는 hotspot을 풀어줄 텍스트 선택
// 대상 자체가 없음). 토글 버튼이 media-viewer-modal에 한 번 붙으면 이후 다른 포맷의
// 뷰어를 열어도 DOM에 그대로 남아있어(모달이 재사용됨) zip 뷰에서도 버튼이 뜬다는
// 커뮤니티 리포트로 확인됨 — 뷰어를 열 때마다 포맷에 맞춰 버튼 표시 여부를 동기화한다.
export function setAnnotationUiEnabled(enabled) {
  if (!enabled) resetHighlightMode();
  const btn = document.getElementById(TOGGLE_ID);
  if (btn) btn.style.display = enabled ? 'flex' : 'none';
}

function ensureButton() {
  let btn = document.getElementById(BUTTON_ID);
  if (btn) return btn;
  btn = document.createElement('button');
  btn.id = BUTTON_ID;
  btn.type = 'button';
  btn.className = 'context-menu';
  btn.textContent = '🖍️ 형광펜 추가';
  btn.style.cssText = [
    'display:none', 'padding:8px 14px', 'background:#1e293b', 'color:#fbbf24',
    'border:1px solid rgba(251,191,36,0.5)', 'border-radius:8px', 'font-size:0.85rem',
    'font-weight:600', 'cursor:pointer', 'box-shadow:0 4px 12px rgba(0,0,0,0.35)',
    'white-space:nowrap',
  ].join(';');
  getModalRoot().appendChild(btn);
  btn.addEventListener('click', onAddHighlightClick);
  return btn;
}

function hideButton() {
  hideFloatingMenu(BUTTON_ID);
  pending = null;
}

function findChunkEl(node) {
  const el = node && node.nodeType === 1 ? node : (node && node.parentElement);
  return el ? el.closest('.txt-chunk[data-idx], .txt-scroll-chunk[data-idx]') : null;
}

function isReaderOverlayOpen() {
  const menu = document.getElementById('comic-overlay-menu');
  return !!menu && menu.style.display !== 'none';
}

function handleSelectionEnd() {
  if (!highlightModeActive) return;
  // 선택이 브라우저 내부적으로 확정되기까지 짧은 지연 후 확인 (touchend 직후엔 아직 비어있는 경우 있음)
  setTimeout(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0 || sel.toString().trim().length === 0) {
      hideButton();
      return;
    }
    const range = sel.getRangeAt(0);
    const contentArea = document.getElementById('txt-content-area');
    if (!contentArea || !contentArea.contains(range.commonAncestorContainer)) {
      hideButton();
      return;
    }
    const chunkEl = findChunkEl(range.commonAncestorContainer);
    if (!chunkEl) {
      hideButton();
      return;
    }
    // 읽기 설정 오버레이(이동/보기/스타일/여백 패널)가 열려 있으면 그 위에 겹쳐
    // 보이는 게 오히려 시야를 가리므로, 오버레이가 열려 있는 동안은 띄우지 않는다.
    if (isReaderOverlayOpen()) {
      hideButton();
      return;
    }

    pending = { range: range.cloneRange(), chunkEl };
    const rect = range.getBoundingClientRect();
    const btn = ensureButton();
    // 선택 영역 "아래"에 띄운다. iOS/Android 네이티브 선택 툴바(복사/찾아보기 등)는
    // 공간이 있으면 항상 선택 위쪽에 뜨므로, 아래쪽에 두면 겹칠 확률이 훨씬 낮아진다.
    positionMenuAtPoint(btn, rect.left, rect.bottom + 10);
  }, 10);
}

async function onAddHighlightClick() {
  if (!pending) return;
  const { range, chunkEl } = pending;
  hideButton();

  const chunkIdx = parseInt(chunkEl.getAttribute('data-idx') || '-1', 10);
  const isEpub = state.currentViewerFormat === 'epub';
  const anchor = encodeRange(chunkEl, range);
  window.getSelection()?.removeAllRanges();
  if (!anchor || !Number.isFinite(chunkIdx)) return;

  let payload;
  if (isEpub) {
    payload = {
      format: 'epub', chapter_idx: chunkIdx,
      start_offset: anchor.start, end_offset: anchor.end,
      quote: anchor.quote, prefix: anchor.prefix, suffix: anchor.suffix,
    };
  } else {
    // TXT: 청크 로컬(렌더) 오프셋을 그 청크의 raw 시작 오프셋 기준 근사치로 변환해
    // "원본 파일 기준 글로벌 오프셋"으로 저장한다 (청킹 알고리즘이 나중에 바뀌어도
    // quote 검색 자가복구로 재발견 가능 — annotation_anchor.js 상단 설계 주석 참고).
    const chunkStartRaw = rawChunkStartOffset(getTxtChunksFn(), chunkIdx);
    payload = {
      format: 'txt', chapter_idx: null,
      start_offset: chunkStartRaw + anchor.start, end_offset: chunkStartRaw + anchor.end,
      quote: anchor.quote, prefix: anchor.prefix, suffix: anchor.suffix,
    };
  }

  const bookId = state.activeBookId;
  const dbType = state.currentLibraryType;
  try {
    const res = await fetch(`/api/v1/books/${bookId}/annotations?db_type=${dbType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data && data.success) {
      const created = { id: data.annotation_id, book_id: bookId, user_id: null, color: '#fbbf24', note: null, plugin_marker: null, ...payload };
      addAnnotationLocal(created);
      wrapRangeWithMark(range, { id: created.id, color: created.color });
    } else if (typeof window.showToast === 'function') {
      window.showToast(data && data.error ? data.error : '형광펜 추가에 실패했습니다.', 'error');
    }
  } catch (e) {
    console.error('[Annotation] create failed', e);
  }
}

async function deleteAnnotationById(annotationId) {
  if (!annotationId) return;
  const annotation = getAnnotationById(annotationId);
  const confirmMsg = annotation && annotation.note
    ? `이 하이라이트를 삭제할까요?\n메모: ${annotation.note}`
    : '이 하이라이트를 삭제할까요?';
  if (!window.confirm(confirmMsg)) return;

  const dbType = state.currentLibraryType;
  try {
    const res = await fetch(`/api/v1/annotations/${annotationId}?db_type=${dbType}`, { method: 'DELETE' });
    const data = await res.json();
    if (data && data.success) {
      removeAnnotationLocal(annotationId);
      // <mark>가 여러 텍스트 노드로 쪼개져 있을 수 있으므로 같은 id를 가진 모두를 제거
      document.querySelectorAll(`mark.annotation-highlight[data-annotation-id="${annotationId}"]`).forEach((el) => {
        const parent = el.parentNode;
        while (el.firstChild) parent.insertBefore(el.firstChild, el);
        parent.removeChild(el);
        parent.normalize();
      });
    }
  } catch (e) {
    console.error('[Annotation] delete failed', e);
  }
}

function onMarkClick(event) {
  if (!highlightModeActive) return;
  if (Date.now() < suppressClickUntil) return; // 방금 롱프레스로 컨텍스트 메뉴를 띄운 직후의 합성 클릭 무시
  const mark = event.target.closest('mark.annotation-highlight');
  if (!mark) return;
  const annotationId = mark.dataset.annotationId;
  if (!annotationId) return;
  event.preventDefault();
  event.stopPropagation();
  deleteAnnotationById(annotationId);
}

function onMarkContextMenu(event) {
  if (!highlightModeActive) return;
  const mark = event.target.closest('mark.annotation-highlight');
  if (!mark) return;
  event.preventDefault();
  event.stopPropagation();
  const annotation = getAnnotationById(mark.dataset.annotationId);
  if (annotation) showAnnotationContextMenu(event.clientX, event.clientY, annotation);
}

function clearLongPressTimer() {
  if (longPressTimer) {
    clearTimeout(longPressTimer);
    longPressTimer = null;
  }
}

function onMarkTouchStart(event) {
  if (!highlightModeActive) return;
  const mark = event.target.closest('mark.annotation-highlight');
  if (!mark) return;
  const touch = event.touches && event.touches[0];
  if (!touch) return;
  longPressStartX = touch.clientX;
  longPressStartY = touch.clientY;
  clearLongPressTimer();
  longPressTimer = setTimeout(() => {
    longPressTimer = null;
    const annotation = getAnnotationById(mark.dataset.annotationId);
    if (annotation) {
      showAnnotationContextMenu(touch.clientX, touch.clientY, annotation);
      suppressClickUntil = Date.now() + 400; // 롱프레스 후 이어지는 합성 click(삭제 확인) 억제
    }
  }, LONG_PRESS_MS);
}

function onMarkTouchMove(event) {
  if (!longPressTimer) return;
  const touch = event.touches && event.touches[0];
  if (!touch) return;
  const dx = Math.abs(touch.clientX - longPressStartX);
  const dy = Math.abs(touch.clientY - longPressStartY);
  if (dx > LONG_PRESS_MOVE_THRESHOLD || dy > LONG_PRESS_MOVE_THRESHOLD) clearLongPressTimer();
}

function onMarkTouchEnd() {
  clearLongPressTimer();
}

export function initAnnotationSelectionUI(getTxtChunks) {
  if (typeof getTxtChunks === 'function') getTxtChunksFn = getTxtChunks;
  resetHighlightMode();

  // 모바일에서는 형광펜 기능 자체를 비활성화한다. 항상 떠 있는 버튼(본문 가림) → 두
  // 손가락 탭(Android Chrome이 contextmenu로 가로채 신뢰성 없음) → 롱프레스(네이티브
  // 단어 선택 드래그와 충돌) 순으로 시도했지만 매번 새로운 사이드이펙트가 나와, 근본
  // 원인(모바일 터치 제스처 공간이 이미 OS 몸짓들로 꽉 차 있어 새 제스처를 안전하게
  // 얹을 자리가 없음)을 받아들이고 기능 자체를 끄기로 결정함(2026-08-22, 사용자 지시).
  // 데스크톱(마우스 우클릭 기반)은 이런 충돌이 없어 그대로 유지한다.
  if (getViewerPlatformProfile().isMobileDevice) return;

  configureAnnotationContextMenu({ onDelete: deleteAnnotationById });
  ensureToggleButton();
  if (bound) return;
  bound = true;

  document.addEventListener('mouseup', handleSelectionEnd);
  document.addEventListener('touchend', handleSelectionEnd);
  document.addEventListener('mousedown', (event) => {
    const btn = document.getElementById(BUTTON_ID);
    if (btn && !btn.contains(event.target)) hideButton();
    const menu = document.getElementById('annotation-context-menu');
    if (menu && !menu.contains(event.target)) hideAnnotationContextMenu();
  }, true);

  document.addEventListener('click', onMarkClick, true);
  // PC 우클릭: 형광펜 모드 중 하이라이트 위에서만 커스텀 메뉴(플러그인 항목 + 삭제)를 띄우고
  // 그 외에는(페이지 넘김 등) 브라우저 기본 컨텍스트 메뉴를 그대로 둔다.
  document.addEventListener('contextmenu', onMarkContextMenu, true);
  document.addEventListener('touchstart', onMarkTouchStart, { passive: true });
  document.addEventListener('touchmove', onMarkTouchMove, { passive: true });
  document.addEventListener('touchend', onMarkTouchEnd);

  // 선택 도중/직후에 읽기 설정 오버레이가 열리면(중앙 탭존 클릭 등) 겹쳐 보이지 않도록 즉시 숨김
  const overlayMenu = document.getElementById('comic-overlay-menu');
  if (overlayMenu && typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(() => {
      if (isReaderOverlayOpen()) {
        hideButton();
        hideAnnotationContextMenu();
      }
    });
    observer.observe(overlayMenu, { attributes: true, attributeFilter: ['style'] });
  }
}
