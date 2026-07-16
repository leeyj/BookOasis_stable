// metadata_search.js – 통합 도서 메타데이터 검색 및 선택 적용 모듈
import { state } from './state.js';
import * as api from './api.js';
import { buildFallbackCoverUrl } from './cover_fallback.js';

let currentTargetBookId = null;
let currentSeriesName = null;
let isSeriesMode = false;
let cachedPlugins = null; // 플러그인 캐시

export function invalidateSearchModalPluginsCache() {
  cachedPlugins = null;
}
window.invalidateSearchModalPluginsCache = invalidateSearchModalPluginsCache;

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
    sourceSelect.innerHTML = `<option value="">${i18n.t('metadata_search.loading')}</option>`;
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
    sourceSelect.innerHTML = `<option value="aladin">${i18n.t('metadata_search.default_plugin')}</option>`;
  }
  
  // 2. 검색어 정제 (괄호나 대괄호에 든 불필요한 메타단어 제거로 검색 성공률 상승)
  let cleanQuery = defaultQuery || '';
  cleanQuery = cleanQuery.replace(/\[.*?\]|\(.*?\)/g, '').trim();
  
  input.value = cleanQuery;
  container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #94a3b8;">${i18n.t('metadata_search.init_message')}</div>`;
  
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
    alert(i18n.t('metadata_search.empty_query'));
    return;
  }
  
  const selectedSourceName = sourceSelect.options[sourceSelect.selectedIndex]?.text || i18n.t('metadata_search.default_source');
  container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #a855f7;"><i class="fa-solid fa-circle-notch fa-spin fa-2x"></i><br><br>${i18n.t('metadata_search.searching', {source: selectedSourceName})}</div>`;
  
  try {
    const data = await api.searchMetadata(state.currentLibraryType, query, source);
    if (data.success && data.results && data.results.length > 0) {
      renderMetadataResults(data.results, source);
    } else {
      container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #f43f5e;">${i18n.t('metadata_search.search_fail', {error: data.error || i18n.t('metadata_search.no_result')})}</div>`;
    }
  } catch (err) {
    console.error('메타데이터 검색 API 에러:', err);
    container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #f43f5e;">${i18n.t('metadata_search.server_error')}</div>`;
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
    // description: 플러그인이 HTML을 포함할 수 있으므로 sanitize 허용
    let desc = sanitizePluginHtml(book.description || i18n.t('metadata_search.no_description'));
    if (desc.length > 150) {
      desc = desc.substring(0, 150) + '...';
    }
    // title/author/publisher: 고유명사이므로 완전 이스케이프 유지
    const safeTitle = escapeHtml(book.title || '');
    const safeAuthor = escapeHtml(book.author || '');
    const safePublisher = escapeHtml(book.publisher || '');
    const safePubDate = escapeHtml(book.pubDate || '');
    const fallbackCoverSrc = buildFallbackCoverUrl({
      title: book.title || currentSeriesName || 'Untitled',
      format: 'text',
      seed: `${source || 'meta'}:${book.title || ''}:${book.author || ''}`
    });
    const coverSrc = escapeHtml(book.cover || fallbackCoverSrc);
    
    html += `
      <div class="metadata-result-card" style="display: flex; gap: 1rem; background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 1rem; cursor: pointer; transition: all 0.2s;" data-index="${idx}">
        <div style="flex-shrink: 0; width: 80px; height: 110px; background: rgba(15, 23, 42, 0.5); border-radius: 4px; overflow: hidden; display: flex; align-items: center; justify-content: center;">
          <img src="${coverSrc}" alt="Cover" style="width: 100%; height: 100%; object-fit: cover;" onerror="if(this.src.indexOf('/covers/fallback')===-1){this.src='${fallbackCoverSrc}';}else{this.onerror=null; this.src='/static/images/default_cover.jpg';}">
        </div>
        <div style="flex: 1; display: flex; flex-direction: column; gap: 0.3rem;">
          <h4 style="margin: 0; color: #fff; font-size: 0.95rem; font-weight: 700;">${safeTitle}</h4>
          <div style="font-size: 0.8rem; color: #94a3b8;">
            <span>${i18n.t('metadata_search.book_meta', {author: safeAuthor, publisher: safePublisher, pubDate: safePubDate})}</span>
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
    ? i18n.t('metadata_search.confirm_series', {title: book.title, author: book.author, publisher: book.publisher})
    : i18n.t('metadata_search.confirm_single', {title: book.title, author: book.author, publisher: book.publisher});
    
  const confirmApply = confirm(confirmMsg);
  if (!confirmApply) return;
  
  import('./view_manager.js').then(async (vm) => {
    vm.showToast(i18n.t('metadata_search.applying'), 'info');
    console.log('[MetadataApply-DEBUG] 1단계 시작: applyMetadata 호출 준비', {
      libraryType: state.currentLibraryType,
      bookId: currentTargetBookId,
      source: source,
      bookData: book
    });
    try {
      // 1단계: 첫 번째 책에 플러그인 메타데이터 적용
      const res = await api.applyMetadata(state.currentLibraryType, currentTargetBookId, book, source);
      console.log('[MetadataApply-DEBUG] 1단계 결과 (applyMetadata):', res);
      
      if (res.success) {
        if (isSeriesMode && currentSeriesName) {
          console.log('[MetadataApply-DEBUG] 2단계 시작: 시리즈 전파 모드 활성화됨 (isSeriesMode: true)', {
            currentSeriesName: currentSeriesName,
            libraryIdState: state.currentLibraryId
          });
          
          let targetBook = null;
          
          // 다운로드 완료된 표지 파일명을 획득하기 위해 우선 타겟 도서 상세 재조회
          console.log('[MetadataApply-DEBUG] 2.1단계: fetchMediaDetail 호출', {
            libraryId: state.currentLibraryId,
            seriesName: currentSeriesName
          });
          const detailRes = await api.fetchMediaDetail(state.currentLibraryType, state.currentLibraryId, currentSeriesName);
          console.log('[MetadataApply-DEBUG] 2.1단계 결과 (fetchMediaDetail):', detailRes);
          
          if (detailRes.success) {
            console.log('[MetadataApply-DEBUG] 2.2단계: books 리스트에서 targetBook 탐색 시작', {
              targetId: currentTargetBookId,
              booksCount: detailRes.books ? detailRes.books.length : 0
            });
            targetBook = detailRes.books ? detailRes.books.find(b => b.id === currentTargetBookId) : null;
            console.log('[MetadataApply-DEBUG] 2.2단계 targetBook 탐색 완료:', targetBook);
            
            // 플러그인에 의해 도서 메타데이터가 적용되었으므로, 해당 책의 정보를 기반으로 시리즈 내 모든 도서에 텍스트 메타를 복사 전파합니다.
            if (targetBook) {
              const actualLibraryId = targetBook.library_id || state.currentLibraryId;
              console.log('[MetadataApply-DEBUG] 2.3단계: copyMetadata 호출 준비', {
                targetSeriesName: currentSeriesName,
                actualLibraryId: actualLibraryId,
                sourceBookId: currentTargetBookId
              });
              
              const copyFormData = new FormData();
              copyFormData.append('type', state.currentLibraryType);
              copyFormData.append('target_series', currentSeriesName);
              copyFormData.append('target_library_id', actualLibraryId);
              copyFormData.append('source_book_id', currentTargetBookId);
              
              const copyRes = await api.copyMetadata(copyFormData);
              console.log('[MetadataApply-DEBUG] 2.3단계 결과 (copyMetadata):', copyRes);
            } else {
              console.warn('[MetadataApply-DEBUG] [경고] targetBook을 찾지 못해 copyMetadata를 호출하지 못했습니다. targetId:', currentTargetBookId);
            }
          } else {
            console.error('[MetadataApply-DEBUG] [에러] fetchMediaDetail 실패. 전파 실패.');
          }
          
          // closeMetadataSearchModal() 실행 시 전역변수 currentSeriesName이 null로 비워지기 때문에 임시 로컬 변수에 백업해 둡니다.
          const seriesNameToRefresh = currentSeriesName;
          
          vm.showToast(i18n.t('metadata_search.apply_series_success'), 'success');
          closeMetadataSearchModal();
          
          const activeLibId = (targetBook && targetBook.library_id) ? targetBook.library_id : state.currentLibraryId;
          console.log('[MetadataApply-DEBUG] 3단계: openBookDetail 호출하여 화면 갱신 시도', {
            currentSeriesName: seriesNameToRefresh,
            activeLibId: activeLibId
          });
          if (typeof window.openBookDetail === 'function') {
            window.openBookDetail(null, seriesNameToRefresh, activeLibId);
          } else {
            console.error('[MetadataApply-DEBUG] [에러] window.openBookDetail 함수가 정의되어 있지 않습니다.');
          }
        } else {
          console.log('[MetadataApply-DEBUG] 단권/그리드 모드로 완료 처리');
          vm.showToast(res.message, 'success');
          closeMetadataSearchModal();
          
          // 현재 상세 보기(Detail View)가 활성화되어 있는 경우, 리스트로 돌아가지 않고 상세 화면만 갱신
          const isDetailActive = history.state && history.state.view === 'detail';
          const activeSeries = history.state ? history.state.series : null;
          const activeLibId = (history.state && history.state.libraryId) ? history.state.libraryId : state.currentLibraryId;
          
          console.log('[MetadataApply-DEBUG] 단권 갱신 openBookDetail 호출 정보', {
            isDetailActive: isDetailActive,
            activeSeries: activeSeries,
            activeLibId: activeLibId
          });
          
          if (isDetailActive && activeSeries && typeof window.openBookDetail === 'function') {
            window.openBookDetail(null, activeSeries, activeLibId);
          } else if (typeof window.selectCategory === 'function') {
            // 그리드 목록 뷰인 경우에만 카테고리 전체 목록 갱신
            window.selectCategory(state.currentLibraryId);
          }
        }
      } else {
        console.error('[MetadataApply-DEBUG] [에러] res.success가 false입니다.', res.error);
        vm.showToast(i18n.t('metadata_search.apply_fail', {error: res.error}), 'error');
      }
    } catch (err) {
      console.error('[MetadataApply-DEBUG] [예외 발생] 메타데이터 적용 API 에러:', err);
      vm.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  });
}

// 글로벌 윈도우 스코프 바인딩 (인라인 HTML 핸들러 대응)
window.openMetadataSearchModal = openMetadataSearchModal;
window.closeMetadataSearchModal = closeMetadataSearchModal;
window.performMetadataSearch = performMetadataSearch;

// ── XSS 방지 유틸 ────────────────────────────────────────────

/**
 * escapeHtml – 문자열을 HTML 엔티티로 완전 이스케이프 (title/author 등 고유명사용)
 */
function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * sanitizePluginHtml – 플러그인 콘텐츠용 제한적 HTML 허용 함수
 *
 * 허용 태그: b, i, em, strong, br, span, a(href만), ul, ol, li, p, small, mark, code
 * 차단 대상: <script>, <iframe>, <object>, <embed>, on* 이벤트 속성, javascript: href
 *
 * description 같은 플러그인 콘텐츠 필드에만 사용할 것.
 * title/author/publisher 같은 고유명사 필드에는 escapeHtml을 유지할 것.
 */
function sanitizePluginHtml(value) {
  const raw = String(value || '');

  // 1단계: 위험 태그 완전 제거
  const DANGEROUS_TAGS = /(<\s*\/?(script|iframe|object|embed|form|input|button|select|textarea|style|link|meta|base|svg|math)[^>]*>)/gi;
  let sanitized = raw.replace(DANGEROUS_TAGS, '');

  // 2단계: on* 이벤트 속성 제거
  sanitized = sanitized.replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '');

  // 3단계: javascript: 프로토콜 제거
  sanitized = sanitized.replace(/(href|src)\s*=\s*["']?\s*javascript:[^"'>]*/gi, '$1="#"');

  // 4단계: 허용 태그 화이트리스트 외 모든 태그 이스케이프
  const ALLOWED_TAGS = new Set(['b', 'i', 'em', 'strong', 'br', 'span', 'a', 'ul', 'ol', 'li', 'p', 'small', 'mark', 'code']);
  sanitized = sanitized.replace(/<(\/?)([\w]+)([^>]*)>/g, (match, slash, tag, attrs) => {
    const lowerTag = tag.toLowerCase();
    if (!ALLOWED_TAGS.has(lowerTag)) {
      return match.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    if (lowerTag === 'a') {
      const hrefMatch = attrs.match(/href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]*))/i);
      const titleMatch = attrs.match(/title\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      const href = hrefMatch ? (hrefMatch[1] || hrefMatch[2] || hrefMatch[3] || '#') : '#';
      const title = titleMatch ? ` title="${escapeHtml(titleMatch[1] || titleMatch[2] || '')}"` : '';
      const safeHref = /^(https?:\/\/|\/)/.test(href) ? href : '#';
      return `<a href="${escapeHtml(safeHref)}"${title} target="_blank" rel="noopener noreferrer">`;
    }
    if (lowerTag === 'span') {
      const styleMatch = attrs.match(/style\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      if (styleMatch) {
        const styleVal = styleMatch[1] || styleMatch[2] || '';
        const safeStyle = styleVal.split(';')
          .filter(rule => /^\s*(color|font-weight|font-style|font-size|text-decoration)\s*:/i.test(rule))
          .join(';');
        return safeStyle ? `<span style="${escapeHtml(safeStyle)}">` : '<span>';
      }
      return '<span>';
    }
    return `<${slash}${lowerTag}>`;
  });

  return sanitized;
}
