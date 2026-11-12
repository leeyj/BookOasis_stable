// table_view/columns.js – 관리자 테이블 뷰의 컬럼 정의와 요청 조립 (순수 함수, import 없음).
// 화면은 table_view/index.js가 그린다. import가 없어야 tests/test_table_view_columns.mjs가 node에서 그대로 불러 검증할 수 있다.
// 서버 쪽 짝: repositories/series_table_query.py (COLUMNS) - 편집/정렬/빈 값 필터 가능 여부를 같게 유지한다.

// type: cover | link | text | select | number | date | lock | longtext(아이콘 + 팝업 편집)
export const COLUMN_DEFS = [
  { key: 'cover',              labelKey: 'table_view.col_cover',        fallback: '표지',      type: 'cover',  sortable: false, missing: true,  editable: false, fixed: true },
  { key: 'series_name',        labelKey: 'table_view.col_series',       fallback: '시리즈',    type: 'link',   sortable: true,  missing: false, editable: false, fixed: true },
  { key: 'series_alias',       labelKey: 'table_view.col_alias',        fallback: '별칭',      type: 'text',   sortable: true,  missing: true,  editable: true },
  { key: 'author',             labelKey: 'table_view.col_author',       fallback: '작가',      type: 'text',   sortable: true,  missing: true,  editable: true,  defaultVisible: true },
  { key: 'publisher',          labelKey: 'table_view.col_publisher',    fallback: '출판사',    type: 'text',   sortable: true,  missing: true,  editable: true },
  { key: 'isbn',               labelKey: 'table_view.col_isbn',         fallback: 'ISBN',      type: 'text',   sortable: true,  missing: true,  editable: true },
  { key: 'genre',              labelKey: 'table_view.col_genre',        fallback: '장르',      type: 'text',   sortable: true,  missing: true,  editable: true,  defaultVisible: true },
  { key: 'tags',               labelKey: 'table_view.col_tags',         fallback: '태그',      type: 'text',   sortable: true,  missing: true,  editable: true,  defaultVisible: true },
  { key: 'books_lv',           labelKey: 'table_view.col_books_lv',     fallback: '등급',      type: 'select', sortable: true,  missing: true,  editable: true },
  { key: 'publication_status', labelKey: 'table_view.col_status',       fallback: '연재 상태', type: 'select', sortable: true,  missing: true,  editable: true,  defaultVisible: true },
  { key: 'summary',            labelKey: 'table_view.col_summary',      fallback: '설명',      type: 'longtext', sortable: false, missing: true, editable: true,  defaultVisible: true },
  { key: 'score',              labelKey: 'table_view.col_score',        fallback: '평점',      type: 'number', sortable: true,  missing: true,  editable: false },
  { key: 'book_count',         labelKey: 'table_view.col_count',        fallback: '권수',      type: 'number', sortable: true,  missing: false, editable: false, defaultVisible: true },
  { key: 'file_format',        labelKey: 'table_view.col_format',       fallback: '형식',      type: 'text',   sortable: true,  missing: false, editable: false },
  { key: 'latest_added',       labelKey: 'table_view.col_added',        fallback: '추가일',    type: 'date',   sortable: true,  missing: false, editable: false, defaultVisible: true },
  { key: 'metadata_locked',    labelKey: 'table_view.col_locked',       fallback: '잠금',      type: 'lock',   sortable: true,  missing: false, editable: false, defaultVisible: true },
];

export const DEFAULT_SORT = { key: 'series_name', dir: 'asc' };
export const VISIBLE_COLUMNS_STORAGE_KEY = 'series_table_visible_columns';

// 상세 화면 수정 폼(detail/header_view.js)의 등급 선택지와 같다. 값 '' = 지정 안 함
export const BOOKS_LV_OPTIONS = ['', 'everyone', '일반', 'ma15+', 'm', '15세', 'r18', 'adult only 18+', '18세'];
export const PUBLICATION_STATUS_OPTIONS = ['', '0', '1', '2'];

const COLUMN_BY_KEY = new Map(COLUMN_DEFS.map((col) => [col.key, col]));

export function getColumn(key) {
  return COLUMN_BY_KEY.get(key) || null;
}

export function defaultVisibleKeys() {
  return COLUMN_DEFS.filter((col) => col.fixed || col.defaultVisible).map((col) => col.key);
}

// 저장된 표시 컬럼(JSON 배열 문자열) → 정의 순서대로 정리한 키 목록. 고정 컬럼(표지·시리즈명)은 항상 포함.
export function normalizeVisibleKeys(stored) {
  let keys = null;
  try {
    const parsed = typeof stored === 'string' ? JSON.parse(stored) : stored;
    if (Array.isArray(parsed)) keys = parsed.map(String);
  } catch (e) {
    keys = null;
  }
  if (!keys) return defaultVisibleKeys();
  const picked = new Set(keys);
  return COLUMN_DEFS.filter((col) => col.fixed || picked.has(col.key)).map((col) => col.key);
}

export function toggleVisibleKey(visibleKeys, key) {
  const col = getColumn(key);
  if (!col || col.fixed) return normalizeVisibleKeys(visibleKeys);
  const picked = new Set(visibleKeys);
  if (picked.has(key)) picked.delete(key);
  else picked.add(key);
  return normalizeVisibleKeys([...picked]);
}

// 머리글을 눌렀을 때 다음 정렬: 다른 컬럼이면 오름차순부터, 같은 컬럼이면 방향만 뒤집는다.
export function nextSort(current, key) {
  const col = getColumn(key);
  if (!col || !col.sortable) return current || DEFAULT_SORT;
  if (current && current.key === key) {
    return { key, dir: current.dir === 'asc' ? 'desc' : 'asc' };
  }
  return { key, dir: 'asc' };
}

export function normalizeMissingKeys(keys) {
  const picked = new Set((keys || []).map(String));
  return COLUMN_DEFS.filter((col) => col.missing && picked.has(col.key)).map((col) => col.key);
}

function cleanTokens(values) {
  return (values || [])
    .map((value) => String(value || '').replace(/^[\s'"\[\],]+|[\s'"\[\],]+$/g, '').replace(/\s{2,}/g, ' ').trim())
    .filter(Boolean);
}

// 목록/내보내기 공용 쿼리스트링. page·limit·columns는 준 것만 붙는다.
export function buildQuery({ type, libraryId, sort, missing, search, genres, tags, filterMode, page, limit, columns } = {}) {
  const params = new URLSearchParams();
  params.set('type', type || 'general');
  params.set('library_id', String(libraryId ?? 'all'));
  const safeSort = sort && getColumn(sort.key)?.sortable ? sort : DEFAULT_SORT;
  params.set('sort', safeSort.key);
  params.set('dir', safeSort.dir === 'desc' ? 'desc' : 'asc');
  const missingKeys = normalizeMissingKeys(missing);
  if (missingKeys.length) params.set('missing', missingKeys.join(','));
  const term = String(search || '').trim();
  if (term) params.set('search', term);
  const genreTokens = cleanTokens(genres);
  const tagTokens = cleanTokens(tags);
  if (genreTokens.length) params.set('genres', genreTokens.join(','));
  if (tagTokens.length) params.set('tags', tagTokens.join(','));
  if (filterMode === 'or' && genreTokens.length + tagTokens.length > 1) params.set('filter_mode', 'or');
  if (page) params.set('page', String(page));
  if (limit) params.set('limit', String(limit));
  if (Array.isArray(columns) && columns.length) {
    params.set('columns', columns.filter((key) => key !== 'cover').join(','));
  }
  return params.toString();
}

// 테이블 뷰를 쓸 수 있는 곳: 관리자 + 도서(일반/성인) + 실제 카테고리 또는 전체보기 + 넓은 화면
export function canUseTableView({ role, type, libraryId, wide = true } = {}) {
  if (String(role || '').trim().toLowerCase() !== 'admin') return false;
  if (!['general', 'adult'].includes(String(type || '').toLowerCase())) return false;
  if (!wide) return false;
  const id = String(libraryId ?? '');
  return id === 'all' || /^\d+$/.test(id);
}

export function formatCellText(col, row) {
  const value = row ? row[col.key] : '';
  if (col.type === 'date') return String(value || '').slice(0, 10);
  if (value === null || value === undefined) return '';
  return String(value);
}
