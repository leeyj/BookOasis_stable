// kind_manager.js – 카테고리 속성(만화/도서/잡지 등) 종류 관리 모달 (관리자 전용)
//
// 속성 목록은 세션(general/adult/...)마다 따로 있고, 라이브러리 목록 응답(kinds)으로 state.libraryKinds에 실려 온다.
// 여기서 추가/이름 변경/삭제를 하면 다시 받아서 목록과 라이브러리 모달의 선택지를 갱신한다.
import { state } from '../state.js';
import * as api from '../api.js';
import { buildKindListHtml } from './kind_options.js';

function t(key, fallback) {
  const translated = window.i18n?.t?.(key);
  return translated && translated !== key ? translated : fallback;
}

function getModal() {
  return document.getElementById('library-kinds-modal');
}

function renderKindList() {
  const list = document.getElementById('library-kinds-list');
  if (!list) return;
  list.innerHTML = buildKindListHtml(state.libraryKinds, {
    rename: t('modal.content_kind_rename', '이름 변경'),
    remove: t('modal.content_kind_delete', '삭제'),
    builtin: t('modal.content_kind_builtin', '기본'),
    empty: t('modal.content_kind_empty', '등록된 속성이 없습니다.'),
  });
}

async function refreshKinds() {
  const data = await api.fetchLibraries(state.currentLibraryType);
  if (data && data.success) state.libraryKinds = Array.isArray(data.kinds) ? data.kinds : [];
  renderKindList();
  window.dispatchEvent(new CustomEvent('library:kinds-changed'));
}

export async function openKindManager() {
  const modal = getModal();
  if (!modal) return;
  modal.style.display = 'flex';
  renderKindList();
  try {
    await refreshKinds();
  } catch (error) {
    console.warn('[KindManager] 속성 목록 조회 실패:', error);
  }
}

export function closeKindManager() {
  const modal = getModal();
  if (modal) modal.style.display = 'none';
}

function buildForm(fields) {
  const formData = new FormData();
  formData.append('type', state.currentLibraryType);
  Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
  return formData;
}

async function submitResult(request) {
  try {
    const result = await request();
    if (!result?.success) {
      alert(result?.error || t('modal.content_kind_failed', '속성을 저장하지 못했습니다.'));
      return false;
    }
    await refreshKinds();
    return true;
  } catch (error) {
    console.error('[KindManager] 요청 실패:', error);
    alert(t('modal.content_kind_failed', '속성을 저장하지 못했습니다.'));
    return false;
  }
}

async function addKind(form) {
  const code = form.querySelector('[name="code"]').value.trim();
  const name = form.querySelector('[name="name"]').value.trim();
  const saved = await submitResult(() => api.addLibraryKind(buildForm({ code, name })));
  if (saved) form.reset();
}

async function renameKind(code) {
  const kind = (state.libraryKinds || []).find((item) => item.code === code);
  if (!kind) return;
  const name = prompt(t('modal.content_kind_rename_prompt', '속성 이름을 입력하세요.'), kind.name || '');
  if (name === null) return;
  await submitResult(() => api.editLibraryKind(buildForm({ code, name: name.trim() })));
}

async function deleteKind(code) {
  const kind = (state.libraryKinds || []).find((item) => item.code === code);
  if (!kind) return;
  const message = t('modal.content_kind_delete_confirm', "'{name}' 속성을 삭제할까요?").replace('{name}', kind.name || code);
  if (!confirm(message)) return;
  await submitResult(() => api.deleteLibraryKind(buildForm({ code })));
}

function bindKindManager() {
  if (typeof document === 'undefined' || window.__kindManagerBound) return;
  window.__kindManagerBound = true;

  document.addEventListener('click', (event) => {
    const target = event?.target?.closest?.(
      '[data-role="library-manage-kinds"], [data-role="library-kinds-close"], [data-role="library-kind-rename"], [data-role="library-kind-delete"]'
    );
    if (!target) return;
    event.preventDefault();
    event.stopPropagation();
    const role = target.getAttribute('data-role');
    const code = target.getAttribute('data-kind-code') || '';
    if (role === 'library-manage-kinds') return openKindManager();
    if (role === 'library-kinds-close') return closeKindManager();
    if (role === 'library-kind-rename') return renameKind(code);
    if (role === 'library-kind-delete') return deleteKind(code);
  }, true);

  document.addEventListener('submit', (event) => {
    const form = event?.target;
    if (!form || form.id !== 'library-kinds-add-form') return;
    event.preventDefault();
    event.stopPropagation();
    addKind(form);
  }, true);
}

bindKindManager();
