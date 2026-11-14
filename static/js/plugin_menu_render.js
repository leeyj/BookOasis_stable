// plugin_menu_render.js – 컨텍스트 메뉴(도서/하이라이트)의 플러그인 항목을 플러그인별 그룹으로 그린다.
// 예전에는 book_menu/plugin_items.js와 viewer/annotation_context_menu.js에 같은 코드가 따로 있었다.
// label/icon은 플러그인이 보내는 값이라 텍스트/클래스로만 넣는다(HTML로 해석하지 않는다).

const PLUGIN_ITEM_SELECTOR = '.plugin-context-menu-item, .plugin-context-menu-group-title, .plugin-context-menu-separator';

/** 플러그인 ID에서 고정된 강조색을 만든다 (같은 플러그인은 항상 같은 색). */
export function getPluginAccentColor(pluginId) {
  const text = String(pluginId || 'plugin');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash |= 0;
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 72% 60%)`;
}

export function clearPluginMenuItems(listEl) {
  if (!listEl) return;
  listEl.querySelectorAll(PLUGIN_ITEM_SELECTOR).forEach((el) => el.remove());
}

/**
 * listEl 안의 '.context-menu-close-item' 앞(없으면 끝)에 플러그인 항목을 그룹별로 넣는다.
 * @param {HTMLElement} listEl - '.context-menu-list'
 * @param {Array} items - [{plugin_id, plugin_name, id, label, icon}]
 * @param {(pluginId: string, actionId: string) => void} onItemClick
 */
export function renderPluginMenuGroups(listEl, items, onItemClick) {
  if (!listEl) return;
  clearPluginMenuItems(listEl);
  if (!Array.isArray(items) || items.length === 0) return;

  const closeItem = listEl.querySelector('.context-menu-close-item');
  const insert = (el) => {
    if (closeItem) listEl.insertBefore(el, closeItem);
    else listEl.appendChild(el);
  };

  const groups = new Map();
  items.forEach((item) => {
    const pluginId = String(item.plugin_id || '').trim();
    if (!pluginId) return;
    const pluginName = String(item.plugin_name || pluginId).trim();
    if (!groups.has(pluginId)) groups.set(pluginId, { pluginId, pluginName, items: [] });
    groups.get(pluginId).items.push(item);
  });

  Array.from(groups.values()).forEach((group, groupIdx) => {
    const accentColor = getPluginAccentColor(group.pluginId);

    if (groupIdx > 0) {
      const sep = document.createElement('li');
      sep.className = 'plugin-context-menu-separator';
      insert(sep);
    }

    const titleEl = document.createElement('li');
    titleEl.className = 'plugin-context-menu-group-title';
    titleEl.style.setProperty('--plugin-accent', accentColor);
    titleEl.textContent = group.pluginName;
    insert(titleEl);

    group.items.forEach((item) => {
      const pluginId = String(item.plugin_id || '').trim();
      const actionId = String(item.id || '').trim();
      const label = String(item.label || '').trim();
      if (!pluginId || !actionId || !label) return;

      const li = document.createElement('li');
      li.className = 'context-menu-item plugin-context-menu-item';
      li.dataset.pluginId = pluginId;
      li.dataset.actionId = actionId;
      li.style.setProperty('--plugin-accent', accentColor);

      const icon = document.createElement('i');
      icon.className = `${window.boIcon(String(item.icon || 'lc lc-puzzle').trim())} plugin-context-menu-icon`;
      const labelEl = document.createElement('span');
      labelEl.className = 'plugin-context-menu-label';
      labelEl.textContent = label;
      li.append(icon, ' ', labelEl);

      li.addEventListener('click', () => onItemClick(pluginId, actionId));
      insert(li);
    });
  });
}
