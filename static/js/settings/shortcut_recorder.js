// shortcut_recorder.js - 도서관 검색 단축키 녹화 UI 및 임시 상태 보관
// 임시 상태(tempShortcut)는 loadGeneralSettings()가 localStorage에서 읽어 채우고,
// submitGeneralSettings()가 저장 시점에 다시 읽어가므로 getter/setter로 노출한다.
let tempShortcut = null;
let isRecordingShortcut = false;

export function getTempShortcut() {
  return tempShortcut;
}

export function setTempShortcut(value) {
  tempShortcut = value;
}

// 단축키 레코더 이벤트 리스너 바인딩 헬퍼
export function initShortcutRecorderEvents() {
  const btnRecord = document.getElementById('btn-record-shortcut');
  const btnReset = document.getElementById('btn-reset-shortcut');
  const displayEl = document.getElementById('setting-search-shortcut-display');
  if (!btnRecord || !btnReset || !displayEl) return;

  if (btnRecord.__bound) return;
  btnRecord.__bound = true;

  btnRecord.addEventListener('click', () => {
    if (isRecordingShortcut) return;
    isRecordingShortcut = true;
    btnRecord.innerText = '입력 대기...';
    displayEl.value = '원하는 단축키 조합을 누르세요...';

    const onKeyDown = (e) => {
      e.preventDefault();
      e.stopPropagation();

      const isModifierOnly = ['control', 'alt', 'shift', 'meta'].includes(e.key.toLowerCase());

      const parts = [];
      if (e.ctrlKey) parts.push('Ctrl');
      if (e.altKey) parts.push('Alt');
      if (e.shiftKey) parts.push('Shift');
      if (e.metaKey) parts.push('Win');

      if (isModifierOnly) {
        displayEl.value = parts.join(' + ') + ' + ...';
      } else {
        let keyDisplay = e.key;
        if (e.code === 'Space') keyDisplay = 'Space';
        else if (e.code === 'Backquote') keyDisplay = '`';
        else if (keyDisplay.length === 1) keyDisplay = keyDisplay.toUpperCase();

        parts.push(keyDisplay);
        const finalDisplay = parts.join(' + ');

        tempShortcut = {
          ctrlKey: e.ctrlKey,
          altKey: e.altKey,
          shiftKey: e.shiftKey,
          metaKey: e.metaKey,
          key: e.key,
          code: e.code,
          display: finalDisplay
        };

        displayEl.value = finalDisplay;

        // 대기 종료
        isRecordingShortcut = false;
        btnRecord.innerText = '기록 시작';
        window.removeEventListener('keydown', onKeyDown, true);
      }
    };

    window.addEventListener('keydown', onKeyDown, true);
  });

  btnReset.addEventListener('click', () => {
    if (isRecordingShortcut) return;
    tempShortcut = { ctrlKey: false, altKey: true, shiftKey: false, metaKey: false, key: '`', code: 'Backquote', display: 'Alt + `' };
    displayEl.value = tempShortcut.display;
  });
}
