// index.js – 상세 뷰 라이프사이클 관리 (오케스트레이터)
import { state } from '../state.js';
import * as api from '../api.js';
import { switchActiveView } from '../view_manager.js';
import { renderDetailHeader, renderVolumesList, renderRecommendList } from '../detail_render.js';
import { updateCurrentCategoryIndicator } from '../category_indicator.js';
import { detailVolumeViewState } from './volume_controller.js';
import { encodeDetailParams } from '../url_obfuscator.js';
import { bindDetailInteractions } from './interactions.js';
import { createBookCard } from '../ui.js';
import './volume_context_menu.js';

bindDetailInteractions();

if (!document.body.dataset.detailBackDelegated) {
  document.body.dataset.detailBackDelegated = '1';
  document.addEventListener('click', (event) => {
    const backButton = event.target.closest('[data-role="detail-back-to-list"]');
    if (!backButton) return;
    event.preventDefault();
    goBackToList();
  });
}

// 그리드 뷰 → 상세 뷰 전환
export async function openBookDetail(event, seriesName, libraryId, representativeBookId = null, displayTitle = '') {
  const detailView = document.getElementById('book-detail-view');
  if (!detailView) return;

  // 현재 탭에서의 상세 뷰 활성 세션 기록 (새 탭 진입 보안 구분을 위함)
  try {
    sessionStorage.setItem('bookoasis_tab_session', 'active');
  } catch (e) {}

  const safeSeriesName = seriesName || '';
  const safeDisplayTitle = String(displayTitle || '').trim() || safeSeriesName;
  // 전달된 libraryId가 없으면 현재 상태값을 사용하되, 대시보드 시스템성 값이면 'all'로 대체 처리
  const activeLibId = libraryId || state.currentLibraryId || 'all';

  // 현재 화면의 스크롤 위치 저장 (목록/대시보드에서 상세 뷰로 최초 진입하는 경우에만 저장)
  const isAlreadyOpen = detailView && detailView.style.display !== 'none';
  if (!isAlreadyOpen) {
    state.scrollPositions = state.scrollPositions || {};
    const mainContent = document.querySelector('.library-main-content');
    const currentScrollY = (mainContent && mainContent.scrollTop > 0)
      ? mainContent.scrollTop
      : (window.pageYOffset || document.documentElement.scrollTop || 0);

    state.scrollPositions['last_pos'] = currentScrollY;
    state.scrollPositions[state.currentLibraryId] = currentScrollY;
    state.scrollPositions[activeLibId] = currentScrollY;

    console.log(`[Scroll-Debug] SAVED scroll position: ${currentScrollY}px (Current lib: ${state.currentLibraryId}, Active lib: ${activeLibId})`);
  } else {
    console.log(`[Scroll-Debug] PRESERVED existing scroll position: ${state.scrollPositions ? state.scrollPositions['last_pos'] : 0}px (Detail view already open)`);
  }

  // 로딩 표시
  detailView.innerHTML = `
    <button class="btn-back-to-list" data-role="detail-back-to-list">
      <i class="fa-solid fa-arrow-left"></i> ${i18n.t('modal.go_back')}
    </button>
    <div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('modal.loading_detail')}</div>
  `;
  switchActiveView('detail');

  try {
    const data = await api.fetchMediaDetail(state.currentLibraryType, activeLibId, safeSeriesName, representativeBookId);

    if (data.success) {
      const meta = data.meta;
      const books = data.books || [];
      const actualLibraryId = (books.length > 0 && books[0].library_id) ? books[0].library_id : activeLibId;
      state.detailSeriesName = safeSeriesName;
      state.detailLibraryId = actualLibraryId;
      state.detailRepresentativeBookId = representativeBookId || (books.length > 0 ? books[0].id : null);
      state.detailBookIds = books.map(book => Number(book.id)).filter(Number.isFinite);
      state.detailDisplayTitle = safeDisplayTitle;
      state.detailMeta = meta;
      updateCurrentCategoryIndicator(actualLibraryId);

      const detailViewKey = `${state.currentLibraryType || 'general'}:${actualLibraryId}:${safeSeriesName}`;
      if (detailVolumeViewState.key !== detailViewKey) {
        detailVolumeViewState.key = detailViewKey;
        detailVolumeViewState.unreadOnly = false;
        detailVolumeViewState.sortOrder = 'oldest';
      }

      // 상세페이지 본문 렌더러 결정: 이 세션에 코어가 아닌 플러그인이 지정돼 있으면
      // 그 플러그인의 detail_view UI 번들로 header+volumes 영역을 통째로 대체한다.
      // 실패/미지정 시 항상 기존 코어 렌더링으로 폴백한다 (기본값 100% 유지).
      const detailViewPluginId = (state.detailViewProviders && state.detailViewProviders[state.currentLibraryType]) || 'core';
      let pluginDetailBundle = null;
      if (detailViewPluginId !== 'core') {
        try {
          const bundleRes = await api.fetchPluginDetailUiBundle(detailViewPluginId);
          if (bundleRes && bundleRes.success && bundleRes.bundle) {
            pluginDetailBundle = bundleRes.bundle;
          }
        } catch (err) {
          console.error(`[Detail] 플러그인 상세뷰 번들 로드 실패 (${detailViewPluginId}):`, err);
        }
      }

      let mainContentHtml;
      if (pluginDetailBundle) {
        mainContentHtml = (pluginDetailBundle.css ? `<style id="plugin-detail-view-style-${detailViewPluginId}">${pluginDetailBundle.css}</style>` : '')
          + (pluginDetailBundle.html || '');
      } else {
        // 컴포넌트 렌더러 모듈 호출 (기본 코어 렌더링)
        const headerHtml = renderDetailHeader(meta, books, safeSeriesName, actualLibraryId, safeDisplayTitle);
        const volumesSectionHtml = renderVolumesList(
          books,
          safeSeriesName,
          actualLibraryId,
          state.currentLibraryType || 'general',
          detailVolumeViewState
        );
        mainContentHtml = headerHtml + volumesSectionHtml;
      }

      detailView.innerHTML = `
        <button class="btn-back-to-list" data-role="detail-back-to-list">
          <i class="fa-solid fa-arrow-left"></i> ${i18n.t('modal.go_back')}
        </button>
        <div class="detail-page-layout">
          <div class="detail-page-main" id="detail-page-main-content">
            ${mainContentHtml}
          </div>
          <aside class="detail-page-sidebar" id="detail-widget-sidebar" style="display:none;"></aside>
        </div>
      `;

      if (pluginDetailBundle && pluginDetailBundle.js) {
        try {
          const mainEl = document.getElementById('detail-page-main-content');
          const scriptFn = new Function('pluginId', 'container', 'context', pluginDetailBundle.js);
          scriptFn(detailViewPluginId, mainEl, { meta, books, seriesName: safeSeriesName, libraryId: actualLibraryId });
        } catch (err) {
          console.error(`[Detail] 플러그인 상세뷰 스크립트 실행 오류 (${detailViewPluginId}):`, err);
        }
      }

      // 도서 상세 사이드바 위젯(플러그인) 로드 - 본문 렌더링을 막지 않도록 논블로킹으로 로드.
      // 예전엔 "이 작가의 다른 도서"가 코어에 하드코딩돼 있었으나, 플러그인 개발자들이
      // "관련도서"/"유사한 태그 도서" 등 다른 알고리즘이나 아예 다른 성격의 위젯(예: 이 책에
      // 어울리는 음악 추천)으로 자유롭게 교체하고 싶다는 요청이 많아 detail_sidebar_widget
      // 플러그인 계약으로 완전히 분리했다 - 코어 기본값은 sample_plugins/metadata/
      // author_other_books 참조 구현이며, 설치 여부는 관리자의 선택이다.
      // 사이드바는 폭 고정(336px, 카드 2열)이고 본문은 flex:1이라, 사이드바가 없거나
      // 숨겨져도 본문이 자동으로 남는 공간을 채운다 - 별도 폭 조정 클래스가 필요 없다.
      (async () => {
        if (state.bookRecommendEnabled === false) return; // 설정 > 내 설정의 "도서 추천기능" 해제 시 요청 자체를 안 보냄
        const sidebar = document.getElementById('detail-widget-sidebar');
        if (!sidebar) return;
        try {
          // 목록 조회 + 위젯별 데이터 조회 2회 왕복이던 것을 서버에서 한 번에 묶어 반환하도록
          // 통합 - 위젯이 1개뿐인 기본 설치 상태에서도 상세 페이지를 열 때마다 불필요한
          // 네트워크 왕복이 추가되는 걸 막는다.
          const res = await api.fetchDetailSidebarWidgets(state.currentLibraryType || 'general', safeSeriesName, actualLibraryId);
          if (!res.success || !Array.isArray(res.widgets) || res.widgets.length === 0) return;

          let sectionsRendered = 0;
          res.widgets.forEach((widget) => {
            if (!Array.isArray(widget.items) || widget.items.length === 0) return;

            const section = document.createElement('div');
            section.className = 'detail-sidebar-widget-section';
            section.dataset.pluginId = widget.id;
            section.innerHTML = `<h3 class="detail-sidebar-title">${escapeHtml(widget.title)}</h3><div class="detail-sidebar-grid"></div>`;
            const grid = section.querySelector('.detail-sidebar-grid');

            widget.items.forEach((item) => {
              grid.appendChild(renderDetailSidebarWidgetItem(item, actualLibraryId));
            });

            sidebar.appendChild(section);
            sectionsRendered += 1;
          });

          if (sectionsRendered > 0) sidebar.style.display = '';
        } catch (err) {
          console.error('[Detail] 사이드바 위젯 로드 실패:', err);
        }
      })();

      // 헤더의 정적 점수 별(.detail-score) → 커뮤니티 별점 위젯 대체 시도. rating_widget을
      // 선언한 플러그인이 없거나(설치 안 함) 이 세션(성인/오디오북/영상)에서 배제되면
      // 서버가 success:false를 주고, 그 경우 renderDetailHeader가 이미 그려둔 기존 정적
      // 별을 그대로 둔다(폴백) - detail_view가 본문을 통째로 대체한 경우는 이 자리 자체가
      // 없으므로 건너뛴다.
      if (!pluginDetailBundle) {
        (async () => {
          const scoreRoot = document.getElementById('detail-score-root');
          if (!scoreRoot) return;
          const libType = state.currentLibraryType || 'general';
          const ratingContext = {
            seriesName: safeSeriesName,
            libraryId: actualLibraryId,
            bookId: state.detailRepresentativeBookId,
            author: meta.author || '',
            isbn: meta.isbn || '',
          };
          try {
            const res = await api.fetchRatingWidget(libType, ratingContext);
            if (!res.success) return; // 활성 provider 없음 - 기존 정적 별 유지
            renderInteractiveRatingStars(scoreRoot, libType, ratingContext, res);
          } catch (err) {
            console.error('[Detail] 별점 위젯 로드 실패:', err);
          }
        })();
      }

      // 메타데이터 비동기 로드 추천 후보군 검색
      const triggerRecommendSearch = () => {
        const recSection = document.getElementById('meta-recommend-section');
        const recList = document.getElementById('recommend-candidates-list');
        if (recSection && recList) {
          recSection.style.display = 'block';
          recList.innerHTML = `<div style="font-size:0.75rem; color: var(--app-text-muted);"><i class="fa-solid fa-circle-notch fa-spin"></i> 추천 후보를 찾는 중...</div>`;
          api.fetchMetaRecommend(state.currentLibraryType, seriesName).then(res => {
            if (res.success && res.recommends && res.recommends.length > 0) {
              recList.innerHTML = renderRecommendList(res.recommends, seriesName);

              // 적용 버튼 클릭 이벤트 바인딩
              recList.querySelectorAll('.btn-apply-meta').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                  const sourceBookId = e.target.dataset.sourceId;
                  const confirmApply = confirm(i18n.t('modal.copy_confirm', {seriesName: seriesName}));
                  if (!confirmApply) return;

                  e.target.disabled = true;
                  e.target.innerText = i18n.t('modal.applying');

                  const formData = new FormData();
                  formData.append('type', state.currentLibraryType);
                  formData.append('target_series', safeSeriesName);
                  formData.append('target_library_id', actualLibraryId);
                  formData.append('source_book_id', sourceBookId);

                  try {
                    const copyRes = await api.copyMetadata(formData);
                    if (copyRes.success) {
                      alert(copyRes.message);
                      openBookDetail(null, safeSeriesName, actualLibraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
                    } else {
                      alert(i18n.t('modal.apply_fail', {error: copyRes.error}));
                      e.target.disabled = false;
                      e.target.innerText = '이 정보로 채우기';
                    }
                  } catch (err) {
                    console.error('메타데이터 복사 오류:', err);
                    alert(i18n.t('modal.server_error'));
                    e.target.disabled = false;
                    e.target.innerText = '이 정보로 채우기';
                  }
                });
              });
            } else {
              recList.innerHTML = `<div style="font-size:0.75rem; color: var(--app-text-muted);">${i18n.t('modal.no_recommend')}</div>`;
            }
          }).catch(err => {
            console.error('추천 데이터 로드 실패:', err);
            recList.innerHTML = `<div style="font-size:0.75rem; color:#ef4444;">${i18n.t('modal.recommend_fail')}</div>`;
          });
        }
      };

      // 메타데이터가 공란이거나 기본 설명일 때 자동 트리거 분기
      // (영상 강좌는 show.yaml 스캔 메타 전용이라 도서용 메타 추천 검색 대상이 아님)
      const isMetaEmpty = (state.currentLibraryType !== 'video') && (!meta.summary || meta.summary === '등록된 설명이 없습니다.');
      if (isMetaEmpty) {
        triggerRecommendSearch();
      } else {
        const btnManual = document.getElementById('btn-manual-meta-search');
        if (btnManual) {
          btnManual.style.display = 'inline-block';
          btnManual.addEventListener('click', () => {
            btnManual.style.display = 'none';
            triggerRecommendSearch();
          });
        }
      }

      const repIdForHistory = state.detailRepresentativeBookId || '';
      const displayTitleForHistory = state.detailDisplayTitle || '';
      const currentType = state.currentLibraryType || 'general';
      const obfuscatedQuery = encodeDetailParams({
        series: safeSeriesName,
        libraryId: actualLibraryId,
        repBookId: repIdForHistory || null,
        displayTitle: displayTitleForHistory || null,
        type: currentType
      });
      const detailHash = `#detail?${obfuscatedQuery}`;
      const previousHistoryState = history.state;
      const previousReturnState = previousHistoryState?.view === 'detail'
        ? (previousHistoryState.returnState || null)
        : (previousHistoryState && typeof previousHistoryState === 'object' ? previousHistoryState : null);
      const returnLibraryId = previousReturnState?.libraryId ?? state.currentLibraryId;
      const savedReturnScroll = state.scrollPositions?.[String(returnLibraryId)]
        ?? state.scrollPositions?.last_pos
        ?? 0;
      const returnState = previousReturnState
        ? {
          ...previousReturnState,
          scrollTop: previousReturnState.scrollTop ?? Number(savedReturnScroll),
        }
        : null;
      const detailHistoryState = {
        view: 'detail',
        type: currentType,
        series: safeSeriesName,
        libraryId: actualLibraryId,
        sourceLibraryId: state.currentLibraryId || actualLibraryId,
        repBookId: repIdForHistory || null,
        displayTitle: displayTitleForHistory || null,
        returnState,
      };

      if (!window.location.hash.startsWith('#detail')) {
        history.pushState(detailHistoryState, '', detailHash);
      } else {
        history.replaceState(detailHistoryState, '', detailHash);
      }

      if (!isAlreadyOpen) {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    } else {
      detailView.innerHTML = `
        <button class="btn-back-to-list" data-role="detail-back-to-list">
          <i class="fa-solid fa-arrow-left"></i> ${i18n.t('modal.go_back')}
        </button>
        <div class="loading-spinner">${i18n.t('modal.load_detail_fail', {error: data.error || ''})}</div>
      `;
    }
  } catch (e) {
    console.error('[detail] openBookDetail 에러:', e);
    detailView.innerHTML = `
      <button class="btn-back-to-list" data-role="detail-back-to-list">
        <i class="fa-solid fa-arrow-left"></i> ${i18n.t('modal.go_back')}
      </button>
      <div class="loading-spinner">${i18n.t('modal.load_detail_error')}</div>
    `;
  }
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// 헤더의 .detail-score 자리를 클릭 가능한 커뮤니티 별점(0.5 단위)으로 그린다. widgetData는
// {average, count, my_rating} 형태(GET/POST 응답 공통 스키마).
// 별 아이콘이 작아 클릭 좌표로 반개/정수를 구분하기 어려우므로, 클릭 횟수로 구분한다:
// 싱글클릭 = 그 별의 반개(X.5), 더블클릭 = 그 별의 정수점(X.0). 브라우저가 더블클릭 시에도
// click을 두 번 먼저 쏘고 그다음 dblclick을 쏘는 점을 이용해 - click은 화면만 즉시 갱신하고
// 실제 제출은 짧게 지연시켰다가, 그사이 dblclick이 오면 그 지연을 취소하고 정수점을 대신
// 제출한다(중복 relay 호출 방지). 실패 시 커밋 이전 상태로 롤백한다.
function renderInteractiveRatingStars(root, libType, ratingContext, widgetData) {
  const COMMIT_DELAY_MS = 400; // 표준 더블클릭 간격보다 넉넉히 길게 잡아 오조작을 줄인다
  let pendingTimer = null;

  const starClass = (state) => {
    if (state === 'full') return 'fa-solid fa-star is-filled';
    if (state === 'half') return 'fa-solid fa-star-half-stroke is-filled';
    return 'fa-regular fa-star';
  };

  const draw = (data, disabled) => {
    const myRating = Math.max(0, Math.min(5, Math.round((Number(data.my_rating) || 0) * 2) / 2));
    const avgText = data.count > 0
      ? `<span class="detail-score-summary">(${data.count}명 평균 ${Number(data.average || 0).toFixed(1)})</span>`
      : '';
    let starsHtml = '';
    for (let i = 1; i <= 5; i += 1) {
      const state = myRating >= i ? 'full' : (myRating >= i - 0.5 ? 'half' : 'empty');
      starsHtml += `<i class="detail-score-star ${starClass(state)}" data-rating="${i}"></i>`;
    }
    root.innerHTML = `<span class="detail-score-interactive"${disabled ? ' data-disabled="1"' : ''}>${starsHtml}</span>${avgText}`;
  };

  draw(widgetData, false);

  const commit = async (rating) => {
    if (root.querySelector('[data-disabled="1"]')) return;
    const previous = { average: widgetData.average, count: widgetData.count, my_rating: widgetData.my_rating };
    draw({ average: widgetData.average, count: widgetData.count, my_rating: rating }, true);

    try {
      const res = await api.submitRating(libType, ratingContext, rating);
      if (!res.success) {
        alert(res.error || '별점 제출에 실패했습니다.');
        draw(previous, false);
        return;
      }
      widgetData = res;
      draw(res, false);
    } catch (err) {
      console.error('[Detail] 별점 제출 실패:', err);
      alert('별점 제출 중 오류가 발생했습니다.');
      draw(previous, false);
    }
  };

  root.addEventListener('click', (event) => {
    const starEl = event.target.closest('.detail-score-star');
    if (!starEl || root.querySelector('[data-disabled="1"]')) return;
    const starIndex = parseInt(starEl.dataset.rating, 10);
    if (!Number.isFinite(starIndex)) return;

    const halfRating = starIndex - 0.5;
    draw({ average: widgetData.average, count: widgetData.count, my_rating: halfRating }, false);

    if (pendingTimer) clearTimeout(pendingTimer);
    pendingTimer = setTimeout(() => {
      pendingTimer = null;
      commit(halfRating);
    }, COMMIT_DELAY_MS);
  });

  root.addEventListener('dblclick', (event) => {
    const starEl = event.target.closest('.detail-score-star');
    if (!starEl || root.querySelector('[data-disabled="1"]')) return;
    const starIndex = parseInt(starEl.dataset.rating, 10);
    if (!Number.isFinite(starIndex)) return;

    if (pendingTimer) {
      clearTimeout(pendingTimer);
      pendingTimer = null;
    }
    commit(starIndex);
  });
}

// 도서 상세 사이드바 위젯 아이템 1개 렌더링.
// 대시보드 위젯(dashboard_widget)과 동일한 아이템 스키마를 공유한다:
// - item_type: 'metric' -> 도서와 무관한 자유 형식 카드 (예: "이 도서 무드 음악")
// - link(외부 URL) -> 새 탭으로 여는 단순 링크 카드
// - book_id/series_name -> 코어 도서로 연결되는 카드(클릭 시 상세 이동, "이어읽기" 지원)
function renderDetailSidebarWidgetItem(item, fallbackLibraryId) {
  if (item && (item.item_type === 'metric' || item.metric)) {
    const el = document.createElement('div');
    el.className = 'dashboard-metric-card';
    const metric = escapeHtml(item.metric || item.title || '');
    const value = escapeHtml(item.value || '');
    const desc = item.description ? `<span class="dashboard-metric-desc">${escapeHtml(item.description)}</span>` : '';
    el.innerHTML = `<span class="dashboard-metric-label">${metric}</span><strong class="dashboard-metric-value">${value}</strong>${desc}`;
    return el;
  }

  const link = item && item.link;
  if (link && link !== '#') {
    const el = document.createElement('a');
    el.className = 'detail-sidebar-link-card';
    el.href = link;
    el.target = '_blank';
    el.rel = 'noopener noreferrer';
    el.innerHTML = `
      ${item.cover ? `<img class="detail-sidebar-link-card-cover" src="${escapeHtml(item.cover)}" alt="">` : ''}
      <span class="detail-sidebar-link-card-title">${escapeHtml(item.title || link)}</span>
    `;
    return el;
  }

  const seriesName = item && item.series_name;
  const libraryId = (item && item.library_id != null) ? item.library_id : fallbackLibraryId;
  const bookId = item && item.book_id;
  return createBookCard({
    id: bookId,
    representative_book_id: bookId,
    series_name: seriesName || item.title || '',
    cover_image: item.cover,
    file_format: item.file_format,
    library_id: libraryId,
  }, {
    actionTitle: '이어읽기',
    onPrimaryClick: (e) => openBookDetail(e, seriesName || item.title, libraryId, bookId, seriesName || item.title),
    onActionClick: (e) => {
      if (typeof window.resumeSeries === 'function') {
        window.resumeSeries(e, seriesName, libraryId, bookId);
      }
    },
  });
}

// 상세 뷰 → 그리드 뷰/대시보드 복귀
export function goBackToList(triggerBack = true) {
  updateCurrentCategoryIndicator(state.currentLibraryId);

  const isMobileLayout = window.matchMedia('(max-width: 1200px)').matches;
  const avoidDocumentScrollRestore = !triggerBack && isMobileLayout;

  const targetScroll = (state.scrollPositions && (
    state.scrollPositions['last_pos'] ?? 
    state.scrollPositions[state.currentLibraryId]
  )) || 0;

  console.log(`[Scroll-Debug] RESTORING scroll position to: ${targetScroll}px (Current lib: ${state.currentLibraryId})`);

  if (state.currentLibraryId === 'home') {
    switchActiveView('dashboard');
  } else {
    switchActiveView('grid');
  }

  // 상세에서 돌아올 때 저장된 스크롤 위치가 있으면 즉시 및 렌더 후 다중 복원
  const doScroll = (pos) => {
    if (avoidDocumentScrollRestore) {
      // 모바일 OS back(popstate) 경로에서는 문서 스크롤을 올리지 않고,
      // 실제 리스트 컨테이너만 복원해 상단 카테고리 UI 이탈을 방지한다.
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
    } else {
      window.scrollTo(0, pos);
      document.documentElement.scrollTop = pos;
      document.body.scrollTop = pos;
    }
    const mainContent = document.querySelector('.library-main-content');
    if (mainContent) mainContent.scrollTop = pos;
    const gridView = document.getElementById('books-grid-view');
    const dashView = document.getElementById('library-dashboard-view');
    if (gridView) gridView.scrollTop = pos;
    if (dashView) dashView.scrollTop = pos;
  };

  if (targetScroll > 0) {
    try {
      doScroll(targetScroll);
      requestAnimationFrame(() => doScroll(targetScroll));
      setTimeout(() => doScroll(targetScroll), 50);
      setTimeout(() => doScroll(targetScroll), 150);
    } catch (e) {
      console.warn('[goBackToList] failed to restore scroll', e);
    }
  }

  // 상세를 보는 동안 스캔이 끝났다면 그사이 무효화된 목록만 지금 다시 불러온다.
  if (state.currentLibraryId !== 'home' && typeof window.refreshBooksListIfStale === 'function') {
    window.refreshBooksListIfStale();
  }

  // 상세 뷰 해시(#detail)가 남아있는 경우 브라우저 외부/홈으로 튕김(history.back) 없이 해시만 안전하게 제거
  if (window.location.hash.startsWith('#detail')) {
    try {
      history.replaceState({ view: 'list', libraryId: state.currentLibraryId }, '', window.location.pathname + window.location.search);
    } catch (e) {}
  }
}
