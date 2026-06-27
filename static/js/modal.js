// modal.js – 도서 상세 인라인 뷰 관리 (모달 제거, 그리드↔상세 전환)
import { state } from './state.js';
import * as api from './api.js';
import { switchActiveView } from './view_manager.js';

// 그리드 뷰 → 상세 뷰 전환
export async function openBookDetail(event, seriesName, libraryId) {
  const detailView = document.getElementById('book-detail-view');
  if (!detailView) return;

  const safeSeriesName = seriesName || '';
  // 전달된 libraryId가 없으면 현재 상태값을 사용하되, 대시보드 시스템성 값이면 'all'로 대체 처리
  const activeLibId = libraryId || state.currentLibraryId || 'all';

  // 현재 리스트 스크롤 위치 저장 (복귀 시 사용)
  state.scrollPositions = state.scrollPositions || {};
  try {
    state.scrollPositions[activeLibId] = window.pageYOffset || document.documentElement.scrollTop || 0;
  } catch (e) {
    // 접근이 실패하면 무시
    console.warn('[detail] failed to capture scroll position', e);
  }

  // 로딩 표시
  detailView.innerHTML = `
    <button class="btn-back-to-list" onclick="goBackToList()">
      <i class="fa-solid fa-arrow-left"></i> 목록으로 돌아가기
    </button>
    <div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 도서 정보를 불러오는 중...</div>
  `;
  switchActiveView('detail');

  try {
    const data = await api.fetchMediaDetail(state.currentLibraryType, activeLibId, safeSeriesName);

    if (data.success) {
      const meta = data.meta;
      const books = data.books || [];
      const firstBookId = books.length > 0 ? books[0].id : null;
      const actualLibraryId = (books.length > 0 && books[0].library_id) ? books[0].library_id : activeLibId;
      const coverSrc = meta.cover_image
        ? `/covers/${meta.cover_image}`
        : '/static/images/default_cover.jpg';
      const stars = '★'.repeat(Math.round(meta.score / 20)) + '☆'.repeat(5 - Math.round(meta.score / 20));
      const linkHtml = meta.link
        ? `<a href="${meta.link}" target="_blank" class="ridi-link-btn">리디북스 바로가기</a>`
        : '';

      // 단행본 목록 (하단 전체 너비, Kavita 스타일)
      let volumesHtml = '';
      books.forEach(b => {
        const progressPercent = b.total_pages > 0 ? Math.round((b.pages_read / b.total_pages) * 100) : 0;
        const progressText = b.pages_read > 0
          ? `${b.pages_read}p / ${b.total_pages}p (${progressPercent}%)`
          : '미독';
        const readBtnText = b.pages_read > 0
          ? `<i class="fa-solid fa-play"></i> 이어보기`
          : `<i class="fa-solid fa-play"></i> 처음부터`;
        const volCoverSrc = b.cover_image
          ? `/covers/${b.cover_image}`
          : '/static/images/default_cover.jpg';
        const isCompleted = b.is_completed
          ? `<span class="vol-badge-completed">완독</span>`
          : '';

        const isFav = b.is_favorite === 1;
        const favIconClass = isFav ? 'fa-solid fa-star' : 'fa-regular fa-star';
        const favIconColor = isFav ? '#eab308' : '#64748b';
        const favBtnHtml = `
          <button class="btn-fav-toggle" onclick="toggleBookFavorite(event, ${b.id}, ${isFav ? 0 : 1}, '${safeSeriesName.replace(/'/g, "\\'")}',' ${actualLibraryId}')" style="background:none; border:none; color:${favIconColor}; cursor:pointer; font-size:1.1rem; padding:0 0.5rem; display:inline-flex; align-items:center;" title="즐겨찾기 토글">
            <i class="${favIconClass}"></i>
          </button>
        `;

        // ── 스캔 오류 감지 및 경고 배너 생성 ──
        // 경고 배너는 "페이지 미검출 + 커버표지 없음" 두 조건이 동시에 충족될 때만 표시
        const noCover = !b.cover_image;
        const isZipFormat = ['zip', 'cbz'].includes((b.file_format || '').toLowerCase());
        const noOffsets = isZipFormat && (b.total_pages === 0 || b.has_offsets === 0);
        // 페이지 미검출 단독 or 커버 단독으로는 배너 미표시; 두 조건 모두 해당될 때만 표시
        const needsWarn = noCover && noOffsets;

        let warnTexts = [];
        if (noCover) warnTexts.push('커버 미검출');
        if (noOffsets) warnTexts.push('페이지 수 미검출 — 정상 열람이 어려울 수 있습니다.');
        const warnBannerHtml = needsWarn ? `
          <div class="vol-warn-banner">
            <i class="fa-solid fa-triangle-exclamation"></i>
            <span>${warnTexts.join(' · ')}</span>
            <button class="btn-rescan-book" onclick="rescanBook(event, ${b.id}, '${safeSeriesName.replace(/'/g, "\\'")}', '${actualLibraryId}')">
              <i class="fa-solid fa-rotate"></i> 다시 스캔
            </button>
          </div>
        ` : '';

        volumesHtml += `
          <div class="volume-card" oncontextmenu="event.preventDefault(); event.stopPropagation(); if (typeof window.showBookContextMenu === 'function') window.showBookContextMenu(event.clientX, event.clientY, ${b.id}, '${(b.title || '').replace(/'/g, "\\'")}',' true);">
            <img class="volume-thumb" src="${volCoverSrc}" alt="cover"
                 onerror="this.onerror=null; this.src='/static/images/default_cover.jpg';">
            <div class="volume-info">
              ${warnBannerHtml}
              <div class="volume-title-row" style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
                <span class="volume-title">${b.title || ''}</span>
                ${isCompleted}
                ${favBtnHtml}
              </div>
              <span class="volume-path" style="font-size: 0.72rem; color: #64748b; word-break: break-all; margin-top: 0.15rem; display: block;">(${b.file_path})</span>
              <div class="volume-meta-row">
                <span class="vol-meta"><i class="fa-regular fa-file"></i> ${b.total_pages}p</span>
                <span class="vol-meta"><i class="fa-regular fa-clock"></i> 약 ${Math.max(1, Math.ceil(b.total_pages / 40))}분</span>
              </div>
              <div class="volume-progress-bar-wrap">
                <div class="volume-progress-bar" style="width: ${progressPercent}%"></div>
              </div>
              <div class="chapter-progress-text">${progressText}</div>
            </div>
            <button class="btn-read" onclick="openReader(${b.id}, '${b.file_format}', '${b.title}', ${b.pages_read}, ${b.total_pages})">${readBtnText}</button>
          </div>
        `;
      });

        const isSeriesFav = books.some(b => b.is_favorite === 1);
        const seriesFavIconClass = isSeriesFav ? 'fa-solid fa-star' : 'fa-regular fa-star';
        const seriesFavIconColor = isSeriesFav ? '#eab308' : '#64748b';

        detailView.innerHTML = `
          <button class="btn-back-to-list" onclick="goBackToList()">
            <i class="fa-solid fa-arrow-left"></i> 목록으로 돌아가기
          </button>
  
          <!-- 상단 헤더: 커버(작게) + 메타정보 -->
          <div class="detail-header-panel">
            <div class="detail-cover-container" 
                 ondragover="event.preventDefault(); this.style.borderColor='#a855f7';" 
                 ondragleave="this.style.borderColor='rgba(255,255,255,0.08)';" 
                 ondrop="handleCoverDrop(event); this.style.borderColor='rgba(255,255,255,0.08)';">
              <img class="detail-cover-sm" id="detail-cover-img-preview" src="${coverSrc}" alt="Cover"
                   onerror="this.onerror=null; this.src='/static/images/default_cover.jpg';">
              <div class="cover-upload-overlay" id="cover-upload-overlay-btn" onclick="triggerCoverUpload(event)">
                <i class="fa-solid fa-camera"></i>
                <span>표지 변경</span>
              </div>
              <input type="file" id="cover-upload-file-input" accept="image/*" style="display: none;" onchange="handleCoverUploadSelect(event)">
            </div>
            
            <!-- 뷰어 모드 (일반 노출) -->
            <div id="detail-header-meta-view" class="detail-header-meta">
              <h3 class="book-detail-title" style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
                ${safeSeriesName}
                <button class="btn-fav-toggle" onclick="toggleSeriesFavorite(event, '${safeSeriesName.replace(/'/g, "\\'")}', ${isSeriesFav ? 1 : 0}, '${actualLibraryId}')" style="background:none; border:none; color:${seriesFavIconColor}; cursor:pointer; font-size:1.4rem; display:inline-flex; align-items:center;" title="시리즈 전체 즐겨찾기 토글">
                  <i class="${seriesFavIconClass}"></i>
                </button>
                <button class="ridi-link-btn btn-edit-toggle" onclick="toggleMetaEditMode()" style="background: #0284c7; border-color: #0ea5e9; font-size: 0.75rem; padding: 0.2rem 0.6rem; display: inline-flex; align-items: center; gap: 0.2rem; margin-left: 0.4rem;">
                  <i class="fa-solid fa-pen-to-square"></i> 정보 수정
                </button>
              </h3>
              <div class="detail-meta">
                <span class="badge">${safeSeriesName}</span>
                <span class="meta-item"><i class="fa-solid fa-pen-nib"></i> ${meta.author || '-'}</span>
                <span class="meta-item"><i class="fa-solid fa-building"></i> ${meta.publisher || '-'}</span>
                <span class="meta-item"><i class="fa-solid fa-book-open"></i> ${books.length}권</span>
              </div>
              <div class="detail-score">${stars}</div>
              <p class="book-summary-text">${meta.summary || '등록된 설명이 없습니다.'}</p>
              ${linkHtml}
              
              <!-- 버튼: 메타정보 찾기 (이미 메타데이터가 있을 때 수동 실행용) -->
              <div style="display: flex; gap: 0.5rem; margin-top: 1rem; flex-wrap: wrap; align-items: center;">
                <button id="btn-manual-meta-search" class="ridi-link-btn" style="display:none; margin: 0; background: #7c3aed; border-color: #a855f7;"><i class="fa-solid fa-wand-magic-sparkles"></i> 추천 매칭</button>
                <button id="btn-plugin-meta-search" class="ridi-link-btn" onclick="openMetadataSearchModal(${firstBookId}, '${safeSeriesName.replace(/'/g, "\\'")}', true)" style="margin: 0; background: #2563eb; border-color: #3b82f6;"><i class="fa-solid fa-magnifying-glass"></i> 메타정보 검색</button>
              </div>
            </div>

            <!-- 편집 모드 (수동 입력 폼) -->
            <div id="detail-header-meta-edit" class="detail-header-meta" style="display: none;">
              <h3 class="book-detail-title" style="margin-bottom: 0.5rem; font-size: 1.3rem;">도서 정보 수정 <span style="font-size: 0.8rem; color: #94a3b8; font-weight: normal; margin-left: 0.5rem;">(표지는 왼쪽 이미지 클릭 또는 파일 드롭)</span></h3>
              <div class="edit-meta-form-group">
                <div class="edit-meta-row-item">
                  <label>작가</label>
                  <input type="text" id="edit-author-input" class="edit-meta-input" value="${meta.author === '-' ? '' : meta.author}">
                </div>
                <div class="edit-meta-row-item">
                  <label>출판사</label>
                  <input type="text" id="edit-publisher-input" class="edit-meta-input" value="${meta.publisher === '-' ? '' : meta.publisher}">
                </div>
                <div class="edit-meta-row-item">
                  <label>리디북스 링크</label>
                  <input type="text" id="edit-link-input" class="edit-meta-input" value="${meta.link || ''}">
                </div>
                <div class="edit-meta-row-item">
                  <label>작품 설명</label>
                  <textarea id="edit-summary-input" class="edit-meta-textarea">${meta.summary === '등록된 설명이 없습니다.' ? '' : meta.summary}</textarea>
                </div>
              </div>
              <div class="edit-meta-buttons-row">
                <button class="ridi-link-btn" onclick="saveManualMetadata('${safeSeriesName.replace(/'/g, "\\'")}', '${actualLibraryId}')" style="background: #22c55e; border-color: #4ade80;">저장</button>
                <button class="ridi-link-btn" onclick="toggleMetaEditMode()" style="background: #64748b; border-color: #94a3b8;">취소</button>
              </div>
            </div>
            
            <!-- 유사 메타데이터 추천 영역 -->
            <div id="meta-recommend-section" style="display:none; margin-top: 1rem; padding: 1rem; background: rgba(30, 41, 59, 0.5); border: 1px dashed rgba(168, 85, 247, 0.4); border-radius: 8px; width: 100%;">
              <h5 style="margin: 0 0 0.8rem 0; color: #c084fc; font-size: 0.85rem;"><i class="fa-solid fa-wand-magic-sparkles"></i> 유사 메타데이터 정보 가져오기</h5>
              <div id="recommend-candidates-list" style="display: flex; flex-direction: column; gap: 0.6rem;">
                <div style="font-size:0.75rem; color:#64748b;"><i class="fa-solid fa-circle-notch fa-spin"></i> 추천 후보를 찾는 중...</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 하단: 단행본 목록 (전체 너비) -->
        <div class="volumes-section">
          <h4 class="volumes-section-title">
            <i class="fa-solid fa-layer-group"></i> 단행본 목록
            <span class="vol-count-badge">${books.length}권</span>
          </h4>
          <div class="volumes-list">
            ${volumesHtml}
          </div>
        </div>
      `;

      // 메타데이터 비동기 로드 함수 정의
      const triggerRecommendSearch = () => {
        const recSection = document.getElementById('meta-recommend-section');
        const recList = document.getElementById('recommend-candidates-list');
        if (recSection && recList) {
          recSection.style.display = 'block';
          recList.innerHTML = `<div style="font-size:0.75rem; color:#64748b;"><i class="fa-solid fa-circle-notch fa-spin"></i> 추천 후보를 찾는 중...</div>`;
          api.fetchMetaRecommend(state.currentLibraryType, seriesName).then(res => {
            if (res.success && res.recommends && res.recommends.length > 0) {
              let recHtml = '';
              res.recommends.forEach(rec => {
                recHtml += `
                  <div class="recommend-card" style="display: flex; flex-direction: column; gap: 0.3rem; padding: 0.6rem; background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                      <strong style="font-size: 0.85rem; color: #fff;">${rec.series_name}</strong>
                      <button class="btn-apply-meta" data-source-id="${rec.id}" style="padding: 0.2rem 0.6rem; font-size: 0.72rem; font-weight: 700; color: #fff; background: #7c3aed; border: none; border-radius: 4px; cursor: pointer; transition: background 0.2s;">이 정보로 채우기</button>
                    </div>
                    <div style="font-size: 0.72rem; color: #94a3b8;">
                      <span>저자: ${rec.author}</span> | <span>출판사: ${rec.publisher}</span>
                    </div>
                    <p style="margin: 0.2rem 0 0 0; font-size: 0.72rem; color: #cbd5e1; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; line-height: 1.4;">${rec.summary}</p>
                  </div>
                `;
               });
              recList.innerHTML = recHtml;

              // 적용 버튼 클릭 이벤트 바인딩
              recList.querySelectorAll('.btn-apply-meta').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                  const sourceBookId = e.target.dataset.sourceId;
                  const confirmApply = confirm(`💡 선택한 ["${seriesName}"]의 정보를 이 라이브러리에 영구 복사하시겠습니까?`);
                  if (!confirmApply) return;

                  e.target.disabled = true;
                  e.target.innerText = '적용 중...';

                  const formData = new FormData();
                  formData.append('type', state.currentLibraryType);
                  formData.append('target_series', safeSeriesName);
                  formData.append('target_library_id', actualLibraryId);
                  formData.append('source_book_id', sourceBookId);

                  try {
                    const copyRes = await api.copyMetadata(formData);
                    if (copyRes.success) {
                      alert(copyRes.message);
                      // 화면을 갱신하여 채워진 내용 렌더링
                      openBookDetail(null, safeSeriesName, actualLibraryId);
                    } else {
                      alert(`적용 실패: ${copyRes.error}`);
                      e.target.disabled = false;
                      e.target.innerText = '이 정보로 채우기';
                    }
                  } catch (err) {
                    console.error('메타데이터 복사 오류:', err);
                    alert('서버 통신 중 오류가 발생했습니다.');
                    e.target.disabled = false;
                    e.target.innerText = '이 정보로 채우기';
                  }
                });
              });
            } else {
              recList.innerHTML = `<div style="font-size:0.75rem; color:#64748b;">유사한 추천 메타데이터 후보를 찾지 못했습니다.</div>`;
            }
          }).catch(err => {
            console.error('추천 데이터 로드 실패:', err);
            recList.innerHTML = `<div style="font-size:0.75rem; color:#ef4444;">추천 정보를 로드하는 데 실패했습니다.</div>`;
          });
        }
      };

      // 메타데이터가 공란이거나 기본 설명일 때 자동 트리거 분기
      const isMetaEmpty = !meta.summary || meta.summary === '등록된 설명이 없습니다.';
      if (isMetaEmpty) {
        triggerRecommendSearch();
      } else {
        const btnManual = document.getElementById('btn-manual-meta-search');
        if (btnManual) {
          btnManual.style.display = 'inline-block';
          btnManual.addEventListener('click', () => {
            btnManual.style.display = 'none'; // 버튼을 숨기고
            triggerRecommendSearch(); // 수동 검색 시작
          });
        }
      }

      // 히스토리 해시가 #detail이 아닌 경우 상태 푸시
      if (window.location.hash !== '#detail') {
        history.pushState({ view: 'detail', series: safeSeriesName, libraryId: actualLibraryId }, '', '#detail');
      }

      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      detailView.innerHTML = `
        <button class="btn-back-to-list" onclick="goBackToList()">
          <i class="fa-solid fa-arrow-left"></i> 목록으로 돌아가기
        </button>
        <div class="loading-spinner">도서 정보를 불러올 수 없습니다: ${data.error || '알 수 없는 오류'}</div>
      `;
    }
  } catch (e) {
    console.error('[detail] openBookDetail 에러:', e);
    detailView.innerHTML = `
      <button class="btn-back-to-list" onclick="goBackToList()">
        <i class="fa-solid fa-arrow-left"></i> 목록으로 돌아가기
      </button>
      <div class="loading-spinner">도서 상세 정보를 가져오는 데 실패했습니다.</div>
    `;
  }
}

// 상세 뷰 → 그리드 뷰/대시보드 복귀
export function goBackToList(triggerBack = true) {
  if (state.currentLibraryId === 'home') {
    switchActiveView('dashboard');
  } else {
    switchActiveView('grid');
  }

  // 상세에서 돌아올 때 저장된 스크롤 위치가 있으면 복원
  try {
    const saved = state.scrollPositions && state.scrollPositions[state.currentLibraryId];
    if (typeof saved !== 'undefined' && saved !== null) {
      // 뷰 전환 렌더링이 완료될 시간을 약간 둔 후 복원
      setTimeout(() => {
        window.scrollTo({ top: saved, behavior: 'auto' });
      }, 50);
      // 복원 후 캐시 정리
      delete state.scrollPositions[state.currentLibraryId];
    }
  } catch (e) {
    console.warn('[goBackToList] failed to restore scroll', e);
  }
  // 수동 목록으로 돌아가기 버튼을 누른 경우에만 브라우저 히스토리 스택 원상복구
  if (triggerBack && window.location.hash === '#detail') {
    history.back();
  }
}

window.toggleBookFavorite = async (event, bookId, nextStatus, seriesName, libraryId) => {
  if (event) event.stopPropagation();
  const res = await window.toggleFavoriteAction(bookId, nextStatus);
  if (res && res.success) {
    const statusText = nextStatus === 1 ? '등록' : '해제';
    if (typeof window.showToast === 'function') {
      window.showToast(`즐겨찾기가 ${statusText}되었습니다.`, 'success');
    }
    openBookDetail(null, seriesName, libraryId);
  } else {
    if (typeof window.showToast === 'function') {
      window.showToast('즐겨찾기 갱신에 실패했습니다.', 'error');
    } else {
      alert('즐겨찾기 갱신에 실패했습니다.');
    }
  }
};

window.toggleSeriesFavorite = async (event, seriesName, currentStatus, libraryId) => {
  if (event) event.stopPropagation();
  try {
    const data = await api.fetchMediaDetail(state.currentLibraryType, libraryId || state.currentLibraryId, seriesName);
    if (data.success && data.books && data.books.length > 0) {
      const nextStatus = currentStatus === 1 ? 0 : 1;
      const promises = data.books.map(b => window.toggleFavoriteAction(b.id, nextStatus));
      await Promise.all(promises);
      const statusText = nextStatus === 1 ? '등록' : '해제';
      if (typeof window.showToast === 'function') {
        window.showToast(`"${seriesName}" 시리즈 전체 즐겨찾기가 ${statusText}되었습니다.`, 'success');
      }
      openBookDetail(null, seriesName, libraryId);
    }
  } catch (err) {
    console.error('시리즈 즐겨찾기 토글 실패:', err);
    if (typeof window.showToast === 'function') {
      window.showToast('시리즈 즐겨찾기 갱신에 실패했습니다.', 'error');
    } else {
      alert('시리즈 즐겨찾기 갱신에 실패했습니다.');
    }
  }
};

window.toggleMetaEditMode = () => {
  const viewEl = document.getElementById('detail-header-meta-view');
  const editEl = document.getElementById('detail-header-meta-edit');
  const overlayBtn = document.getElementById('cover-upload-overlay-btn');
  const btnEdit = document.querySelector('.btn-edit-toggle');

  if (viewEl && editEl) {
    const isEdit = editEl.style.display !== 'none';
    if (isEdit) {
      editEl.style.display = 'none';
      viewEl.style.display = 'flex';
      if (overlayBtn) overlayBtn.classList.remove('editable');
      if (btnEdit) btnEdit.style.display = 'inline-flex';
    } else {
      editEl.style.display = 'flex';
      viewEl.style.display = 'none';
      if (overlayBtn) overlayBtn.classList.add('editable');
      if (btnEdit) btnEdit.style.display = 'none';
    }
  }
};

window.triggerCoverUpload = (event) => {
  if (event) event.stopPropagation();
  const fileInput = document.getElementById('cover-upload-file-input');
  if (fileInput) fileInput.click();
};

window.handleCoverUploadSelect = (event) => {
  const file = event.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const previewImg = document.getElementById('detail-cover-img-preview');
      if (previewImg) {
        previewImg.src = e.target.result;
      }
    };
    reader.readAsDataURL(file);
  }
};

window.handleCoverDrop = (event) => {
  event.preventDefault();
  event.stopPropagation();
  
  // 편집 모드가 활성화되어 있을 때만 드롭 승인
  const editEl = document.getElementById('detail-header-meta-edit');
  if (!editEl || editEl.style.display === 'none') {
    return;
  }
  
  const files = event.dataTransfer.files;
  if (files && files.length > 0) {
    const file = files[0];
    if (file.type.startsWith('image/')) {
      const fileInput = document.getElementById('cover-upload-file-input');
      if (fileInput) {
        // DataTransfer 객체를 통해 드롭된 파일을 Input 요소에 강제 매핑 바인딩
        const container = new DataTransfer();
        container.items.add(file);
        fileInput.files = container.files;
        
        // 미리보기 이미지 갱신
        const reader = new FileReader();
        reader.onload = (e) => {
          const previewImg = document.getElementById('detail-cover-img-preview');
          if (previewImg) {
            previewImg.src = e.target.result;
          }
        };
        reader.readAsDataURL(file);
        console.log('[CoverDrop] 드래그 앤 드롭 표지 파일 바인딩 완료:', file.name);
      }
    } else {
      alert('이미지 파일만 표지로 등록할 수 있습니다.');
    }
  }
};

window.saveManualMetadata = async (seriesName) => {
  const author = document.getElementById('edit-author-input').value.trim();
  const publisher = document.getElementById('edit-publisher-input').value.trim();
  const link = document.getElementById('edit-link-input').value.trim();
  const summary = document.getElementById('edit-summary-input').value.trim();
  const fileInput = document.getElementById('cover-upload-file-input');
  const coverFile = fileInput && fileInput.files ? fileInput.files[0] : null;

  const formData = new FormData();
  formData.append('type', state.currentLibraryType);
  formData.append('series', seriesName);
  formData.append('author', author);
  formData.append('publisher', publisher);
  formData.append('summary', summary);
  formData.append('link', link);
  if (coverFile) {
    formData.append('cover_image', coverFile);
  }

  try {
    const res = await api.editMediaDetail(formData);
    if (res.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(res.message || '정보가 수정되었습니다.', 'success');
      } else {
        alert(res.message || '정보가 수정되었습니다.');
      }
      openBookDetail(null, seriesName);
    } else {
      alert(`수정 실패: ${res.error}`);
    }
  } catch (err) {
    console.error('수동 메타 수정 오류:', err);
    alert('서버 통신 중 오류가 발생했습니다.');
  }
};

/**
 * rescanBook — 단일 도서 즉시 재스캔 실행
 * total_pages=0 또는 커버 없는 볼륨 카드의 "다시 스캔" 버튼에서 호출됩니다.
 */
window.rescanBook = async (event, bookId, seriesName, libraryId) => {
  if (event) event.stopPropagation();

  const btn = event.currentTarget;
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> 스캔 중...';

  try {
    const formData = new FormData();
    formData.append('type', state.currentLibraryType);

    const res = await fetch(`/api/media/books/${bookId}/scan`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (data.success) {
      if (typeof window.showToast === 'function') {
        window.showToast('스캔이 완료되었습니다. 화면을 새로 고칩니다.', 'success');
      }
      // 1초 후 상세 화면 새로고침 (토스트 메시지 표시 시간 확보)
      setTimeout(() => openBookDetail(null, seriesName, libraryId), 1000);
    } else {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      if (typeof window.showToast === 'function') {
        window.showToast(`스캔 실패: ${data.error || '알 수 없는 오류'}`, 'error');
      } else {
        alert(`스캔 실패: ${data.error || '알 수 없는 오류'}`);
      }
    }
  } catch (err) {
    console.error('[rescanBook] 오류:', err);
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    if (typeof window.showToast === 'function') {
      window.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  }
};
