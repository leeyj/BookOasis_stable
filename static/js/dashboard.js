// dashboard.js – 대시보드 데이터 로드 및 수평 휠/버튼 스크롤 제어
import { state } from './state.js';
import * as api from './api.js';
import { renderDashboardHistory, renderDashboardRecentlyAdded } from './ui.js?v=20260809-unread-series-v3';
import { updateLibraryTotalCount } from './book_list.js';
import { loadPluginHealthPanel } from './plugin_health_panel.js';

let dashboardLoadToken = 0;
let pluginsLoadToken = 0;
let dashboardRowLastType = null;

// 대시보드 섹션 제목("최근 읽은 도서"/"신규 추가 도서")은 오디오북/영상 강좌 세션에서도
// "도서" 문구를 그대로 쓰고 있었다 - 상단 총계 배지(book_list.js::updateLibraryTotalCount)와
// 동일한 이유로 세션 타입별 라벨을 따로 둔다.
function updateDashboardSectionLabels(targetType) {
  const recentTitleEl = document.getElementById('dashboard-recent-title');
  const recentSuffixEl = document.getElementById('dashboard-recent-title-suffix');
  const newTitleEl = document.getElementById('dashboard-new-title');

  const recentKey = targetType === 'audiobook'
    ? 'dashboard.recent_title_audiobook'
    : targetType === 'video'
      ? 'dashboard.recent_title_video'
      : 'dashboard.recent_title';
  const newKey = targetType === 'audiobook'
    ? 'dashboard.new_books_title_audiobook'
    : targetType === 'video'
      ? 'dashboard.new_books_title_video'
      : 'dashboard.new_books_title';
  const suffixKey = targetType === 'video'
    ? 'dashboard.recent_title_suffix_video'
    : 'dashboard.recent_title_suffix';

  if (recentTitleEl) recentTitleEl.textContent = i18n.t(recentKey);
  if (newTitleEl) newTitleEl.textContent = i18n.t(newKey);
  if (recentSuffixEl) recentSuffixEl.textContent = i18n.t(suffixKey);
}

export async function loadDashboardData() {
  const requestToken = ++dashboardLoadToken;
  const targetType = state.currentLibraryType || 'general';
  state.isLoading = true;

  updateDashboardSectionLabels(targetType);

  const historyRow = document.getElementById('dashboard-history-row');
  const newRow = document.getElementById('dashboard-new-row');
  const countSpan = document.getElementById('library-total-count');
  if (countSpan) countSpan.innerText = '';

  const isTypeSwitched = dashboardRowLastType !== targetType;
  dashboardRowLastType = targetType;

  // 탭 타입 전환 시 이전 탭의 카드를 즉시 지우고 로딩 스피너로 초기화 (1~2초 잔상 현상 방지)
  if (isTypeSwitched || (historyRow && !historyRow.children.length)) {
    if (historyRow) historyRow.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 최근 항목을 불러오는 중...</div>';
  }
  if (isTypeSwitched || (newRow && !newRow.children.length)) {
    if (newRow) newRow.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 신규 항목을 불러오는 중...</div>';
  }
  
  try {
    // 0. 독서 동기부여 위젯 로드
    if (typeof window.loadDashboardInsights === 'function') {
      window.loadDashboardInsights(targetType);
    }

    // 0-1. 플러그인 로드 상태 패널 (관리자 전용, 나머지 대시보드 로딩을 막지 않도록 별도 실행)
    loadPluginHealthPanel();

    // 0-2. 홈 화면 플러그인 배치 모드 레이아웃. 코어 3섹션은 정적 HTML에 항상 이미 존재해서
    // fetch를 아무리 빨리 해도 "기본 배치로 먼저 페인트된 뒤 → 재배치/카드 삽입"이라는 2단계
    // 자체가 눈에 보이는 리플로우로 남는다(fetch 타이밍 문제가 아니었음). 그래서 레이아웃이
    // 확정되기 전까지 스택 전체를 미리 숨겨두고, loadHomeDashboardLayout()이 배치를 다 끝낸
    // 뒤 한 번에 드러낸다 - 타입 전환 시 historyRow/newRow에 스피너를 넣는 것과 같은 원리.
    const homeWidgetStackEl = document.getElementById('home-widget-stack');
    if (state.homeDashboardPluginMode) {
      if (homeWidgetStackEl) homeWidgetStackEl.classList.add('home-widget-stack--loading');
      loadHomeDashboardLayout(targetType, { allowSsr: true }).catch((e) => {
        console.error('[Dashboard] 홈 위젯 레이아웃 적용 실패:', e);
        if (homeWidgetStackEl) homeWidgetStackEl.classList.remove('home-widget-stack--loading');
      });
    }

    // 1. 전체 보관함 합계, 최근 읽은 도서, 신규 추가 도서를 동시에 요청
    const totalsPromise = api.fetchBooksTotals({type: targetType, libraryId: 'all'})
      .catch(err => ({ success: false, error: String(err) }));
    const historyPromise = api.fetchReadingHistory(targetType);
    const recentlyAddedPromise = fetch(`/api/media/recently-added?type=${targetType}&_=${Date.now()}`, {cache: 'no-store'})
      .then(res => res.json())
      .catch(err => ({ success: false, error: String(err) }));

    const [totalsData, historyData, newData] = await Promise.all([totalsPromise, historyPromise, recentlyAddedPromise]);
    if (requestToken !== dashboardLoadToken) return;
    if (state.currentLibraryId !== 'home' || state.currentLibraryType !== targetType) return;

    if (totalsData && totalsData.success) {
      updateLibraryTotalCount([], totalsData);
    }

    // 최근 읽은 도서 렌더링
    if (historyData && historyData.success) {
      let books = historyData.books || [];
      if (state.hideCompletedInHistory) {
        books = books.filter(b => {
          const fmt = String(b.file_format || '').toLowerCase();
          const isAudiobook = fmt === 'audiobook' || fmt === 'audio';
          return isAudiobook
            ? (b.is_completed !== 1)
            : !(b.is_completed === 1 || (b.total_pages > 0 && b.pages_read >= b.total_pages));
        });
      }
      renderDashboardHistory(books);
    } else {
      // 서버 예외 원문(DB 엔진/테이블명 등 내부 정보 포함 가능)을 화면에 그대로 노출하지 않고
      // 콘솔에만 남긴다 - 사용자에게는 일반적인 실패 메시지만 보여준다.
      if (historyData && historyData.error) console.error('[Dashboard] 히스토리 로드 실패:', historyData.error);
      if (historyRow) historyRow.innerHTML = `<div class="loading-spinner">${i18n.t('dashboard.history_load_fail') || '히스토리를 불러오지 못했습니다.'}</div>`;
    }

    // 신규 추가 도서 렌더링
    if (newData && newData.success) {
      renderDashboardRecentlyAdded(newData.books);
    } else {
      if (newData && newData.error) console.error('[Dashboard] 신규 도서 로드 실패:', newData.error);
      if (newRow) newRow.innerHTML = `<div class="loading-spinner">${i18n.t('dashboard.new_books_load_fail') || '신규 도서를 불러오지 못했습니다.'}</div>`;
    }

  } catch (e) {
    if (requestToken !== dashboardLoadToken) return;
    console.error('대시보드 데이터 로드 오류:', e);
    if (historyRow) historyRow.innerHTML = '<div class="loading-spinner">서버 연결 오류</div>';
    if (newRow) newRow.innerHTML = '<div class="loading-spinner">서버 연결 오류</div>';
  } finally {
    if (requestToken === dashboardLoadToken) {
      state.isLoading = false;
    }
  }
}


let homeLayoutLoadToken = 0;

// 최초 페이지 로드 시 서버(services/home_dashboard_service.py)가 이미 db_type='general' 기준
// 최종 순서로 #home-widget-stack을 렌더링해뒀다(data-ssr-* 속성 참고). 그 순서를 딱 한 번
// "소비"할 기회를 이 플래그로 표시한다 - 세션 타입이 일치하면 재조회 없이 이미 그려진 DOM을
// 그대로 인정하고 상호작용(Sortable/위젯 데이터)만 붙인다. 코어 위젯이 기본 배치로 먼저
// 그려졌다가 JS가 재배치하며 생기던 리플로우를 근본적으로 없애기 위함
// (docs/plan_home_dashboard_pluginization.md 참고). 세션이 안 맞거나 이미 한 번 썼으면 그
// 뒤로는 항상 기존 fetch 경로를 탄다.
let homeLayoutSsrChecked = false;

// 서버가 마지막으로 내려준 "현재 레이아웃에 실제로 포함된" 위젯 id 목록. 코어 3섹션의
// DOM 래퍼는 제거해도 항상 #home-widget-stack에 남아있고 display:none으로만 숨겨지기
// 때문에, 드래그 재정렬/위젯 추가·제거 시 DOM을 그대로 스캔하면 이미 뺀 코어 섹션이
// "숨김 상태로 다시 레이아웃에 포함"되며 부활해버린다 - 그래서 저장할 때는 항상 이
// 목록으로 "진짜 포함된" id만 걸러낸다.
let lastHomeWidgetOrder = [];

function getPresentWidgetOrder(stack) {
  const presentIds = new Set(lastHomeWidgetOrder.map((w) => w.id));
  return Array.from(stack.children)
    .filter((el) => el.classList && el.classList.contains('home-widget-slot') && presentIds.has(el.getAttribute('data-widget-id')))
    .map((el) => ({ id: el.getAttribute('data-widget-id'), hidden: el.style.display === 'none' }));
}

// "보이는 슬롯 중 첫 번째가 아닌 'full' 슬롯"에만 구분선을 그려준다 - 재정렬/숨김으로
// 순서가 바뀌어도 고정 <hr>과 달리 항상 올바른 위치에만 남는다. 'grid' 위젯끼리는
// 카드 자체 테두리로 이미 구분되므로 divider를 적용하지 않되, "이전에 보이는 위젯이
// 있었는지" 판단에는 grid/full 구분 없이 포함시킨다.
export function refreshHomeWidgetDividers() {
  const stack = document.getElementById('home-widget-stack');
  if (!stack) return;
  let seenVisible = false;
  Array.from(stack.children).forEach((el) => {
    if (!el.classList || !el.classList.contains('home-widget-slot')) return;
    const hidden = el.style.display === 'none';
    const isFull = el.classList.contains('home-widget-slot--full');
    el.classList.toggle('home-widget-slot--divider', !hidden && isFull && seenVisible);
    if (!hidden) seenVisible = true;
  });
}
window.refreshHomeWidgetDividers = refreshHomeWidgetDividers;

// 서버가 이미 렌더해둔 순서를 그대로 인정하고, fetch/DOM 재배치 없이 상호작용(Sortable,
// 위젯 데이터 fetch)만 붙인다. 플러그인 카드는 서버가 껍데기(제목/아이콘/자리)까지는
// 그려뒀지만 콘텐츠(get_dashboard_data)는 아직 없으므로 그것만 병렬로 채운다.
function consumeSsrHomeLayout(stack, requestToken) {
  const ssrMode = stack.dataset.ssrMode;

  if (ssrMode !== 'plugin') {
    // 서버가 이미 클래식 순서(코어 3개, 기본 배치)로 렌더링해뒀다 - 할 일 없음
    lastHomeWidgetOrder = [];
    stack.classList.remove('home-widget-stack--loading');
    return;
  }

  stack.classList.add('home-widget-stack--plugin-mode');
  lastHomeWidgetOrder = Array.from(stack.children)
    .filter((el) => el.classList && el.classList.contains('home-widget-slot'))
    .map((el) => ({ id: el.getAttribute('data-widget-id'), hidden: el.style.display === 'none' }));

  refreshHomeWidgetDividers();
  stack.classList.remove('home-widget-stack--loading');

  if (typeof Sortable !== 'undefined') {
    stack.__homeSortable = Sortable.create(stack, {
      animation: 180,
      ghostClass: 'dragging',
      onEnd: function () {
        const order = getPresentWidgetOrder(stack);
        lastHomeWidgetOrder = order;
        api.updateUserSetting('HOME_WIDGET_LAYOUT', JSON.stringify(order)).catch((e) => {
          console.error('[Dashboard] 홈 위젯 순서 저장 실패:', e);
        });
        refreshHomeWidgetDividers();
      }
    });
  }

  const dataFetchPromises = [];
  stack.querySelectorAll('.home-widget-slot[data-widget-kind="plugin"]').forEach((el) => {
    if (requestToken !== homeLayoutLoadToken) return;
    if (el.style.display === 'none') return;
    const pluginId = el.getAttribute('data-plugin-id');
    const limit = Number(el.getAttribute('data-limit')) || 10;
    const contentId = `home-widget-content-${el.getAttribute('data-widget-id')}`;
    dataFetchPromises.push(loadDashboardWidgetData(pluginId, limit, contentId, pluginsLoadToken));
  });
  Promise.all(dataFetchPromises).catch((e) => {
    console.error('[Dashboard] SSR 홈 위젯 데이터 로드 실패:', e);
  });

  // 카탈로그(+ 위젯 추가 버튼)도 서버가 이미 그려뒀다 - 버튼 클릭은 전역 delegation이 처리한다.
}

// 사용자가 "내 설정 > 홈 화면 플러그인 배치 모드"를 켠 경우, /api/media/home-layout이
// 계산해준 순서대로 코어 3섹션 + home_widget 플러그인 카드를 #home-widget-stack 안에서
// 재배치한다. 꺼져 있으면(mode !== 'plugin') 코어 섹션을 기본 DOM 순서로 되돌리고
// 이전에 동적으로 삽입된 플러그인 카드를 정리한다 - 설계는
// docs/plan_home_dashboard_pluginization.md 참고.
export async function loadHomeDashboardLayout(targetType, { allowSsr = false } = {}) {
  const requestToken = ++homeLayoutLoadToken;
  const stack = document.getElementById('home-widget-stack');
  if (!stack) return;

  // SSR 스냅샷은 "자연스러운 최초 로드" 경로(loadDashboardData)에서만 소비를 시도한다.
  // 위젯 추가/제거, 순서 변경, 설정 화면에서 모드를 방금 켠 뒤의 명시적 재조회처럼 "지금 막
  // 바뀐 걸 반영해야 하는" 호출에서 SSR을 쓰면, 페이지가 그려질 때의 낡은 스냅샷을 최신
  // 상태로 착각해 방금의 변경이 반영 안 된 것처럼 보일 수 있다.
  if (allowSsr && !homeLayoutSsrChecked) {
    homeLayoutSsrChecked = true;
    if (stack.dataset.ssrType === targetType && stack.dataset.ssrMode) {
      consumeSsrHomeLayout(stack, requestToken);
      return;
    }
  }

  let data;
  try {
    data = await api.fetchHomeLayout(targetType);
  } catch (e) {
    console.error('[Dashboard] 홈 레이아웃 조회 실패:', e);
    return;
  }
  if (requestToken !== homeLayoutLoadToken) return;

  // 이전 로드에서 동적으로 삽입한 플러그인 위젯 카드는 매번 새로 그린다 (중복/오염 방지)
  stack.querySelectorAll('.home-widget-slot[data-widget-kind="plugin"]').forEach((el) => el.remove());

  if (stack.__homeSortable) {
    stack.__homeSortable.destroy();
    stack.__homeSortable = null;
  }

  if (!data || !data.success || data.mode !== 'plugin') {
    // 클래식 모드: 코어 3섹션을 원래 순서로 되돌린다. 독서 인사이트 표시 여부는
    // SHOW_DASHBOARD_INSIGHTS 사용자 설정(theme_settings.js)이 별도로 관리하므로 건드리지 않는다.
    stack.classList.remove('home-widget-stack--plugin-mode');
    lastHomeWidgetOrder = [];
    ['core.reading_insights', 'core.recent', 'core.new'].forEach((id) => {
      const el = stack.querySelector(`[data-widget-id="${id}"]`);
      if (!el) return;
      stack.appendChild(el);
      if (id !== 'core.reading_insights') el.style.display = '';
    });
    refreshHomeWidgetDividers();
    renderHomeWidgetCatalog([]);
    stack.classList.remove('home-widget-stack--loading');
    return;
  }

  // 플러그인 배치 모드: 코어 3섹션도 사용자가 닫을 수 있으므로, data.widgets에 없는 코어
  // 섹션은(=닫아서 레이아웃에서 빠진 것) 여기서 명시적으로 숨긴다. 아래 for문은 widgets에
  // '있는' 항목만 처리하기 때문에 없는 항목은 별도로 다뤄야 한다.
  stack.classList.add('home-widget-stack--plugin-mode');
  const widgets = Array.isArray(data.widgets) ? data.widgets : [];
  lastHomeWidgetOrder = widgets.map((w) => ({ id: w.id, hidden: !!w.hidden }));
  const presentCoreIds = new Set(widgets.filter((w) => w.kind === 'core').map((w) => w.id));
  ['core.reading_insights', 'core.recent', 'core.new'].forEach((id) => {
    if (presentCoreIds.has(id)) return;
    const el = stack.querySelector(`[data-widget-id="${id}"]`);
    if (el) el.style.display = 'none';
  });

  // 위젯 데이터 조회(get_dashboard_data)는 위젯별로 독립적인 API 호출이라, 카드를 하나
  // 그릴 때마다 순서대로 await하면 위젯 수만큼 왕복이 그대로 직렬로 쌓인다 - 카드는 순서대로
  // 즉시 다 그려 넣고, 데이터 fetch만 한꺼번에 병렬로 실행한다.
  const dataFetchPromises = [];

  for (const widget of widgets) {
    if (requestToken !== homeLayoutLoadToken) return;

    if (widget.kind === 'core') {
      const el = stack.querySelector(`[data-widget-id="${widget.id}"]`);
      if (!el) continue;
      stack.appendChild(el);
      // 독서 인사이트는 자체 설정으로 이미 숨겨져 있을 수 있으므로 명시적으로 숨김일 때만 덮어쓴다
      if (widget.hidden) el.style.display = 'none';
      else if (widget.id !== 'core.reading_insights') el.style.display = '';
      continue;
    }

    // 플러그인 위젯: 공통 데스크 탭([플러그인] 탭)과 동일한 카드 마크업/데이터 소스
    // (get_dashboard_data → loadDashboardWidgetData)를 그대로 재사용한다.
    const widgetId = widget.id;
    const contentId = `home-widget-content-${widgetId}`;
    const iconClass = widget.icon || 'fa-solid fa-puzzle-piece';
    const title = escapeHtml(widget.title || widget.plugin_id || widgetId);
    const provider = escapeHtml(widget.provider || widget.title || 'Plugin');
    const subtitle = widget.subtitle ? `<div class="plugin-widget-subtitle">${escapeHtml(widget.subtitle)}</div>` : '';
    let layoutClass = ' home-widget-slot--full';
    if (widget.layout === 'grid') {
      const span = Number(widget.size) || 1;
      layoutClass = span >= 3 ? ' home-widget-slot--span-3' : (span === 2 ? ' home-widget-slot--span-2' : '');
    }

    const cardHtml = `
      <div class="plugin-card home-widget-slot${layoutClass}" id="home-widget-${widgetId}" data-widget-id="${widgetId}" data-widget-kind="plugin" data-plugin-id="${widget.plugin_id}" data-limit="${Number(widget.limit) || 10}"${widget.hidden ? ' style="display:none;"' : ''}>
          <h4 class="plugin-card-header">
              <span class="plugin-card-header-title"><i class="${iconClass}"></i><span class="plugin-card-header-title-text">${title}</span></span>
              <span class="plugin-card-provider">제공: ${provider}</span>
              <button type="button" class="home-widget-remove-btn" data-remove-widget-id="${widgetId}" title="홈 화면에서 위젯 제거"><i class="fa-solid fa-xmark"></i></button>
          </h4>
          ${subtitle}
          <div id="${contentId}" class="plugin-widget-body">
              <div class="loading-spinner loading-spinner--widget"><i class="fa-solid fa-circle-notch fa-spin"></i> 위젯 데이터를 불러오는 중...</div>
          </div>
      </div>
    `;
    stack.insertAdjacentHTML('beforeend', cardHtml);
    if (!widget.hidden) {
      dataFetchPromises.push(loadDashboardWidgetData(widget.plugin_id, Number(widget.limit) || 10, contentId, pluginsLoadToken));
    }
  }

  await Promise.all(dataFetchPromises);

  if (requestToken !== homeLayoutLoadToken) return;
  refreshHomeWidgetDividers();

  // 순서 변경은 데스크 탭(localStorage)과 달리 기기 간 동기화가 필요한 "내 홈 화면"이므로
  // 서버 개인화 설정(HOME_WIDGET_LAYOUT)에 즉시 저장한다.
  if (typeof Sortable !== 'undefined') {
    stack.__homeSortable = Sortable.create(stack, {
      animation: 180,
      ghostClass: 'dragging',
      onEnd: function () {
        const order = getPresentWidgetOrder(stack);
        lastHomeWidgetOrder = order;
        api.updateUserSetting('HOME_WIDGET_LAYOUT', JSON.stringify(order)).catch((e) => {
          console.error('[Dashboard] 홈 위젯 순서 저장 실패:', e);
        });
        refreshHomeWidgetDividers();
      }
    });
  }

  renderHomeWidgetCatalog(data.catalog || []);
  stack.classList.remove('home-widget-stack--loading');
}

// 아직 레이아웃에 추가하지 않은 home_widget 플러그인 목록을 "+ 위젯 추가" 버튼 그룹으로
// 보여준다. 설치된 플러그인이 늘어나도 사용자가 명시적으로 고른 것만 홈 화면에 쌓이도록
// 하기 위한 카탈로그다 (2026-09-07 결정, docs/plan_home_dashboard_pluginization.md 참고).
function renderHomeWidgetCatalog(catalog) {
  const el = document.getElementById('home-widget-catalog');
  if (!el) return;

  if (!Array.isArray(catalog) || catalog.length === 0) {
    el.style.display = 'none';
    el.innerHTML = '';
    return;
  }

  el.style.display = 'flex';
  el.innerHTML = `
    <span class="home-widget-catalog-label"><i class="fa-solid fa-plus"></i> 위젯 추가:</span>
    ${catalog.map((w) => `
      <button type="button" class="home-widget-catalog-btn" data-add-widget-id="${escapeHtml(w.id)}">
        <i class="${w.icon || 'fa-solid fa-puzzle-piece'}"></i> ${escapeHtml(w.title || w.plugin_id || w.id)}
      </button>
    `).join('')}
  `;
}

// 서버가 마지막으로 내려준 "실제 포함된" 순서(lastHomeWidgetOrder)를 기준으로
// HOME_WIDGET_LAYOUT을 변경(추가/제거)하고 저장한다. DOM을 직접 스캔하지 않는 이유는
// getPresentWidgetOrder() 주석 참고 - 코어 섹션은 제거해도 DOM에는 hidden 상태로 남기 때문.
// mutateFn은 {id, hidden}[] 배열을 받아 새 배열을 반환해야 한다.
async function mutateHomeWidgetLayout(mutateFn) {
  const next = mutateFn(lastHomeWidgetOrder);
  lastHomeWidgetOrder = next;
  await api.updateUserSetting('HOME_WIDGET_LAYOUT', JSON.stringify(next));
}

if (!window.__homeWidgetCatalogDelegationBound) {
  document.addEventListener('click', async (event) => {
    const addBtn = event.target.closest('[data-add-widget-id]');
    if (addBtn) {
      const widgetId = addBtn.getAttribute('data-add-widget-id');
      addBtn.disabled = true;
      try {
        await mutateHomeWidgetLayout((current) => (
          current.some((w) => w.id === widgetId) ? current : [...current, { id: widgetId, hidden: false }]
        ));
        await loadHomeDashboardLayout(state.currentLibraryType || 'general');
      } catch (e) {
        console.error('[Dashboard] 홈 위젯 추가 실패:', e);
        addBtn.disabled = false;
      }
      return;
    }

    const removeBtn = event.target.closest('[data-remove-widget-id]');
    if (removeBtn) {
      const widgetId = removeBtn.getAttribute('data-remove-widget-id');
      try {
        await mutateHomeWidgetLayout((current) => current.filter((w) => w.id !== widgetId));
        await loadHomeDashboardLayout(state.currentLibraryType || 'general');
      } catch (e) {
        console.error('[Dashboard] 홈 위젯 제거 실패:', e);
      }
    }
  });
  window.__homeWidgetCatalogDelegationBound = true;
}

export async function loadDashboardPlugins(requestToken = null) {
  const section = document.getElementById('dashboard-plugins-section');
  const container = document.getElementById('dashboard-plugins-container');
  const tabsContainer = document.getElementById('plugins-view-tabs');
  const dynamicWrapper = document.getElementById('plugins-dynamic-contents-wrapper');

  if (!section || !container) return;

  const currentToken = requestToken !== null ? requestToken : ++pluginsLoadToken;

  // 1. 이전 동적 생성 탭 및 콘텐츠 초기화
  if (tabsContainer) {
    tabsContainer.querySelectorAll('.plugin-dynamic-tab-btn').forEach(btn => btn.remove());
  }
  if (dynamicWrapper) {
    dynamicWrapper.innerHTML = '';
  }
  container.innerHTML = '';

  try {
    const res = await fetch(`/api/media/dashboard/widgets?type=${state.currentLibraryType}`);
    const data = await res.json();

    if (currentToken !== pluginsLoadToken) return;

    if (data.success && data.widgets && data.widgets.length > 0) {
      section.style.display = 'block';

      // 순서 복원을 위한 정렬 리스트 획득
      let savedOrder = [];
      try {
        savedOrder = JSON.parse(localStorage.getItem('plugins_order') || '[]');
      } catch (err) {}

      // widgets 정렬 처리 (all_desk_tab가 없고 순서 저장이 있는 경우 우선 적용)
      const commonWidgets = data.widgets.filter(w => !w.all_desk_tab);
      const tabWidgets = data.widgets.filter(w => w.all_desk_tab);

      commonWidgets.sort((a, b) => {
        const idxA = savedOrder.indexOf(a.id);
        const idxB = savedOrder.indexOf(b.id);
        if (idxA !== -1 && idxB !== -1) return idxA - idxB;
        if (idxA !== -1) return -1;
        if (idxB !== -1) return 1;
        return 0;
      });

      // 위젯별 get_dashboard_data 호출은 서로 독립적이라 카드 그릴 때마다 순서대로 await하면
      // 위젯 수만큼 왕복이 직렬로 쌓인다 - 카드는 순서대로 즉시 그려 넣고 데이터 fetch만
      // 한꺼번에 병렬로 실행한다.
      const dataFetchPromises = [];

      // 2. 공통 데스크 위젯 카드 렌더링
      for (const widget of commonWidgets) {
        if (currentToken !== pluginsLoadToken) return;

        const widgetId = String(widget.id || '').trim();
        if (!widgetId) continue;

        const contentId = `dashboard-widget-content-${widgetId}`;
        const iconClass = widget.icon || 'fa-solid fa-puzzle-piece';
        const title = escapeHtml(widget.title || widget.name || widgetId);
        const provider = escapeHtml(widget.provider || widget.name || 'Plugin');
        const subtitle = widget.subtitle ? `<div class="plugin-widget-subtitle">${escapeHtml(widget.subtitle)}</div>` : '';

        const cardHtml = `
          <div class="plugin-card" id="plugin-${widgetId}">
              <h4 class="plugin-card-header">
                  <span class="plugin-card-header-title"><i class="${iconClass}"></i><span class="plugin-card-header-title-text">${title}</span></span>
                  <span class="plugin-card-provider">제공: ${provider}</span>
              </h4>
              ${subtitle}
              <div id="${contentId}" class="plugin-widget-body">
                  <div class="loading-spinner loading-spinner--widget"><i class="fa-solid fa-circle-notch fa-spin"></i> 위젯 데이터를 불러오는 중...</div>
              </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', cardHtml);
        dataFetchPromises.push(loadDashboardWidgetData(widgetId, Number(widget.limit) || 10, contentId, currentToken));
      }

      // 3. 독점 탭 플러그인 구성
      for (const widget of tabWidgets) {
        if (currentToken !== pluginsLoadToken) return;

        const widgetId = String(widget.id || '').trim();
        if (!widgetId) continue;

        const contentId = `dashboard-widget-content-${widgetId}`;
        const iconClass = widget.icon || 'fa-solid fa-puzzle-piece';
        const title = escapeHtml(widget.title || widget.name || widgetId);
        const provider = escapeHtml(widget.provider || widget.name || 'Plugin');
        const subtitle = widget.subtitle ? `<div class="plugin-widget-subtitle plugin-widget-subtitle--tab">${escapeHtml(widget.subtitle)}</div>` : '';

        // 탭 버튼 생성
        if (tabsContainer) {
          const tabBtnHtml = `
            <button class="settings-tab-btn plugin-dynamic-tab-btn" id="tab-btn-${widgetId}" data-role="plugins-view-tab" data-plugin-tab="${widgetId}">
              <i class="${iconClass}"></i> <span>${title}</span>
            </button>
          `;
          tabsContainer.insertAdjacentHTML('beforeend', tabBtnHtml);
        }

        // 탭 본문 생성
        if (dynamicWrapper) {
          const tabContentHtml = `
            <div class="plugins-tab-content plugin-dynamic-tab-content" id="plugins-content-${widgetId}">
              <div class="dashboard-section">
                <div class="section-header">
                  <h3 class="section-title">
                    <i class="${iconClass}"></i> <span>${title}</span>
                  </h3>
                  <span class="plugin-tab-provider">제공: ${provider}</span>
                </div>
                ${subtitle}
                <div id="${contentId}" class="plugin-tab-widget-body">
                  <div class="loading-spinner loading-spinner--widget-grid"><i class="fa-solid fa-circle-notch fa-spin"></i> 데이터를 불러오는 중...</div>
                </div>
              </div>
            </div>
          `;
          dynamicWrapper.insertAdjacentHTML('beforeend', tabContentHtml);
        }

        dataFetchPromises.push(loadDashboardWidgetData(widgetId, Number(widget.limit) || 12, contentId, currentToken));
      }

      await Promise.all(dataFetchPromises);
      if (currentToken !== pluginsLoadToken) return;

      // 4. Sortable 활성화 (공통 데스크 카드들)
      if (typeof Sortable !== 'undefined' && container && commonWidgets.length > 0) {
        Sortable.create(container, {
          animation: 180,
          ghostClass: 'dragging',
          onEnd: function () {
            const newOrder = Array.from(container.children).map(child => child.id.replace('plugin-', ''));
            localStorage.setItem('plugins_order', JSON.stringify(newOrder));
          }
        });
      }

    } else {
      section.style.display = 'none';
      container.innerHTML = '';
    }
  } catch (e) {
    console.error('대시보드 위젯 로드 오류:', e);
    section.style.display = 'none';
  }
}

// 플러그인 뷰 내부 탭 전환 함수
export function switchPluginsViewTab(tabId) {
  // 1. 버튼 활성화 클래스 조율
  const tabsContainer = document.getElementById('plugins-view-tabs');
  if (tabsContainer) {
    tabsContainer.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(tabId === 'common-desk' ? 'tab-btn-common-desk' : `tab-btn-${tabId}`);
    if (activeBtn) activeBtn.classList.add('active');
  }

  // 2. 본문 활성화 전환
  document.querySelectorAll('.plugins-tab-content').forEach(el => {
    el.style.display = 'none';
  });

  const activeContent = document.getElementById(tabId === 'common-desk' ? 'plugins-content-common-desk' : `plugins-content-${tabId}`);
  if (activeContent) {
    activeContent.style.display = 'flex';
  }
}
window.switchPluginsViewTab = switchPluginsViewTab;

if (!window.__pluginsViewTabDelegationBound) {
  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="plugins-view-tab"], [data-role="dashboard-widget-item"]')
      : null;
    if (!target) return;

    console.log('[Dashboard-Delegation] Delegation target clicked:', target);
    event.preventDefault();
    if (target.getAttribute('data-role') === 'plugins-view-tab') {
      switchPluginsViewTab(target.getAttribute('data-plugin-tab') || 'common-desk');
      return;
    }

    const action = target.getAttribute('data-item-action');
    if (action === 'open-reader' && typeof window.openReader === 'function') {
      const bookId = Number.parseInt(target.getAttribute('data-book-id') || '', 10);
      const pagesRead = Number.parseInt(target.getAttribute('data-pages-read') || '0', 10) || 0;
      const totalPages = Number.parseInt(target.getAttribute('data-total-pages') || '0', 10) || 0;
      console.log('[Dashboard-Delegation] Delegated open-reader:', { bookId, pagesRead, totalPages });
      if (Number.isFinite(bookId) && bookId > 0) {
        window.openReader(bookId, target.getAttribute('data-file-format') || '', target.getAttribute('data-book-title') || '', pagesRead, totalPages);
      }
      return;
    }

    if (action === 'open-detail' && typeof window.openBookDetail === 'function') {
      console.log('[Dashboard-Delegation] Delegated open-detail:', target.getAttribute('data-series-name'));
      window.openBookDetail(event, target.getAttribute('data-series-name') || '', target.getAttribute('data-library-id') || null);
    }
  }, true);
  window.__pluginsViewTabDelegationBound = true;
}

async function loadDashboardWidgetData(pluginId, limit, contentId, requestToken) {
  if (requestToken !== pluginsLoadToken) return;

  const container = document.getElementById(contentId);
  if (!container) return;

  try {
    const res = await fetch(`/api/media/dashboard/widgets/${encodeURIComponent(pluginId)}/data?type=${state.currentLibraryType}&limit=${limit}`);
    const data = await res.json();

    if (requestToken !== pluginsLoadToken) return;

    if (data.success && Array.isArray(data.items) && data.items.length > 0) {
      container.innerHTML = '';
      data.items.forEach(item => {
        if (item && (item.item_type === 'metric' || item.metric)) {
          const metric = formatDashboardMetricText(item.metric || item.title || '통계');
          const value = formatDashboardMetricText(item.value || '-');
          const desc = formatDashboardMetricText(item.description || '');
          const metricHtml = `
            <div class="dashboard-metric-card">
              <span class="dashboard-metric-label">${metric}</span>
              <strong class="dashboard-metric-value">${value}</strong>
              ${desc ? `<span class="dashboard-metric-desc">${desc}</span>` : ''}
            </div>
          `;
          container.insertAdjacentHTML('beforeend', metricHtml);
          return;
        }

        const cover = item.cover || 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=100&auto=format&fit=crop&q=60';
        const title = escapeHtml(item.title || '제목 없음');
        const author = escapeHtml(item.author || '저자 미상');
        const publisher = escapeHtml(item.publisher || '출판사 미상');
        const pubDate = escapeHtml(item.pubDate || '');
        const link = item.link || '#';
        const isExternal = link && link !== '#';
        const rawSeriesName = String(item.series_name || item.series || '');
        const rawLibraryId = String(item.library_id || item.libraryId || '');
        const rawBookId = item.book_id || item.bookId || null;
        const rawFileFormat = item.file_format || item.format || '';
        const rawTitle = item.title || '';
        const rawPagesRead = item.pages_read || item.pagesRead || 0;
        const rawTotalPages = item.total_pages || item.totalPages || 0;

        let clickAttr = '';
        let isClickable = false;
        if (!isExternal) {
            if (rawBookId && rawFileFormat) {
            clickAttr = `data-role="dashboard-widget-item" data-item-action="open-reader" data-book-id="${rawBookId}" data-file-format="${escapeHtml(rawFileFormat)}" data-book-title="${escapeHtml(rawTitle)}" data-pages-read="${rawPagesRead}" data-total-pages="${rawTotalPages}"`;
                isClickable = true;
            } else if (rawSeriesName) {
            clickAttr = `data-role="dashboard-widget-item" data-item-action="open-detail" data-series-name="${escapeHtml(rawSeriesName)}" data-library-id="${escapeHtml(rawLibraryId)}"`;
                isClickable = true;
            }
        }

        const itemHtml = `
          <div class="plugin-item-card${isClickable ? ' plugin-item-card--clickable' : ''}" data-series-name="${escapeHtml(rawSeriesName)}" data-library-id="${escapeHtml(rawLibraryId)}" data-book-id="${rawBookId || ''}" data-file-format="${escapeHtml(rawFileFormat)}" ${clickAttr}>
            <div class="plugin-item-cover">
              <img src="${cover}" alt="cover">
            </div>
            <div class="plugin-item-info">
              <a class="plugin-item-title" href="${isExternal ? link : '#'}" ${isExternal ? 'target="_blank" rel="noopener noreferrer"' : ''} title="${title}">${title}</a>
              <span class="plugin-item-meta">${author}</span>
              <div class="plugin-item-footer">
                <span class="plugin-item-publisher">${publisher}</span>
                <span class="plugin-item-pubdate">${pubDate}</span>
              </div>
            </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', itemHtml);
      });
    }
  } catch (e) {
    console.error(`대시보드 위젯 로드 오류(${pluginId}):`, e);
    container.innerHTML = '<div class="plugin-widget-error">서버 연결 오류</div>';
  }
}

function formatDashboardMetricText(value) {
  // metric/value/description 필드: 안전한 HTML 태그 허용
  return sanitizePluginHtml(value)
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\r\n/g, '\n');
}

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
 * title/author/publisher 같은 고유명사 필드에는 사용하지 말 것 (escapeHtml 유지).
 * metric/value/description/subtitle 같은 플러그인 콘텐츠 필드에만 사용할 것.
 */
function sanitizePluginHtml(value) {
  const raw = String(value || '');

  // 1단계: 위험 태그 완전 제거 (script, iframe, object, embed, form, input, style)
  const DANGEROUS_TAGS = /(<\s*\/?(script|iframe|object|embed|form|input|button|select|textarea|style|link|meta|base|svg|math)[^>]*>)/gi;
  let sanitized = raw.replace(DANGEROUS_TAGS, '');

  // 2단계: on* 이벤트 속성 제거 (onclick, onerror, onload 등)
  sanitized = sanitized.replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '');

  // 3단계: href/src의 javascript: 프로토콜 제거
  sanitized = sanitized.replace(/(href|src)\s*=\s*["']?\s*javascript:[^"'>]*/gi, '$1="#"');

  // 4단계: 허용 태그 화이트리스트 외 모든 태그 이스케이프
  const ALLOWED_TAGS = new Set(['b', 'i', 'em', 'strong', 'br', 'span', 'a', 'ul', 'ol', 'li', 'p', 'small', 'mark', 'code']);
  sanitized = sanitized.replace(/<(\/?)(\w+)([^>]*)>/g, (match, slash, tag, attrs) => {
    const lowerTag = tag.toLowerCase();
    if (!ALLOWED_TAGS.has(lowerTag)) {
      // 허용 목록에 없는 태그는 텍스트로 이스케이프
      return match.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    if (lowerTag === 'a') {
      // <a> 태그: href, title, target만 허용 (rel="noopener" 강제)
      const hrefMatch = attrs.match(/href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]*))/i);
      const titleMatch = attrs.match(/title\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      const href = hrefMatch ? (hrefMatch[1] || hrefMatch[2] || hrefMatch[3] || '#') : '#';
      const title = titleMatch ? ` title="${escapeHtml(titleMatch[1] || titleMatch[2] || '')}"` : '';
      const safeHref = /^(https?:\/\/|\/)/.test(href) ? href : '#';
      return `<a href="${escapeHtml(safeHref)}"${title} target="_blank" rel="noopener noreferrer">`;
    }
    if (lowerTag === 'span') {
      // <span>: class, style만 허용 (style은 color/font-weight/font-style만)
      const styleMatch = attrs.match(/style\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      if (styleMatch) {
        const styleVal = styleMatch[1] || styleMatch[2] || '';
        // color, font-weight, font-style, font-size, text-decoration만 허용
        const safeStyle = styleVal.split(';')
          .filter(rule => /^\s*(color|font-weight|font-style|font-size|text-decoration)\s*:/i.test(rule))
          .join(';');
        return safeStyle ? `<span style="${escapeHtml(safeStyle)}">` : '<span>';
      }
      return '<span>';
    }
    // 그 외 허용 태그: 속성 전체 제거 (태그 이름만 유지)
    return `<${slash}${lowerTag}>`;
  });

  return sanitized;
}
