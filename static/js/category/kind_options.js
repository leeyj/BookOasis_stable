// kind_options.js – 카테고리 속성(content_kind) 선택지/목록 HTML을 만드는 순수 함수 (DOM을 직접 만지지 않음)
//
// 속성 이름은 관리자가 입력한 문자열이라 innerHTML에 넣기 전에 반드시 이스케이프한다.

export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export const UNSPECIFIED_KIND = 'unspecified';

/**
 * 라이브러리 모달의 속성 <select> 옵션. 첫 항목은 '미지정'(값 '')이고, 저장된 코드가 목록에 없으면(다른 DB에서
 * 옮겨 온 경우 등) 그 코드를 원문으로 보여 줘서 저장 시 값이 조용히 바뀌지 않게 한다.
 */
export function buildKindOptionsHtml(kinds, selectedCode = '', unspecifiedLabel = '미지정') {
  const selected = !selectedCode || selectedCode === UNSPECIFIED_KIND ? '' : String(selectedCode);
  const list = Array.isArray(kinds) ? kinds : [];
  const options = [`<option value=""${selected === '' ? ' selected' : ''}>${escapeHtml(unspecifiedLabel)}</option>`];
  list.forEach((kind) => {
    const code = String(kind.code ?? '');
    options.push(
      `<option value="${escapeHtml(code)}"${code === selected ? ' selected' : ''}>${escapeHtml(kind.name ?? code)}</option>`
    );
  });
  if (selected !== '' && !list.some((kind) => String(kind.code) === selected)) {
    options.push(`<option value="${escapeHtml(selected)}" selected>${escapeHtml(selected)}</option>`);
  }
  return options.join('');
}

/** 속성 관리 모달의 목록 행. 기본 속성은 삭제 버튼을 보여주지 않는다. */
export function buildKindListHtml(kinds, labels = {}) {
  const { rename = '이름 변경', remove = '삭제', builtin = '기본', empty = '등록된 속성이 없습니다.' } = labels;
  const list = Array.isArray(kinds) ? kinds : [];
  if (list.length === 0) return `<li class="library-kind-empty">${escapeHtml(empty)}</li>`;
  return list.map((kind) => {
    const code = escapeHtml(kind.code);
    const isBuiltin = Number(kind.is_builtin) === 1;
    return `<li class="library-kind-row" data-kind-code="${code}">`
      + `<span class="library-kind-name">${escapeHtml(kind.name)}</span>`
      + `<code class="library-kind-code">${code}</code>`
      + (isBuiltin ? `<span class="library-kind-badge">${escapeHtml(builtin)}</span>` : '')
      + '<span class="library-kind-actions">'
      + `<button type="button" class="library-kind-btn" data-role="library-kind-rename" data-kind-code="${code}">${escapeHtml(rename)}</button>`
      + (isBuiltin ? '' : `<button type="button" class="library-kind-btn library-kind-btn--danger" data-role="library-kind-delete" data-kind-code="${code}">${escapeHtml(remove)}</button>`)
      + '</span>'
      + '</li>';
  }).join('');
}
