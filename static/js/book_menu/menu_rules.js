// book_menu/menu_rules.js – 도서 컨텍스트 메뉴의 항목 표시/라벨 규칙 (순수 함수, import 없음).
// DOM 반영은 book_context_menu.js가 한다. 새 메뉴 항목을 추가할 때는 여기 규칙 한 줄 +
// book_menu/actions.js의 액션 하나 + templates/components/context_menus.html의 <li> 하나.
// import가 없어야 tests/test_book_menu_rules.mjs가 node에서 그대로 불러 검증할 수 있다.

// 스캔 범위: 시리즈 카드(대표 권 ID만 넘어옴)일 때만 'series'로 서버가 모든 권으로 확장한다.
// 상세 화면의 개별 권 메뉴는 seriesName이 채워져 있어도 그 권 하나만 대상이다.
export function getBookScanScope(book) {
  const selectedBooks = Array.isArray(book?.selectedBooks) ? book.selectedBooks : [];
  if (selectedBooks.length > 1) {
    return selectedBooks.every(item => item.markUnreadScope === 'series') ? 'series' : 'book';
  }
  return !book?.isVolumeDetail && book?.markUnreadScope === 'series' ? 'series' : 'book';
}

export function getLazyScanSeriesTarget(book) {
  if (!book || book.isVolumeDetail || book.markUnreadScope !== 'series') return null;
  const libraryId = Number(book.libraryId);
  const seriesName = String(book.seriesName || '').trim();
  if (!Number.isInteger(libraryId) || libraryId <= 0 || !seriesName) return null;
  return { libraryId, seriesName };
}

export function isLazyScanAllowed(user, libraryType) {
  const dbType = String(libraryType || '').toLowerCase();
  return String(user?.role || '').trim().toLowerCase() === 'admin'
    && ['general', 'adult', 'audiobook'].includes(dbType);
}

/**
 * 메뉴 대상(target)과 환경(env)으로 항목별 표시 상태를 계산한다.
 * target: { isVolumeDetail, selectedBooks, seriesName, markUnreadScope, libraryId, fileFormat, bookCount, hasProgress }
 * env: { lazyScanAllowed, listenable, ttsPregenEnabled, isVideoLibrary, metaSearchAvailable(true|false|null) }
 * 반환: { title, items: { [elementId]: { visible?, action?, iconClass?, iconColor?, labelKey?, labelFallback?, labelText?, setI18n? } } }
 *   visible이 undefined면 표시 상태를 건드리지 않는다. labelKey가 있으면 i18n(labelKey) || labelFallback || 현재 문구.
 */
export function computeBookMenuState(target, env = {}) {
  const selectedBooks = Array.isArray(target?.selectedBooks) ? target.selectedBooks : [];
  const isMulti = selectedBooks.length > 1;
  const count = selectedBooks.length;
  const fmt = String(target?.fileFormat || '').toLowerCase();
  const seriesName = String(target?.seriesName || '').trim();
  const items = {};

  const scanScope = getBookScanScope(target);
  items['ctx-scan-book'] = {
    setI18n: true,
    labelKey: isMulti
      ? (scanScope === 'series' ? 'context_menu.scan_selected_series_now' : 'context_menu.scan_selected_now')
      : (scanScope === 'series' ? 'context_menu.scan_series_now' : 'context_menu.scan_book_now'),
  };

  const lazySeriesTarget = !isMulti ? getLazyScanSeriesTarget(target) : null;
  items['ctx-lazy-scan-book'] = {
    visible: !!env.lazyScanAllowed,
    setI18n: true,
    labelKey: lazySeriesTarget ? 'context_menu.lazy_scan_series' : 'context_menu.lazy_scan_book',
    labelFallback: lazySeriesTarget ? 'Lazy-Scanner 실행 (시리즈 전체)' : 'Lazy-Scanner 실행 (선택/클릭한 작품)',
  };

  // "페이지 넘김으로 보기(실험적)"는 이미지 기반 만화(zip/cbz)에서만 의미가 있음
  items['ctx-page-turn-book'] = { visible: !isMulti && (fmt === 'zip' || fmt === 'cbz') };
  // "음성으로 듣기"는 브라우저에서 텍스트를 합성하므로 듣기 가능한 형식(TXT/EPUB)에서만 노출
  items['ctx-tts-book'] = { visible: !isMulti && !!env.listenable };
  // "음성 미리 만들기"는 관리자가 서버 미리 만들기를 켰을 때만
  items['ctx-tts-pregen-book'] = { visible: !isMulti && !!env.ttsPregenEnabled && !!env.listenable };

  items['ctx-add-series-to-collection'] = {
    visible: isMulti ? selectedBooks.every(book => String(book.seriesName || '').trim()) : !!seriesName,
  };

  // "커버 정렬"은 개별 권(볼륨) 카드에서만 의미가 있음 (시리즈 집계 카드는 어느 권을 정렬할지
  // 모호함) - 메인 그리드에서도 book_count===1(집계가 아닌 개별 권 카드)이면 허용하고,
  // 다중 선택은 선택된 전부가 개별 권일 때만 허용해 한 번에 일괄 정렬할 수 있게 한다.
  const targetBookCount = Number(target?.bookCount) > 0 ? Number(target.bookCount) : 1;
  const multiAllSingleBooks = isMulti && selectedBooks.every(book => (Number(book.bookCount) || 1) <= 1);
  items['ctx-cover-align-book'] = {
    visible: !!target?.isVolumeDetail || (!isMulti && targetBookCount <= 1) || multiAllSingleBooks,
    labelText: multiAllSingleBooks ? `선택한 ${count}개 커버 정렬 (이중 스캔본용)` : '커버 정렬 (이중 스캔본용)',
  };

  // 다중 선택이거나 영상 강좌(완독 처리 인프라 없음)일 때는 항상 "읽지 않음" 액션만 노출.
  // 그 외 단일 대상은 현재 읽음 진행 여부(hasProgress)를 보고 "읽음/읽지 않음"을 토글.
  const isSeries = target?.markUnreadScope === 'series';
  if (!isMulti && !env.isVideoLibrary && target?.hasProgress === false) {
    items['ctx-unread-book'] = {
      action: 'mark-read', iconClass: 'fa-solid fa-eye', iconColor: '#22c55e',
      labelKey: isSeries ? 'context_menu.mark_series_as_read' : 'context_menu.mark_as_read',
      labelFallback: isSeries ? '이 시리즈 전체를 읽은 상태로 변경 (완독)' : '읽은 상태로 변경 (완독)',
    };
  } else {
    items['ctx-unread-book'] = isMulti
      ? { action: 'mark-unread', iconClass: 'fa-solid fa-eye-slash', iconColor: '#ef4444',
          labelText: `선택한 ${count}개 작품을 읽지 않은 상태로 변경 (0%)` }
      : { action: 'mark-unread', iconClass: 'fa-solid fa-eye-slash', iconColor: '#ef4444',
          labelKey: isSeries ? 'context_menu.mark_series_as_unread' : 'context_menu.mark_as_unread',
          labelFallback: isSeries ? '이 시리즈 전체를 읽지 않은 상태로 변경 (0%)' : '읽지 않은 상태로 변경 (0%)' };
  }

  // 메타정보 검색: 활성 검색 플러그인이 있을 때만. 아직 모르면(null) 건드리지 않는다(비동기로 채움).
  items['ctx-search-meta-book'] = {
    visible: env.metaSearchAvailable == null ? undefined : !!env.metaSearchAvailable,
  };

  return { title: isMulti ? `도서 메뉴 (${count}개 선택)` : '도서 메뉴', items };
}
