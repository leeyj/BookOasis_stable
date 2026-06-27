// metadata_search.js – 통합 도서 메타데이터 검색 및 선택 적용 모듈
import { state } from './state.js';
import * as api from './api.js';

let currentTargetBookId = null;
let currentSeriesName = null;
let isSeriesMode = false;
let cachedPlugins = null; // 플러그인 캐시

/**
 * 메타데이터 검색 모달창을 오픈하고 검색 소스 목록을 동적으로 구성합니다.
 */
export async function openMetadataSearchModal(bookId, defaultQuery, seriesMode = false) {
  currentTargetBookId = bookId;
  isSeriesMode = seriesMode;
  currentSeriesName = seriesMode ? defaultQuery : null;
  const modal = document.getElementById('metadata-search-modal');
  const input = document.getElementById('metadata-search-input');
  const container = document.getElementById('metadata-results-container');
  const sourceSelect = document.getElementById('metadata-search-source');
  
  if (!modal || !input || !sourceSelect) return;
  
  // 1. 활성화된 플러그인 드롭다운 목록 동적 로드 (최초 1회 캐시)
  if (!cachedPlugins) {
    sourceSelect.innerHTML = '<option value="">로딩 중...</option>';
    try {
      const data = await api.fetchMetadataPlugins();
      if (data.success && data.plugins && data.plugins.length > 0) {
        cachedPlugins = data.plugins;
      }
    } catch (err) {
      console.error('메타데이터 플러그인 목록 로드 실패:', err);
    }
  }

  // 드롭다운 채우기
  if (cachedPlugins && cachedPlugins.length > 0) {
    sourceSelect.innerHTML = cachedPlugins.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
  } else {
    sourceSelect.innerHTML = '<option value="aladin">알라딘 도서 검색 (기본)</option>';
  }
  
  // 2. 검색어 정제 (괄호나 대괄호에 든 불필요한 메타단어 제거로 검색 성공률 상승)
  let cleanQuery = defaultQuery || '';
  cleanQuery = cleanQuery.replace(/\[.*?\]|\(.*?\)/g, '').trim();
  
  input.value = cleanQuery;
  container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #94a3b8;">검색 소스를 선택하고 검색 버튼을 누르면 수색을 시작합니다.</div>';
  
  modal.style.display = 'flex';
  
  // 기본 검색어가 있으면 즉시 검색 가동
  if (cleanQuery) {
    performMetadataSearch();
  }
}

/**
 * 모달창을 닫고 상태를 초기화합니다.
 */
export function closeMetadataSearchModal() {
  const modal = document.getElementById('metadata-search-modal');
  if (modal) modal.style.display = 'none';
  currentTargetBookId = null;
  currentSeriesName = null;
  isSeriesMode = false;
}

/**
 * 백엔드 공통 API를 때려 선택된 검색 소스로 메타데이터를 검색합니다.
 */
export async function performMetadataSearch() {
  const input = document.getElementById('metadata-search-input');
  const container = document.getElementById('metadata-results-container');
  const sourceSelect = document.getElementById('metadata-search-source');
  if (!input || !container || !sourceSelect) return;
  
  const query = input.value.trim();
  const source = sourceSelect.value;
  
  if (!query) {
    alert('검색어를 입력해 주세요.');
    return;
  }
  
  const selectedSourceName = sourceSelect.options[sourceSelect.selectedIndex]?.text || '도서 정보';
  container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #a855f7;"><i class="fa-solid fa-circle-notch fa-spin fa-2x"></i><br><br>${selectedSourceName} 수색 중...</div>`;
  
  try {
    const data = await api.searchMetadata(state.currentLibraryType, query, source);
    if (data.success && data.results && data.results.length > 0) {
      renderMetadataResults(data.results, source);
    } else {
      container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #f43f5e;">검색 결과가 없거나 오류가 발생했습니다: ${data.error || '검색어와 일치하는 도서가 존재하지 않습니다.'}</div>`;
    }
  } catch (err) {
    console.error('메타데이터 검색 API 에러:', err);
    container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #f43f5e;">서버와 통신 중 오류가 발생했습니다.</div>';
  }
}

/**
 * 검색 결과를 모달 내 결과 영역에 렌더링합니다.
 */
function renderMetadataResults(books, source) {
  const container = document.getElementById('metadata-results-container');
  if (!container) return;
  
  let html = '';
  books.forEach((book, idx) => {
    let desc = book.description || '책 설명이 존재하지 않습니다.';
    if (desc.length > 150) {
      desc = desc.substring(0, 150) + '...';
    }
    
    html += `
      <div class="metadata-result-card" style="display: flex; gap: 1rem; background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 1rem; cursor: pointer; transition: all 0.2s;" data-index="${idx}">
        <div style="flex-shrink: 0; width: 80px; height: 110px; background: rgba(15, 23, 42, 0.5); border-radius: 4px; overflow: hidden; display: flex; align-items: center; justify-content: center;">
          <img src="${book.cover || '/static/images/default_cover.jpg'}" alt="Cover" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.src='/static/images/default_cover.jpg'">
        </div>
        <div style="flex: 1; display: flex; flex-direction: column; gap: 0.3rem;">
          <h4 style="margin: 0; color: #fff; font-size: 0.95rem; font-weight: 700;">${book.title}</h4>
          <div style="font-size: 0.8rem; color: #94a3b8;">
            <span>저자: ${book.author}</span> | <span>출판사: ${book.publisher}</span> | <span>출간일: ${book.pubDate}</span>
          </div>
          <p style="margin: 0.3rem 0 0 0; font-size: 0.78rem; color: #cbd5e1; line-height: 1.4;">${desc}</p>
        </div>
      </div>
    `;
  });
  
  container.innerHTML = html;
  
  const cards = container.querySelectorAll('.metadata-result-card');
  cards.forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.style.background = 'rgba(168, 85, 247, 0.1)';
      card.style.borderColor = '#a855f7';
    });
    card.addEventListener('mouseleave', () => {
      card.style.background = 'rgba(30, 41, 59, 0.4)';
      card.style.borderColor = 'rgba(255,255,255,0.06)';
    });
    
    card.addEventListener('click', () => {
      const index = parseInt(card.dataset.index);
      selectMetadataBook(books[index], source);
    });
  });
}

/**
 * 사용자가 특정 책 메타데이터를 선택했을 때 DB에 최종 매핑 적용합니다.
 */
async function selectMetadataBook(book, source) {
  if (!currentTargetBookId) return;
  
  const confirmMsg = isSeriesMode
    ? `▶ 선택한 도서 정보로 시리즈 전체 메타데이터를 덮어쓰시겠습니까?\n\n- 제목: ${book.title}\n- 저자: ${book.author}\n- 출판사: ${book.publisher}\n\n※ 적용 시 기존의 시리즈 표지와 작품 설명 정보가 대체됩니다.`
    : `▶ 선택한 도서 정보로 덮어쓰시겠습니까?\n\n- 제목: ${book.title}\n- 저자: ${book.author}\n- 출판사: ${book.publisher}\n\n※ 적용 시 기존의 표지와 책 상세 설명 정보가 대체됩니다.`;
    
  const confirmApply = confirm(confirmMsg);
  if (!confirmApply) return;
  
  import('./view_manager.js').then(async (vm) => {
    vm.showToast('도서 정보 적용 중...', 'info');
    try {
      // 1단계: 첫 번째 책에 플러그인 메타데이터 적용
      const res = await api.applyMetadata(state.currentLibraryType, currentTargetBookId, book, source);
      if (res.success) {
        if (isSeriesMode && currentSeriesName) {
          // 2단계: 시리즈 모드일 경우 첫 번째 책에 저장된 정보를 기반으로 시리즈 전체 전파
          // (별도의 백엔드 전파 API를 호출하는 대신, 기존 editMediaDetail API를 재활용하여 텍스트 및 다운로드된 썸네일 경로를 일괄 전파)
          
          // 다운로드 완료된 표지 파일명을 획득하기 위해 우선 타겟 도서 상세 재조회
          // 다운로드 완료된 표지 파일명을 획득하기 위해 우선 타겟 도서 상세 재조회
          const detailRes = await api.fetchMediaDetail(state.currentLibraryType, state.currentLibraryId, currentSeriesName);
          if (detailRes.success) {
            const firstBook = detailRes.books[0];
            const updatedMeta = detailRes.meta;
            
            const formData = new FormData();
            formData.append('type', state.currentLibraryType);
            formData.append('series', currentSeriesName);
            formData.append('author', updatedMeta.author || book.author);
            formData.append('publisher', updatedMeta.publisher || book.publisher);
            formData.append('summary', updatedMeta.summary || book.description);
            formData.append('link', updatedMeta.link || book.link || '');
            
            // 만약 플러그인에 의해 책 커버가 다운로드되었다면, 시리즈 대표 이미지로 복사 전파
            // (백엔드 BookDetailService.update_media_detail에서 cover_file 유무에 따른 JPG 저장을 처리함)
            if (firstBook && firstBook.cover_image) {
              // file_path를 fetch하여 blob으로 변환하거나, 백엔드에서 복사할 수 있도록 설계
              // 여기서는 다운로드받은 첫 번째 책의 cover_image 경로를 서버측에서 인지하고
              // 시리즈 대표 이미지(series_{hash}.jpg)로 자동 복원 및 복사하는 복사 전파 API가 유용함.
              // 백엔드의 copy_metadata가 이를 완벽히 처리하므로, copy_metadata API를 호출합니다.
              const copyFormData = new FormData();
              copyFormData.append('type', state.currentLibraryType);
              copyFormData.append('target_series', currentSeriesName);
              copyFormData.append('target_library_id', state.currentLibraryId);
              copyFormData.append('source_book_id', currentTargetBookId);
              
              await api.copyMetadata(copyFormData);
            }
          }
          
          vm.showToast('시리즈 메타데이터가 일괄 적용되었습니다.', 'success');
          closeMetadataSearchModal();
          if (typeof window.openBookDetail === 'function') {
            const activeLibId = (history.state && history.state.libraryId) ? history.state.libraryId : state.currentLibraryId;
            window.openBookDetail(null, currentSeriesName, activeLibId);
          }
        } else {
          vm.showToast(res.message, 'success');
          closeMetadataSearchModal();
          
          // 현재 상세 보기(Detail View)가 활성화되어 있는 경우, 리스트로 돌아가지 않고 상세 화면만 갱신
          const isDetailActive = history.state && history.state.view === 'detail';
          const activeSeries = history.state ? history.state.series : null;
          const activeLibId = (history.state && history.state.libraryId) ? history.state.libraryId : state.currentLibraryId;
          
          if (isDetailActive && activeSeries && typeof window.openBookDetail === 'function') {
            window.openBookDetail(null, activeSeries, activeLibId);
          } else if (typeof window.selectCategory === 'function') {
            // 그리드 목록 뷰인 경우에만 카테고리 전체 목록 갱신
            window.selectCategory(state.currentLibraryId);
          }
        }
      } else {
        vm.showToast(`적용 실패: ${res.error}`, 'error');
      }
    } catch (err) {
      console.error('메타데이터 적용 API 에러:', err);
      vm.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  });
}

// 글로벌 윈도우 스코프 바인딩 (인라인 HTML 핸들러 대응)
window.openMetadataSearchModal = openMetadataSearchModal;
window.closeMetadataSearchModal = closeMetadataSearchModal;
window.performMetadataSearch = performMetadataSearch;
