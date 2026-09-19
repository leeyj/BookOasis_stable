// search_navigation.js – 검색어를 입력했을 때 화면을 이동해야 하는지, 어디로 이동할지 판단하는 순수 함수
//
// 홈/최근 읽은 도서에서 검색하면 전체보기로 이동한다(기존 동작). 시리즈 상세 화면이 열려 있을 때도
// 상단 검색창이 보이지만, 예전에는 상세 뒤에 가려진 그리드만 다시 불러와서 검색해도 아무 일도 없는
// 것처럼 보였다. 상세가 열려 있으면 검색 결과 화면으로 이동하되, 히스토리에 상세를 남겨(searchNavigation)
// 브라우저 뒤로가기로 원래 상세로 돌아오게 한다.
const NON_LIST_LIBRARIES = ['home', 'history'];

/**
 * @returns {null | {categoryId: string, options: object}}  null이면 이동 없이 현재 목록을 제자리 필터링한다.
 */
export function resolveSearchNavigation({ query, rawQuery, libraryId, detailVisible }) {
  if (!String(query || '').trim()) return null;
  const currentId = String(libraryId ?? '');
  const isNonListLibrary = NON_LIST_LIBRARIES.includes(currentId);

  if (detailVisible) {
    return {
      // 홈/기록에서 연 상세는 돌아갈 "목록"이 없으므로 전체보기로, 그 외에는 보던 라이브러리 안에서 검색한다.
      categoryId: isNonListLibrary ? 'all' : currentId,
      options: { preserveSearch: true, searchNavigation: true, searchQuery: rawQuery },
    };
  }
  if (isNonListLibrary) {
    return {
      categoryId: 'all',
      options: { preserveSearch: true, searchNavigationFrom: currentId, searchQuery: rawQuery },
    };
  }
  return null;
}
