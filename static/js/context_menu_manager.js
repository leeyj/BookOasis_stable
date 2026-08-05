function resolveMenuElement(menuOrId) {
  if (!menuOrId) return null;
  if (typeof menuOrId === 'string') {
    return document.getElementById(menuOrId);
  }
  return menuOrId;
}

function clampToViewport(value, maxValue) {
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