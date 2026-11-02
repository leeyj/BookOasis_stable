/* tab_collections.js - 사용자별 컬렉션(Collection) UI 렌더러 및 이벤트 매니저 */
import { state } from './state.js';
import { createBookCard } from './ui.js';
import { openBookDetail } from './modal.js';
import { resumeSeries } from './book_list.js';
import { openReader } from './viewer.js';

export async function renderCollectionsView() {
  const container = document.getElementById('books-list-container');
  const indicator = document.getElementById('current-category-indicator');
  const countBadge = document.getElementById('library-total-count');

  const scrollSpinner = document.getElementById('infinite-scroll-spinner');
  if (scrollSpinner) scrollSpinner.style.display = 'none';

  if (indicator) indicator.innerText = i18n.t('collections.indicator');

  if (!container) return;
  container.innerHTML = `
    <div style="grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
      <h3 style="margin:0; font-size:1.1rem; color: var(--app-text-primary); display:flex; align-items:center; gap:0.5rem;">
        <i class="fa-solid fa-bookmark" style="color: var(--app-accent);"></i> ${i18n.t('collections.list_title')}
      </h3>
      <button id="btn-create-collection-main" class="btn-toggle active" style="padding: 0.4rem 0.9rem; font-size: 0.88rem; background: var(--color-accent); color: var(--app-text-primary); border:none; border-radius:6px; cursor:pointer;">
        <i class="lc lc-plus"></i> ${i18n.t('collections.create_new')}
      </button>
    </div>
    <div id="collections-grid-list" style="grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1.2rem;">
      <div style="grid-column:1/-1; text-align:center; padding:3rem; color: var(--app-text-muted);"><i class="lc lc-loader-circle lc-spin"></i> ${i18n.t('collections.loading')}</div>
    </div>
  `;

  document.getElementById('btn-create-collection-main')?.addEventListener('click', () => {
    openCreateCollectionModal();
  });

  try {
    const res = await fetch(`/api/v1/collections?db_type=${state.currentLibraryType || 'general'}`);
    const data = await res.json();
    if (!data.success) {
      document.getElementById('collections-grid-list').innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:2rem;">${i18n.t('collections.error', { error: data.error })}</div>`;
      return;
    }

    const collections = data.collections || [];
    if (countBadge) countBadge.innerText = i18n.t('collections.count', { n: collections.length });

    if (collections.length === 0) {
      document.getElementById('collections-grid-list').innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 12px;">
          <i class="fa-solid fa-bookmark" style="font-size: 3rem; color: #475569; margin-bottom: 1rem;"></i>
          <h4 style="margin: 0 0 0.5rem 0; color: var(--app-text-muted);">${i18n.t('collections.empty_title')}</h4>
          <p style="color: var(--app-text-muted); font-size: 0.9rem; margin-bottom: 1.5rem;">${i18n.t('collections.empty_hint')}</p>
          <button onclick="document.getElementById('btn-create-collection-main').click()" class="btn-toggle active" style="padding: 0.5rem 1.2rem; font-size: 0.9rem; background: var(--color-accent); border:none; border-radius:6px; color: var(--app-text-primary); cursor:pointer;">
            <i class="lc lc-plus"></i> ${i18n.t('collections.create_first')}
          </button>
        </div>
      `;
      return;
    }

    let html = '';
    collections.forEach(coll => {
      const color = coll.color || '#7c3aed';
      html += `
        <div class="collection-card-item" data-coll-id="${coll.id}" style="background: rgba(var(--app-panel-rgb), 0.7); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 12px; padding: 1.2rem; cursor: pointer; transition: all 0.2s ease; position: relative; display: flex; flex-direction: column; justify-content: space-between;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.8rem;">
            <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: ${color};"></span>
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn-edit-coll" data-coll-id="${coll.id}" title="${i18n.t('collections.edit_title')}" style="background:transparent; border:none; color: var(--app-text-muted); cursor:pointer; font-size:0.85rem;"><i class="lc lc-pen"></i></button>
              <button class="btn-delete-coll" data-coll-id="${coll.id}" title="${i18n.t('collections.delete_title')}" style="background:transparent; border:none; color:#ef4444; cursor:pointer; font-size:0.85rem;"><i class="lc lc-trash-2"></i></button>
            </div>
          </div>
          <div>
            <h4 style="margin: 0 0 0.4rem 0; color: var(--app-text-primary); font-size: 1.05rem; word-break: break-word;">${escapeHtml(coll.name)}</h4>
            <p style="margin: 0; color: var(--app-text-muted); font-size: 0.82rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${coll.description ? escapeHtml(coll.description) : i18n.t('collections.no_description')}</p>
          </div>
          <div style="margin-top: 1.2rem; padding-top: 0.8rem; border-top: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: var(--app-text-muted);">
            <span><i class="lc lc-book" style="color:${color}; margin-right:0.3rem;"></i> ${i18n.t('collections.item_count', { n: coll.item_count || 0 })}</span>
            <span style="color: var(--color-accent); font-weight: 500;">${i18n.t('collections.open')} <i class="lc lc-chevron-right" style="font-size:0.75rem;"></i></span>
          </div>
        </div>
      `;
    });

    document.getElementById('collections-grid-list').innerHTML = html;

    // Attach click events
    document.querySelectorAll('.collection-card-item').forEach(card => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('.btn-edit-coll') || e.target.closest('.btn-delete-coll')) return;
        const collId = card.getAttribute('data-coll-id');
        renderCollectionDetail(collId);
      });
    });

    document.querySelectorAll('.btn-edit-coll').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const collId = btn.getAttribute('data-coll-id');
        const coll = collections.find(c => String(c.id) === String(collId));
        if (coll) openEditCollectionModal(coll);
      });
    });

    document.querySelectorAll('.btn-delete-coll').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const collId = btn.getAttribute('data-coll-id');
        if (confirm(i18n.t('collections.delete_confirm'))) {
          await deleteCollection(collId);
        }
      });
    });

  } catch (err) {
    document.getElementById('collections-grid-list').innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:2rem;">${i18n.t('collections.network_error', { error: err.message })}</div>`;
  }
}

export async function renderCollectionDetail(collectionId) {
  const container = document.getElementById('books-list-container');
  const indicator = document.getElementById('current-category-indicator');
  const countBadge = document.getElementById('library-total-count');

  const scrollSpinner = document.getElementById('infinite-scroll-spinner');
  if (scrollSpinner) scrollSpinner.style.display = 'none';

  if (!container) return;
  container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:3rem; color: var(--app-text-muted);"><i class="lc lc-loader-circle lc-spin"></i> ${i18n.t('collections.loading_detail')}</div>`;

  try {
    const res = await fetch(`/api/v1/collections/${collectionId}?db_type=${state.currentLibraryType || 'general'}`);
    const data = await res.json();
    if (!data.success) {
      container.innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:2rem;">${i18n.t('collections.error', { error: data.error })}</div>`;
      return;
    }

    const coll = data.collection;
    const items = coll.items || [];

    if (indicator) indicator.innerText = i18n.t('collections.indicator_named', { name: coll.name });
    if (countBadge) countBadge.innerText = i18n.t('collections.item_total', { n: items.length });

    container.innerHTML = '';

    const headerCard = document.createElement('div');
    headerCard.style.cssText = 'grid-column: 1 / -1; background: rgba(var(--app-panel-rgb), 0.5); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 12px; padding: 1.2rem 1.5rem; margin-bottom: 1.2rem;';
    headerCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
        <button id="btn-back-to-collections" class="btn-toggle" style="padding:0.35rem 0.8rem; font-size:0.85rem; border-radius:6px; cursor:pointer;">
          <i class="lc lc-arrow-left"></i> ${i18n.t('collections.back')}
        </button>
        <span style="font-size:0.8rem; color: var(--app-text-muted); background:rgba(255,255,255,0.05); padding:0.2rem 0.6rem; border-radius:12px;">
          <i class="lc lc-circle" style="color:${coll.color || '#7c3aed'}; font-size:0.6rem; margin-right:0.3rem;"></i> ${escapeHtml(coll.name)}
        </span>
      </div>
      <h2 style="margin:0.5rem 0 0.3rem 0; color: var(--app-text-primary);">${escapeHtml(coll.name)}</h2>
      <p style="margin:0; color: var(--app-text-muted); font-size:0.9rem;">${coll.description ? escapeHtml(coll.description) : i18n.t('collections.no_description_long')}</p>
    `;

    const itemsGrid = document.createElement('div');
    itemsGrid.id = 'collection-items-grid';
    itemsGrid.style.cssText = 'grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 1rem;';

    if (items.length === 0) {
      itemsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 3rem 1rem; color: var(--app-text-muted);">
          <i class="lc lc-folder-open" style="font-size: 2.5rem; color: #475569; margin-bottom: 0.8rem;"></i>
          <p style="margin:0;">${i18n.t('collections.detail_empty')}</p>
        </div>
      `;
    } else {
      items.forEach(item => {
        const isSeries = item.type === 'series';
        const isAudiobook = item.type === 'audiobook';
        const isVideo = item.type === 'video';
        const itemTitle = item.title || item.series_name || i18n.t('collections.untitled');

        const cardOptions = isSeries ? {
          showVolumeCount: true,
          actionTitle: i18n.t('collections.action_resume'),
          onPrimaryClick: (e) => openBookDetail(e, itemTitle, 'all', item.book_id, itemTitle),
          onActionClick: (e) => resumeSeries(e, itemTitle, 'all', item.book_id)
        } : (isAudiobook ? {
          actionTitle: i18n.t('collections.action_play'),
          onPrimaryClick: () => window.playAudiobook?.(item.audiobook_id),
          onActionClick: () => window.playAudiobook?.(item.audiobook_id)
        } : (isVideo ? {
          isVideo: true,
          actionTitle: i18n.t('collections.action_detail'),
          onPrimaryClick: (e) => openBookDetail(e, itemTitle, 'all', item.video_id, itemTitle),
          onActionClick: (e) => openBookDetail(e, itemTitle, 'all', item.video_id, itemTitle)
        } : {
          showProgress: true,
          actionTitle: i18n.t('collections.action_read'),
          onPrimaryClick: (e) => openBookDetail(e, item.book_series || item.series_name || '', 'all', item.book_id, itemTitle),
          onActionClick: (e) => {
            if (window.openReader) window.openReader(item.book_id, item.file_format, itemTitle);
          }
        }));

        const card = createBookCard({
          id: item.video_id || item.audiobook_id || item.book_id || item.id,
          representative_book_id: item.book_id,
          title: itemTitle,
          series_name: isSeries ? itemTitle : (item.book_series || item.series_name || ''),
          series_alias: itemTitle,
          cover_image: item.cover_image,
          file_format: item.file_format,
          book_count: item.book_count || 1,
          pages_read: item.pages_read || 0,
          total_pages: item.total_pages || 1,
          metadata_locked: item.metadata_locked || 0,
          is_favorite: item.is_favorite || 0,
          total_tracks: item.total_tracks || 0
        }, cardOptions);

        // 컬렉션 제거 [X] 버튼을 카드 커버 우상단에 세련되게 추가
        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn-remove-item-from-coll';
        removeBtn.title = i18n.t('collections.remove_title');
        removeBtn.style.cssText = 'position: absolute; top: 6px; right: 6px; background: rgba(0,0,0,0.7); border: none; color: #ef4444; width: 26px; height: 26px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; z-index: 10; transition: transform 0.15s ease;';
        removeBtn.innerHTML = '<i class="lc lc-x"></i>';
        removeBtn.onclick = async (e) => {
          e.stopPropagation();
          e.preventDefault();
          if (confirm(i18n.t('collections.remove_confirm', { title: itemTitle }))) {
            await removeItemFromCollection(collectionId, item.id);
            renderCollectionDetail(collectionId);
          }
        };

        const coverWrap = card.querySelector('.book-card-cover') || card;
        coverWrap.style.position = 'relative';
        coverWrap.appendChild(removeBtn);

        itemsGrid.appendChild(card);
      });
    }

    container.appendChild(headerCard);
    container.appendChild(itemsGrid);

    document.getElementById('btn-back-to-collections')?.addEventListener('click', () => {
      renderCollectionsView();
    });

  } catch (err) {
    container.innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:2rem;">${i18n.t('collections.network_error', { error: err.message })}</div>`;
  }
}

export function openCreateCollectionModal(onCreated) {
  const existing = document.getElementById('modal-create-collection');
  if (existing) existing.remove();

  const modalHtml = `
    <div id="modal-create-collection" style="position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);">
      <div style="background: rgba(var(--app-panel-rgb), 1); border: 1px solid rgba(var(--app-panel-border-rgb), 0.1); border-radius: 12px; width: 90%; max-width: 420px; padding: 1.5rem; color: var(--app-text-primary); box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);">
        <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;">
          <i class="fa-solid fa-bookmark" style="color: var(--app-accent);"></i> ${i18n.t('collections.create_title')}
        </h3>
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.85rem; color: var(--app-text-muted); margin-bottom: 0.3rem;">${i18n.t('collections.name_label')}</label>
          <input type="text" id="input-coll-name" placeholder="${i18n.t('collections.name_placeholder')}" style="width: 100%; box-sizing: border-box; padding: 0.6rem; background: rgba(var(--app-panel-rgb), 0.8); border: 1px solid rgba(var(--app-panel-border-rgb), 0.15); border-radius: 6px; color: var(--app-text-primary); outline: none;">
        </div>
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.85rem; color: var(--app-text-muted); margin-bottom: 0.3rem;">${i18n.t('collections.desc_optional')}</label>
          <textarea id="input-coll-desc" placeholder="${i18n.t('collections.desc_placeholder')}" style="width: 100%; box-sizing: border-box; padding: 0.6rem; background: rgba(var(--app-panel-rgb), 0.8); border: 1px solid rgba(var(--app-panel-border-rgb), 0.15); border-radius: 6px; color: var(--app-text-primary); outline: none; resize: vertical; height: 60px;"></textarea>
        </div>
        <div style="margin-bottom: 1.5rem;">
          <label style="display: block; font-size: 0.85rem; color: var(--app-text-muted); margin-bottom: 0.3rem;">${i18n.t('collections.color_label')}</label>
          <input type="color" id="input-coll-color" value="#7c3aed" style="width: 60px; height: 35px; border: none; background: transparent; cursor: pointer;">
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 0.6rem;">
          <button id="btn-cancel-coll-modal" style="padding: 0.5rem 1rem; background: rgba(255,255,255,0.08); border: none; border-radius: 6px; color: var(--app-text-muted); cursor: pointer;">${i18n.t('collections.cancel')}</button>
          <button id="btn-save-coll-modal" style="padding: 0.5rem 1.2rem; background: var(--color-accent); border: none; border-radius: 6px; color: var(--app-text-primary); font-weight: 600; cursor: pointer;">${i18n.t('collections.create')}</button>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', modalHtml);

  document.getElementById('btn-cancel-coll-modal')?.addEventListener('click', () => {
    document.getElementById('modal-create-collection')?.remove();
  });

  document.getElementById('btn-save-coll-modal')?.addEventListener('click', async () => {
    const name = document.getElementById('input-coll-name').value.trim();
    const description = document.getElementById('input-coll-desc').value.trim();
    const color = document.getElementById('input-coll-color').value;

    if (!name) {
      alert(i18n.t('collections.name_required'));
      return;
    }

    try {
      const res = await fetch(`/api/v1/collections?db_type=${state.currentLibraryType || 'general'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, color })
      });
      const data = await res.json();
      if (data.success) {
        document.getElementById('modal-create-collection')?.remove();
        if (onCreated) onCreated(data.collection_id);
        else renderCollectionsView();
      } else {
        alert(i18n.t('collections.create_failed', { error: data.error }));
      }
    } catch (e) {
      alert(i18n.t('collections.error', { error: e.message }));
    }
  });
}

export function openAddToCollectionModal(itemInfo) {
  const isBulkAdd = Array.isArray(itemInfo?.items);
  const collectionItems = isBulkAdd ? itemInfo.items : [itemInfo];
  const addToSelectedCollection = async (collectionId) => {
    if (isBulkAdd) await addItemsToCollection(collectionId, collectionItems);
    else await addItemToCollection(collectionId, itemInfo);
  };

  fetch(`/api/v1/collections?db_type=${state.currentLibraryType || 'general'}`)
    .then(r => r.json())
    .then(data => {
      if (!data.success) {
        alert(i18n.t('collections.list_failed', { error: data.error }));
        return;
      }
      const collections = data.collections || [];

      const existing = document.getElementById('modal-add-to-collection');
      if (existing) existing.remove();

      let listHtml = '';
      if (collections.length === 0) {
        listHtml = `<div style="text-align:center; padding:1.5rem; color: var(--app-text-muted);">${i18n.t('collections.picker_empty')}</div>`;
      } else {
        collections.forEach(c => {
          listHtml += `
            <div class="coll-select-option" data-coll-id="${c.id}" style="padding: 0.8rem; background: rgba(var(--app-panel-rgb), 0.6); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 8px; margin-bottom: 0.5rem; cursor: pointer; display: flex; align-items: center; justify-content: space-between; transition: background 0.2s;">
              <span style="display:flex; align-items:center; gap:0.5rem; color: var(--app-text-primary); font-size:0.95rem;">
                <i class="lc lc-circle" style="color:${c.color || '#7c3aed'}; font-size:0.6rem;"></i> ${escapeHtml(c.name)}
              </span>
              <span style="font-size:0.8rem; color: var(--app-text-muted);">${i18n.t('collections.picker_count', { n: c.item_count || 0 })}</span>
            </div>
          `;
        });
      }

      const modalHtml = `
        <div id="modal-add-to-collection" style="position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);">
          <div style="background: rgba(var(--app-panel-rgb), 1); border: 1px solid rgba(var(--app-panel-border-rgb), 0.1); border-radius: 12px; width: 90%; max-width: 400px; padding: 1.5rem; color: var(--app-text-primary); box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);">
            <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;">
              <i class="lc lc-circle-plus" style="color: var(--app-accent);"></i> ${escapeHtml(itemInfo?.title || i18n.t('collections.add_title'))}
            </h3>
            <div style="margin-bottom: 1rem; max-height: 240px; overflow-y: auto;">
              ${listHtml}
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; padding-top: 0.8rem; border-top: 1px solid rgba(255,255,255,0.08);">
              <button id="btn-new-coll-inside" style="padding: 0.4rem 0.8rem; background: color-mix(in srgb, var(--app-accent) 20%, transparent); border: 1px solid var(--app-accent); border-radius: 6px; color: var(--app-accent-hover); cursor: pointer; font-size: 0.85rem;"><i class="lc lc-plus"></i> ${i18n.t('collections.new_short')}</button>
              <button id="btn-close-add-coll" style="padding: 0.4rem 1rem; background: rgba(255,255,255,0.08); border: none; border-radius: 6px; color: var(--app-text-muted); cursor: pointer; font-size: 0.85rem;">${i18n.t('collections.close')}</button>
            </div>
          </div>
        </div>
      `;
      document.body.insertAdjacentHTML('beforeend', modalHtml);

      document.getElementById('btn-close-add-coll')?.addEventListener('click', () => {
        document.getElementById('modal-add-to-collection')?.remove();
      });

      document.getElementById('btn-new-coll-inside')?.addEventListener('click', () => {
        document.getElementById('modal-add-to-collection')?.remove();
        openCreateCollectionModal((newCollId) => {
          addToSelectedCollection(newCollId);
        });
      });

      document.querySelectorAll('.coll-select-option').forEach(opt => {
        opt.addEventListener('click', async () => {
          const collId = opt.getAttribute('data-coll-id');
          await addToSelectedCollection(collId);
          document.getElementById('modal-add-to-collection')?.remove();
        });
      });
    });
}

async function addItemToCollection(collectionId, itemInfo, { silent = false } = {}) {
  if (itemInfo.author_key) {
    try {
      const res = await fetch(`/api/v1/collections/${collectionId}/items/by-author?db_type=${state.currentLibraryType || 'general'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ author_key: itemInfo.author_key })
      });
      const data = await res.json();
      if (data.success) {
        const skippedText = data.skipped_count > 0 ? i18n.t('collections.skipped', { n: data.skipped_count }) : '';
        if (!silent) alert(i18n.t('collections.added', { n: data.added_count, skipped: skippedText }));
      } else {
        if (!silent) alert(i18n.t('collections.add_failed', { error: data.error }));
      }
      return data;
    } catch (e) {
      if (!silent) alert(i18n.t('collections.error', { error: e.message }));
      return { success: false, error: e.message };
    }
    return { success: false, error: i18n.t('collections.author_add_failed') };
  }

  try {
    const payload = {};
    if (itemInfo.book_id) payload.book_id = itemInfo.book_id;
    if (itemInfo.series_name) payload.series_name = itemInfo.series_name;
    if (itemInfo.audiobook_id) payload.audiobook_id = itemInfo.audiobook_id;
    if (itemInfo.video_id) payload.video_id = itemInfo.video_id;

    const res = await fetch(`/api/v1/collections/${collectionId}/items?db_type=${state.currentLibraryType || 'general'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      if (!silent) alert(i18n.t('collections.added_one'));
    } else {
      if (!silent) alert(i18n.t('collections.add_failed', { error: data.error }));
    }
    return data;
  } catch (e) {
    if (!silent) alert(i18n.t('collections.error', { error: e.message }));
    return { success: false, error: e.message };
  }
}

async function addItemsToCollection(collectionId, items) {
  const results = [];
  for (const item of items || []) {
    results.push(await addItemToCollection(collectionId, item, { silent: true }));
  }

  const addedCount = results.filter(result => result?.success).length;
  const failure = results.find(result => !result?.success);
  if (addedCount === results.length) {
    alert(i18n.t('collections.added_selected', { n: addedCount }));
  } else {
    alert(`${i18n.t('collections.added_partial', { total: results.length, added: addedCount })}${failure?.error ? i18n.t('collections.first_error', { error: failure.error }) : ''}`);
  }
}

async function removeItemFromCollection(collectionId, itemId) {
  try {
    const res = await fetch(`/api/v1/collections/${collectionId}/items/${itemId}?db_type=${state.currentLibraryType || 'general'}`, {
      method: 'DELETE'
    });
    return (await res.json()).success;
  } catch (e) {
    return false;
  }
}

async function deleteCollection(collectionId) {
  try {
    const res = await fetch(`/api/v1/collections/${collectionId}?db_type=${state.currentLibraryType || 'general'}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (data.success) {
      renderCollectionsView();
    } else {
      alert(i18n.t('collections.delete_failed', { error: data.error }));
    }
  } catch (e) {
    alert(i18n.t('collections.error', { error: e.message }));
  }
}

function openEditCollectionModal(coll) {
  const existing = document.getElementById('modal-create-collection');
  if (existing) existing.remove();

  const modalHtml = `
    <div id="modal-create-collection" style="position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);">
      <div style="background: rgba(var(--app-panel-rgb), 1); border: 1px solid rgba(var(--app-panel-border-rgb), 0.1); border-radius: 12px; width: 90%; max-width: 420px; padding: 1.5rem; color: var(--app-text-primary); box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);">
        <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;">
          <i class="lc lc-pen" style="color: var(--app-accent);"></i> ${i18n.t('collections.edit_title')}
        </h3>
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.85rem; color: var(--app-text-muted); margin-bottom: 0.3rem;">${i18n.t('collections.name_label')}</label>
          <input type="text" id="input-coll-name" value="${escapeHtml(coll.name)}" style="width: 100%; box-sizing: border-box; padding: 0.6rem; background: rgba(var(--app-panel-rgb), 0.8); border: 1px solid rgba(var(--app-panel-border-rgb), 0.15); border-radius: 6px; color: var(--app-text-primary); outline: none;">
        </div>
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.85rem; color: var(--app-text-muted); margin-bottom: 0.3rem;">${i18n.t('collections.desc_label')}</label>
          <textarea id="input-coll-desc" style="width: 100%; box-sizing: border-box; padding: 0.6rem; background: rgba(var(--app-panel-rgb), 0.8); border: 1px solid rgba(var(--app-panel-border-rgb), 0.15); border-radius: 6px; color: var(--app-text-primary); outline: none; resize: vertical; height: 60px;">${coll.description ? escapeHtml(coll.description) : ''}</textarea>
        </div>
        <div style="margin-bottom: 1.5rem;">
          <label style="display: block; font-size: 0.85rem; color: var(--app-text-muted); margin-bottom: 0.3rem;">${i18n.t('collections.color_label')}</label>
          <input type="color" id="input-coll-color" value="${coll.color || '#7c3aed'}" style="width: 60px; height: 35px; border: none; background: transparent; cursor: pointer;">
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 0.6rem;">
          <button id="btn-cancel-coll-modal" style="padding: 0.5rem 1rem; background: rgba(255,255,255,0.08); border: none; border-radius: 6px; color: var(--app-text-muted); cursor: pointer;">${i18n.t('collections.cancel')}</button>
          <button id="btn-save-coll-modal" style="padding: 0.5rem 1.2rem; background: var(--color-accent); border: none; border-radius: 6px; color: var(--app-text-primary); font-weight: 600; cursor: pointer;">${i18n.t('collections.save')}</button>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', modalHtml);

  document.getElementById('btn-cancel-coll-modal')?.addEventListener('click', () => {
    document.getElementById('modal-create-collection')?.remove();
  });

  document.getElementById('btn-save-coll-modal')?.addEventListener('click', async () => {
    const name = document.getElementById('input-coll-name').value.trim();
    const description = document.getElementById('input-coll-desc').value.trim();
    const color = document.getElementById('input-coll-color').value;

    if (!name) {
      alert(i18n.t('collections.name_required'));
      return;
    }

    try {
      const res = await fetch(`/api/v1/collections/${coll.id}?db_type=${state.currentLibraryType || 'general'}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, color })
      });
      const data = await res.json();
      if (data.success) {
        document.getElementById('modal-create-collection')?.remove();
        renderCollectionsView();
      } else {
        alert(i18n.t('collections.update_failed', { error: data.error }));
      }
    } catch (e) {
      alert(i18n.t('collections.error', { error: e.message }));
    }
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
