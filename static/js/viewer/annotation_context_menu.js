// annotation_context_menu.js — 하이라이트(주석) 우클릭/롱프레스 컨텍스트 메뉴.
// static/js/book_context_menu.js의 플러그인 항목 로드/렌더/실행 패턴을 그대로 따르되,
// 도서 카드 대신 개별 하이라이트(annotation)를 대상으로 한다. 플러그인은
// get_annotation_context_menu_items()/run_annotation_context_menu_action()을 구현해서
// (docs/guide_plugins.md 참고) 옵시디언/노션 등으로의 내보내기 같은 기능을 자유롭게
// 붙일 수 있다 — 이 프로젝트는 훅과 API만 제공하고 실제 연동은 커뮤니티 플러그인에 맡긴다.
import { state } from '../state.js';
import * as api from '../api.js';
import { positionMenuAtPoint, hideFloatingMenu, isFloatingMenuOpen, enableMenuDrag } from '../context_menu_manager.js';
import { setAnnotationMarker } from './annotation_anchor.js';
import { updateAnnotationLocal } from './annotation_state.js';
import { clearPluginMenuItems, renderPluginMenuGroups } from '../plugin_menu_render.js';

const MENU_ID = 'annotation-context-menu';
let currentTarget = null; // 현재 메뉴가 열려 있는 annotation 객체
let contextMenuLoadSeq = 0;
let deleteHandler = null;

export function configureAnnotationContextMenu({ onDelete }) {
  deleteHandler = onDelete;
}

function getModalRoot() {
  return document.getElementById('media-viewer-modal') || document.body;
}

function ensureMenu() {
  let menu = document.getElementById(MENU_ID);
  if (menu) return menu;

  menu = document.createElement('div');
  menu.id = MENU_ID;
  menu.className = 'context-menu';
  menu.style.display = 'none';
  menu.innerHTML = `
    <div class="context-menu-header">
      <span class="context-menu-header-left">
        <span class="context-menu-drag-handle" data-role="annotation-context-drag" title="${i18n.t('viewer.menu_move')}" aria-hidden="true"><i class="lc lc-grip-horizontal"></i></span>
        <span class="context-menu-title">${i18n.t('viewer.highlight_menu')}</span>
      </span>
      <button type="button" class="context-menu-close-btn" data-role="annotation-context-close" aria-label="${i18n.t('common.close')}"><span class="context-menu-close-icon">&times;</span><span class="context-menu-close-text">${i18n.t('common.close')}</span></button>
    </div>
    <ul class="context-menu-list">
      <li class="context-menu-item" data-role="annotation-context-delete"><i class="lc lc-trash" style="color: #f87171;"></i> <span>${i18n.t('viewer.highlight_delete')}</span></li>
      <li class="context-menu-item context-menu-close-item" data-role="annotation-context-close"><i class="lc lc-x" style="color: #f87171;"></i> <span>${i18n.t('common.close')}</span></li>
    </ul>
  `;
  getModalRoot().appendChild(menu);

  menu.querySelectorAll('[data-role="annotation-context-close"]').forEach((el) => {
    el.addEventListener('click', hideAnnotationContextMenu);
  });
  menu.querySelector('[data-role="annotation-context-delete"]').addEventListener('click', () => {
    const target = currentTarget;
    hideAnnotationContextMenu();
    if (target && typeof deleteHandler === 'function') deleteHandler(target.id);
  });

  enableMenuDrag(menu, menu.querySelector('[data-role="annotation-context-drag"]'));

  return menu;
}

function getMenuList() {
  const menu = document.getElementById(MENU_ID);
  return menu ? menu.querySelector('.context-menu-list') : null;
}

function clearPluginItems() {
  clearPluginMenuItems(getMenuList());
}

function renderPluginItems(items) {
  renderPluginMenuGroups(getMenuList(), items, triggerAnnotationPluginAction);
}

function buildContext(annotation) {
  const titleEl = document.getElementById('viewer-title-text');
  return {
    annotation_id: annotation.id,
    book_id: state.activeBookId,
    book_title: titleEl ? titleEl.textContent.trim() : '',
    format: annotation.format,
    chapter_idx: annotation.chapter_idx,
    quote: annotation.quote,
    note: annotation.note,
    color: annotation.color,
  };
}

async function loadPluginItems() {
  if (!currentTarget) {
    clearPluginItems();
    return;
  }
  const seq = ++contextMenuLoadSeq;
  try {
    const res = await api.fetchAnnotationContextMenuPluginItems(state.currentLibraryType, buildContext(currentTarget));
    if (seq !== contextMenuLoadSeq) return;
    if (res && res.success) {
      renderPluginItems(res.items || []);
      return;
    }
    clearPluginItems();
  } catch (err) {
    console.error('[Annotation-ContextMenu] plugin item load failed:', err);
    if (seq === contextMenuLoadSeq) clearPluginItems();
  }
}

export function showAnnotationContextMenu(x, y, annotation) {
  if (!annotation) return;
  currentTarget = annotation;
  const menu = ensureMenu();
  positionMenuAtPoint(menu, x, y, { zIndex: 20060 });
  loadPluginItems();
}

export function hideAnnotationContextMenu() {
  hideFloatingMenu(MENU_ID);
  currentTarget = null;
  contextMenuLoadSeq += 1;
  clearPluginItems();
}

export function isAnnotationContextMenuOpen() {
  return isFloatingMenuOpen(MENU_ID);
}

// 실제 액션 1회 호출. extraContext는 프롬프트 왕복 시 사용자가 입력한 값(prompt_value)을
// 실어 보내기 위한 것 — 플러그인은 이 값의 유무로 "처음 호출"과 "입력 받은 뒤 재호출"을 구분한다.
//
// [popup 프리오픈 안 쓰는 이유] book_context_menu.js는 모든 호출이 곧바로 최종 실행이라
// window.open('', '_blank')로 미리 빈 창을 띄워두는 팝업 차단 회피 트릭이 안전하다. 하지만
// 여기서는 클릭 한 번이 'prompt' 요청(입력창만 띄우고 끝, open_url 없음)으로 끝나는 경우가
// 흔해서(예: 이미 메모가 있는 하이라이트 우클릭 → "메모 보기·수정") 그 트릭을 그대로 쓰면
// 빈 탭이 열렸다가 곧바로 닫히는 게 매번 눈에 보이는 문제가 있었다. 그래서 open_url이 실제로
// 온 뒤에만 새 탭을 연다 — 아주 느린 플러그인 액션에서는 브라우저 팝업 차단에 걸릴 수 있지만
// (동일 출처 fetch 응답을 기다리는 짧은 시간 안에는 대부분 문제 없음), 매번 깜빡이는 탭보다는
// 훨씬 나은 절충이다.
async function executeAnnotationAction(pluginId, actionId, target, extraContext) {
  try {
    const context = { ...buildContext(target), ...extraContext };
    const res = await api.runAnnotationContextMenuPluginAction(state.currentLibraryType, pluginId, actionId, context);

    const vm = await import('../view_manager.js');
    if (!res || !res.success) {
      vm.showToast(res && res.error ? res.error : i18n.t('context_menu.plugin_action_failed'), 'error');
      return;
    }

    // 플러그인이 사용자 입력이 더 필요하다고 응답한 경우: 모달로 입력을 받아 같은 액션을
    // prompt_value와 함께 재호출한다.
    if (res.prompt) {
      const { showPluginPromptModal } = await import('./plugin_prompt_modal.js');
      const value = await showPluginPromptModal(res.prompt);
      if (value === null) return; // 사용자가 취소
      await executeAnnotationAction(pluginId, actionId, target, { ...extraContext, prompt_value: value });
      return;
    }

    if (res.open_url) {
      // 프리오픈 트릭 없이 응답 직후 바로 여는 구조라, 아주 느린 플러그인 액션(외부 API 호출 등)
      // 에서는 브라우저가 "클릭과 무관한 팝업"으로 판단해 차단할 수 있다. 그 경우 아무 반응도
      // 없이 조용히 실패하지 않도록 최소한 에러 토스트로는 알려준다.
      const opened = window.open(res.open_url, '_blank');
      if (!opened) {
        vm.showToast(i18n.t('context_menu.popup_blocked'), 'error');
      }
    }

    // 플러그인이 응답에 'marker' 키를 넣었으면(코어가 이미 DB에 영속화한 뒤이므로)
    // 화면도 즉시 반영한다 — 새로고침/페이지 재진입 없이 방금 저장한 표시가 바로 보이게.
    if ('marker' in res) {
      updateAnnotationLocal(target.id, { plugin_marker: res.marker || null });
      setAnnotationMarker(document, target.id, res.marker);
    }

    if (res.message) vm.showToast(res.message, 'success');
  } catch (e) {
    console.error('[Annotation-ContextMenu] plugin action failed', e);
  }
}

async function triggerAnnotationPluginAction(pluginId, actionId) {
  if (!pluginId || !actionId || !currentTarget) return;
  const target = currentTarget;
  hideAnnotationContextMenu(); // 항목을 고른 순간 메뉴는 바로 닫는다 (프롬프트 모달은 별개 레이어)
  await executeAnnotationAction(pluginId, actionId, target, {});
}
