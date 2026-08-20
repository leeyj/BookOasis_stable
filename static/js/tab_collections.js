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

  if (indicator) indicator.innerText = '컬렉션 (Collections)';

  if (!container) return;
  container.innerHTML = `
    <div style="grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
      <h3 style="margin:0; font-size:1.1rem; color: #f8fafc; display:flex; align-items:center; gap:0.5rem;">
        <i class="fa-solid fa-bookmark" style="color: #a855f7;"></i> 나만의 컬렉션 목록
      </h3>
      <button id="btn-create-collection-main" class="btn-toggle active" style="padding: 0.4rem 0.9rem; font-size: 0.88rem; background: var(--color-accent); color:#fff; border:none; border-radius:6px; cursor:pointer;">
        <i class="fa-solid fa-plus"></i> 새 컬렉션 만들기
      </button>
    </div>
    <div id="collections-grid-list" style="grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1.2rem;">
      <div style="grid-column:1/-1; text-align:center; padding:3rem; color:#94a3b8;"><i class="fa-solid fa-circle-notch fa-spin"></i> 컬렉션을 불러오는 중...</div>
    </div>
  `;

  document.getElementById('btn-create-collection-main')?.addEventListener('click', () => {
    openCreateCollectionModal();
  });

  try {
    const res = await fetch(`/api/v1/collections?db_type=${state.currentLibraryType || 'general'}`);
    const data = await res.json();
    if (!data.success) {
      document.getElementById('collections-grid-list').innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:2rem;">오류: ${data.error}</div>`;
      return;
    }

    const collections = data.collections || [];
    if (countBadge) countBadge.innerText = `(총 ${collections.length}개 컬렉션)`;

    if (collections.length === 0) {
      document.getElementById('collections-grid-list').innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 12px;">
          <i class="fa-solid fa-bookmark" style="font-size: 3rem; color: #475569; margin-bottom: 1rem;"></i>
          <h4 style="margin: 0 0 0.5rem 0; color: #cbd5e1;">아직 생성된 컬렉션이 없습니다.</h4>
          <p style="color: #64748b; font-size: 0.9rem; margin-bottom: 1.5rem;">도서 우클릭 메뉴에서 [컬렉션에 추가]를 눌러 나만의 묶음을 만들어 보세요!</p>
          <button onclick="document.getElementById('btn-create-collection-main').click()" class="btn-toggle active" style="padding: 0.5rem 1.2rem; font-size: 0.9rem; background: var(--color-accent); border:none; border-radius:6px; color:#fff; cursor:pointer;">
            <i class="fa-solid fa-plus"></i> 지금 첫 컬렉션 만들기
          </button>
        </div>
      `;
      return;
    }

    let html = '';
    collections.forEach(coll => {
      const color = coll.color || '#7c3aed';
      html += `
        <div class="collection-card-item" data-coll-id="${coll.id}" style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.2rem; cursor: pointer; transition: all 0.2s ease; position: relative; display: flex; flex-direction: column; justify-content: space-between;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.8rem;">
            <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: ${color};"></span>
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn-edit-coll" data-coll-id="${coll.id}" title="컬렉션 수정" style="background:transparent; border:none; color:#94a3b8; cursor:pointer; font-size:0.85rem;"><i class="fa-solid fa-pen"></i></button>
              <button class="btn-delete-coll" data-coll-id="${coll.id}" title="컬렉션 삭제" style="background:transparent; border:none; color:#ef4444; cursor:pointer; font-size:0.85rem;"><i class="fa-solid fa-trash-can"></i></button>
            </div>
          </div>
          <div>
            <h4 style="margin: 0 0 0.4rem 0; color: #f8fafc; font-size: 1.05rem; word-break: break-word;">${escapeHtml(coll.name)}</h4>
            <p style="margin: 0; color: #94a3b8; font-size: 0.82rem; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${coll.description ? escapeHtml(coll.description) : '설명 없음'}</p>
          </div>
          <div style="margin-top: 1.2rem; padding-top: 0.8rem; border-top: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #cbd5e1;">
            <span><i class="fa-solid fa-book" style="color:${color}; margin-right:0.3rem;"></i> ${coll.item_count || 0}개 항목</span>
            <span style="color: var(--color-accent); font-weight: 500;">열기 <i class="fa-solid fa-chevron-right" style="font-size:0.75rem;"></i></span>
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
        if (confirm('이 컬렉션을 삭제하시겠습니까? (소속 도서 원본은 삭제되지 않습니다)')) {
          await deleteCollection(collId);
        }
      });
    });

  } catch (err) {
    document.getElementById('collections-grid-list').innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:2rem;">통신 오류: ${err.message}</div>`;
  }
}

export async function renderCollectionDetail(collectionId) {
  const container = document.getElementById('books-list-container');
  const indicator = document.getElementById('current-category-indicator');
  const countBadge = document.getElementById('library-total-count');

  const scrollSpinner = document.getElementById('infinite-scroll-spinner');
  if (scrollSpinner) scrollSpinner.style.display = 'none';

  if (!container) return;
  container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:3rem; color:#94a3b8;"><i class="fa-solid fa-circle-notch fa-spin"></i> 컬렉션 상세 정보를 불러오는 중...</div>`;

  try {
    const res = await fetch(`/api/v1/collections/${collectionId}?db_type=${state.currentLibraryType || 'general'}`);
    const data = await res.json();
    if (!data.success) {
      container.innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:2rem;">오류: ${data.error}</div>`;
      return;
    }

    const coll = data.collection;
    const items = coll.items || [];

    if (indicator) indicator.innerText = `컬렉션: ${coll.name}`;
    if (countBadge) countBadge.innerText = `(총 ${items.length}개 항목)`;

    container.innerHTML = '';

    const headerCard = document.createElement('div');
    headerCard.style.cssText = 'grid-column: 1 / -1; background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.2rem 1.5rem; margin-bottom: 1.2rem;';
    headerCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
        <button id="btn-back-to-collections" class="btn-toggle" style="padding:0.35rem 0.8rem; font-size:0.85rem; border-radius:6px; cursor:pointer;">
          <i class="fa-solid fa-arrow-left"></i> 컬렉션 목록으로 돌아가기
        </button>
        <span style="font-size:0.8rem; color:#94a3b8; background:rgba(255,255,255,0.05); padding:0.2rem 0.6rem; border-radius:12px;">
          <i class="fa-solid fa-circle" style="color:${coll.color || '#7c3aed'}; font-size:0.6rem; margin-right:0.3rem;"></i> ${escapeHtml(coll.name)}
        </span>
      </div>
      <h2 style="margin:0.5rem 0 0.3rem 0; color:#f8fafc;">${escapeHtml(coll.name)}</h2>
      <p style="margin:0; color:#94a3b8; font-size:0.9rem;">${coll.description ? escapeHtml(coll.description) : '등록된 설명이 없습니다.'}</p>
    `;

    const itemsGrid = document.createElement('div');
    itemsGrid.id = 'collection-items-grid';
    itemsGrid.style.cssText = 'grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 1rem;';

    if (items.length === 0) {
      itemsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 3rem 1rem; color: #94a3b8;">
          <i class="fa-solid fa-folder-open" style="font-size: 2.5rem; color: #475569; margin-bottom: 0.8rem;"></i>
          <p style="margin:0;">컬렉션에 등록된 항목이 없습니다. 도서/시리즈 우클릭 메뉴에서 [컬렉션에 추가]를 눌러보세요.</p>
        </div>
      `;
    } else {
      items.forEach(item => {
        const isSeries = item.type === 'series';
        const isAudiobook = item.type === 'audiobook';
        const isVideo = item.type === 'video';
        const itemTitle = item.title || item.series_name || '제목 없음';

        const cardOptions = isSeries ? {
          showVolumeCount: true,
          actionTitle: '이어읽기',
          onPrimaryClick: (e) => openBookDetail(e, itemTitle, 'all', item.book_id, itemTitle),
          onActionClick: (e) => resumeSeries(e, itemTitle, 'all', item.book_id)
        } : (isAudiobook ? {
          actionTitle: '재생',
          onPrimaryClick: () => window.playAudiobook?.(item.audiobook_id),
          onActionClick: () => window.playAudiobook?.(item.audiobook_id)
        } : (isVideo ? {
          isVideo: true,
          actionTitle: '상세보기',
          onPrimaryClick: (e) => openBookDetail(e, itemTitle, 'all', item.video_id, itemTitle),
          onActionClick: (e) => openBookDetail(e, itemTitle, 'all', item.video_id, itemTitle)
        } : {
          showProgress: true,
          actionTitle: '바로 읽기',
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
        removeBtn.title = '컬렉션에서 제거';
        removeBtn.style.cssText = 'position: absolute; top: 6px; right: 6px; background: rgba(0,0,0,0.7); border: none; color: #ef4444; width: 26px; height: 26px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; z-index: 10; transition: transform 0.15s ease;';
        removeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
        removeBtn.onclick = async (e) => {
          e.stopPropagation();
          e.preventDefault();
          if (confirm(`'${itemTitle}' 항목을 이 컬렉션에서 제거하시겠습니까?`)) {
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
    container.innerHTML = `<div style="grid-column:1/-1; color:#ef4444; padding:2rem;">통신 오류: ${err.message}</div>`;
  }
}

export function openCreateCollectionModal(onCreated) {
  const existing = document.getElementById('modal-create-collection');
  if (existing) existing.remove();

  const modalHtml = `
    <div id="modal-create-collection" style="position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);">
      <div style="background: #1e293b; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; width: 90%; max-width: 420px; padding: 1.5rem; color: #f8fafc; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);">
        <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;">
          <i class="fa-solid fa-bookmark" style="color: #a855f7;"></i> 새 컬렉션 생성
        </h3>
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.3rem;">컬렉션 이름</label>
          <input type="text" id="input-coll-name" placeholder="예: 심리학 도서 모음" style="width: 100%; box-sizing: border-box; padding: 0.6rem; background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; color: #fff; outline: none;">
        </div>
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.3rem;">설명 (선택)</label>
          <textarea id="input-coll-desc" placeholder="컬렉션에 대한 간단한 설명..." style="width: 100%; box-sizing: border-box; padding: 0.6rem; background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; color: #fff; outline: none; resize: vertical; height: 60px;"></textarea>
        </div>
        <div style="margin-bottom: 1.5rem;">
          <label style="display: block; font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.3rem;">테마 색상</label>
          <input type="color" id="input-coll-color" value="#7c3aed" style="width: 60px; height: 35px; border: none; background: transparent; cursor: pointer;">
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 0.6rem;">
          <button id="btn-cancel-coll-modal" style="padding: 0.5rem 1rem; background: rgba(255,255,255,0.08); border: none; border-radius: 6px; color: #cbd5e1; cursor: pointer;">취소</button>
          <button id="btn-save-coll-modal" style="padding: 0.5rem 1.2rem; background: var(--color-accent); border: none; border-radius: 6px; color: #fff; font-weight: 600; cursor: pointer;">생성하기</button>
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
      alert('컬렉션 이름을 입력해 주세요.');
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
        alert(`생성 실패: ${data.error}`);
      }
    } catch (e) {
      alert(`오류: ${e.message}`);
    }
  });
}

export function openAddToCollectionModal(itemInfo) {
  fetch(`/api/v1/collections?db_type=${state.currentLibraryType || 'general'}`)
    .then(r => r.json())
    .then(data => {
      if (!data.success) {
        alert(`컬렉션 목록 조회 실패: ${data.error}`);
        return;
      }
      const collections = data.collections || [];

      const existing = document.getElementById('modal-add-to-collection');
      if (existing) existing.remove();

      let listHtml = '';
      if (collections.length === 0) {
        listHtml = `<div style="text-align:center; padding:1.5rem; color:#94a3b8;">생성된 컬렉션이 없습니다. 아래 버튼으로 먼저 생성해 보세요.</div>`;
      } else {
        collections.forEach(c => {
          listHtml += `
            <div class="coll-select-option" data-coll-id="${c.id}" style="padding: 0.8rem; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; margin-bottom: 0.5rem; cursor: pointer; display: flex; align-items: center; justify-content: space-between; transition: background 0.2s;">
              <span style="display:flex; align-items:center; gap:0.5rem; color:#f8fafc; font-size:0.95rem;">
                <i class="fa-solid fa-circle" style="color:${c.color || '#7c3aed'}; font-size:0.6rem;"></i> ${escapeHtml(c.name)}
              </span>
              <span style="font-size:0.8rem; color:#94a3b8;">(${c.item_count || 0}개)</span>
            </div>
          `;
        });
      }

      const modalHtml = `
        <div id="modal-add-to-collection" style="position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);">
          <div style="background: #1e293b; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; width: 90%; max-width: 400px; padding: 1.5rem; color: #f8fafc; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);">
            <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;">
              <i class="fa-solid fa-plus-circle" style="color: #a855f7;"></i> 컬렉션에 추가
            </h3>
            <div style="margin-bottom: 1rem; max-height: 240px; overflow-y: auto;">
              ${listHtml}
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; padding-top: 0.8rem; border-top: 1px solid rgba(255,255,255,0.08);">
              <button id="btn-new-coll-inside" style="padding: 0.4rem 0.8rem; background: rgba(168,85,247,0.2); border: 1px solid var(--color-accent); border-radius: 6px; color: #c084fc; cursor: pointer; font-size: 0.85rem;"><i class="fa-solid fa-plus"></i> 새 컬렉션</button>
              <button id="btn-close-add-coll" style="padding: 0.4rem 1rem; background: rgba(255,255,255,0.08); border: none; border-radius: 6px; color: #cbd5e1; cursor: pointer; font-size: 0.85rem;">닫기</button>
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
          addItemToCollection(newCollId, itemInfo);
        });
      });

      document.querySelectorAll('.coll-select-option').forEach(opt => {
        opt.addEventListener('click', async () => {
          const collId = opt.getAttribute('data-coll-id');
          await addItemToCollection(collId, itemInfo);
          document.getElementById('modal-add-to-collection')?.remove();
        });
      });
    });
}

async function addItemToCollection(collectionId, itemInfo) {
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
      alert('컬렉션에 성공적으로 추가되었습니다!');
    } else {
      alert(`추가 실패: ${data.error}`);
    }
  } catch (e) {
    alert(`오류: ${e.message}`);
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
      alert(`삭제 실패: ${data.error}`);
    }
  } catch (e) {
    alert(`오류: ${e.message}`);
  }
}

function openEditCollectionModal(coll) {
  const existing = document.getElementById('modal-create-collection');
  if (existing) existing.remove();

  const modalHtml = `
    <div id="modal-create-collection" style="position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);">
      <div style="background: #1e293b; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; width: 90%; max-width: 420px; padding: 1.5rem; color: #f8fafc; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);">
        <h3 style="margin: 0 0 1rem 0; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;">
          <i class="fa-solid fa-pen" style="color: #a855f7;"></i> 컬렉션 수정
        </h3>
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.3rem;">컬렉션 이름</label>
          <input type="text" id="input-coll-name" value="${escapeHtml(coll.name)}" style="width: 100%; box-sizing: border-box; padding: 0.6rem; background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; color: #fff; outline: none;">
        </div>
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.3rem;">설명</label>
          <textarea id="input-coll-desc" style="width: 100%; box-sizing: border-box; padding: 0.6rem; background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; color: #fff; outline: none; resize: vertical; height: 60px;">${coll.description ? escapeHtml(coll.description) : ''}</textarea>
        </div>
        <div style="margin-bottom: 1.5rem;">
          <label style="display: block; font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.3rem;">테마 색상</label>
          <input type="color" id="input-coll-color" value="${coll.color || '#7c3aed'}" style="width: 60px; height: 35px; border: none; background: transparent; cursor: pointer;">
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 0.6rem;">
          <button id="btn-cancel-coll-modal" style="padding: 0.5rem 1rem; background: rgba(255,255,255,0.08); border: none; border-radius: 6px; color: #cbd5e1; cursor: pointer;">취소</button>
          <button id="btn-save-coll-modal" style="padding: 0.5rem 1.2rem; background: var(--color-accent); border: none; border-radius: 6px; color: #fff; font-weight: 600; cursor: pointer;">저장하기</button>
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
      alert('컬렉션 이름을 입력해 주세요.');
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
        alert(`수정 실패: ${data.error}`);
      }
    } catch (e) {
      alert(`오류: ${e.message}`);
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
