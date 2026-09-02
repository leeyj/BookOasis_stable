function resolveMenuElement(menuOrId) {
  if (!menuOrId) return null;
  if (typeof menuOrId === 'string') {
    return document.getElementById(menuOrId);
  }
  return menuOrId;
}

export function clampToViewport(value, maxValue) {
  if (value < 0) return 0;
  if (value > maxValue) return Math.max(0, maxValue);
  return value;
}

export function ensureFloatingMenu(menuOrId, { zIndex = 20000 } = {}) {
  const menuEl = resolveMenuElement(menuOrId);
  if (!menuEl) return null;

  if (menuEl.parentElement !== document.body) {
    document.body.appendChild(menuEl);
  }

  menuEl.style.position = 'fixed';
  menuEl.style.zIndex = String(zIndex);
  menuEl.style.pointerEvents = 'auto';
  menuEl.style.visibility = 'visible';
  menuEl.style.opacity = '1';
  return menuEl;
}

export function hideFloatingMenu(menuOrId) {
  const menuEl = resolveMenuElement(menuOrId);
  if (!menuEl) return;
  menuEl.style.display = 'none';
}

export function hideAllContextMenus({ except = [] } = {}) {
  const exceptSet = new Set((Array.isArray(except) ? except : [except])
    .map((item) => resolveMenuElement(item))
    .filter(Boolean));

  document.querySelectorAll('.context-menu').forEach((menuEl) => {
    if (exceptSet.has(menuEl)) return;
    menuEl.style.display = 'none';
  });
}

export function isFloatingMenuOpen(menuOrId) {
  const menuEl = resolveMenuElement(menuOrId);
  return !!menuEl && menuEl.style.display !== 'none';
}

export function positionMenuAtPoint(menuOrId, x, y, { zIndex = 20000 } = {}) {
  const menuEl = ensureFloatingMenu(menuOrId, { zIndex });
  if (!menuEl) return null;

  hideAllContextMenus({ except: [menuEl] });

  menuEl.style.display = 'block';

  const menuHeight = menuEl.offsetHeight || 180;
  const menuWidth = menuEl.offsetWidth || 160;

  let targetX = Number.isFinite(x) ? x : 0;
  let targetY = Number.isFinite(y) ? y : 0;

  if (targetY + menuHeight > window.innerHeight) {
    targetY -= menuHeight;
  }
  if (targetX + menuWidth > window.innerWidth) {
    targetX -= menuWidth;
  }

  targetX = clampToViewport(targetX, window.innerWidth - menuWidth);
  targetY = clampToViewport(targetY, window.innerHeight - menuHeight);

  menuEl.style.left = `${targetX}px`;
  menuEl.style.top = `${targetY}px`;
  return menuEl;
}

export function positionMenuAtElement(menuOrId, anchorEl, { zIndex = 20000 } = {}) {
  if (!anchorEl || typeof anchorEl.getBoundingClientRect !== 'function') return null;

  const rect = anchorEl.getBoundingClientRect();
  const menuEl = ensureFloatingMenu(menuOrId, { zIndex });
  if (!menuEl) return null;

  hideAllContextMenus({ except: [menuEl] });

  menuEl.style.display = 'block';

  const menuHeight = menuEl.offsetHeight || 180;
  const menuWidth = menuEl.offsetWidth || 160;

  let targetX = rect.left;
  let targetY = rect.bottom;

  if (rect.bottom + menuHeight > window.innerHeight) {
    targetY = rect.top - menuHeight;
  }
  if (rect.left + menuWidth > window.innerWidth) {
    targetX = rect.right - menuWidth;
  }

  targetX = clampToViewport(targetX, window.innerWidth - menuWidth);
  targetY = clampToViewport(targetY, window.innerHeight - menuHeight);

  menuEl.style.left = `${targetX}px`;
  menuEl.style.top = `${targetY}px`;
  return menuEl;
}

// 그립 버튼(handleOrId)을 잡고 드래그하면 대상 요소(menuOrId) 전체가 따라 움직이게 한다.
// context_menu_manager가 관리하는 fixed 플로팅 메뉴뿐 아니라, flexbox 등으로 auto-배치된
// 임의의 패널(예: 뷰어 오버레이 컨트롤 패널)에도 그대로 쓸 수 있다 — 첫 드래그 시점에
// 현재 화면 위치를 fixed 좌표로 굳힌 뒤 그 위에서 delta만 더한다.
// setPointerCapture로 포인터를 핸들에 고정해두기 때문에, 드래그 후 손을 뗀 지점이 메뉴 바깥이어도
// 그 시점의 click 이벤트의 target은 여전히 핸들(메뉴 내부)로 잡혀 bindFloatingMenuOutsideClose 등
// 바깥-클릭 감지 로직이 오작동(드래그 직후 메뉴가 즉시 닫힘)하지 않는다.
export function enableMenuDrag(menuOrId, handleOrId) {
  const menuEl = resolveMenuElement(menuOrId);
  const handleEl = resolveMenuElement(handleOrId);
  if (!menuEl || !handleEl) return;
  if (menuEl.dataset.dragBound === '1') return;
  menuEl.dataset.dragBound = '1';

  let dragging = false;
  let pointerId = null;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  const onPointerMove = (event) => {
    if (!dragging || event.pointerId !== pointerId) return;
    const menuWidth = menuEl.offsetWidth;
    const menuHeight = menuEl.offsetHeight;
    const nextLeft = clampToViewport(startLeft + (event.clientX - startX), window.innerWidth - menuWidth);
    const nextTop = clampToViewport(startTop + (event.clientY - startY), window.innerHeight - menuHeight);
    menuEl.style.left = `${nextLeft}px`;
    menuEl.style.top = `${nextTop}px`;
  };

  const endDrag = (event) => {
    if (!dragging) return;
    dragging = false;
    handleEl.classList.remove('is-dragging');
    if (pointerId !== null && handleEl.releasePointerCapture) {
      try { handleEl.releasePointerCapture(pointerId); } catch (e) { /* 이미 해제된 경우 무시 */ }
    }
    pointerId = null;
    document.removeEventListener('pointermove', onPointerMove);
    document.removeEventListener('pointerup', endDrag);
    document.removeEventListener('pointercancel', endDrag);
  };

  handleEl.addEventListener('pointerdown', (event) => {
    if (event.button !== undefined && event.button !== 0) return; // 마우스 좌클릭/터치만
    dragging = true;
    pointerId = event.pointerId;
    startX = event.clientX;
    startY = event.clientY;
    const rect = menuEl.getBoundingClientRect();
    // flexbox 등으로 auto-배치되던 요소(예: 뷰어 오버레이 패널)도 첫 드래그 시점에
    // 화면상 현재 위치를 그대로 굳혀 fixed 좌표로 전환한다 — 안 그러면 left/top을
    // 아무리 바꿔도 static/relative 배치에 눌려 시각적으로 움직이지 않는다.
    const computedPosition = window.getComputedStyle(menuEl).position;
    if (computedPosition !== 'fixed' && computedPosition !== 'absolute') {
      menuEl.style.position = 'fixed';
      menuEl.style.margin = '0';
    }
    startLeft = rect.left;
    startTop = rect.top;
    menuEl.style.left = `${startLeft}px`;
    menuEl.style.top = `${startTop}px`;
    handleEl.classList.add('is-dragging');
    if (handleEl.setPointerCapture) {
      try { handleEl.setPointerCapture(pointerId); } catch (e) { /* 캡처 실패 시 그냥 진행 */ }
    }
    document.addEventListener('pointermove', onPointerMove);
    document.addEventListener('pointerup', endDrag);
    document.addEventListener('pointercancel', endDrag);
    event.preventDefault();
  });
}

export function bindFloatingMenuOutsideClose(menuOrId, {
  eventTypes = ['click'],
  capture = true,
  shouldIgnoreEvent = null,
} = {}) {
  const menuEl = resolveMenuElement(menuOrId);
  if (!menuEl) return;

  const bindKey = `__outsideCloseBound:${eventTypes.join(',')}:${capture ? '1' : '0'}`;
  if (menuEl.dataset[bindKey] === '1') return;
  menuEl.dataset[bindKey] = '1';

  const listener = (event) => {
    const currentMenuEl = resolveMenuElement(menuOrId);
    if (!currentMenuEl || currentMenuEl.style.display === 'none') return;
    if (typeof shouldIgnoreEvent === 'function' && shouldIgnoreEvent(event)) return;
    if (event && event.target && currentMenuEl.contains(event.target)) return;
    currentMenuEl.style.display = 'none';
  };

  eventTypes.forEach((eventType) => {
    document.addEventListener(eventType, listener, capture);
  });
}