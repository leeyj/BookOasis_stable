// annotation_state.js — 현재 열린 책의 하이라이트(주석) 목록을 메모리에 캐싱하는
// 단일 소스. 뷰어가 열릴 때 1회 로드하고, 생성/삭제 시 로컬 캐시도 함께 갱신해서
// 매번 서버에 재조회하지 않는다.
let currentBookId = null;
let currentDbType = null;
let annotations = [];
let loadPromise = null;

export function loadAnnotationsForBook(bookId, dbType) {
  if (!bookId) {
    annotations = [];
    return Promise.resolve(annotations);
  }
  if (currentBookId === bookId && currentDbType === dbType && loadPromise) {
    return loadPromise;
  }
  currentBookId = bookId;
  currentDbType = dbType;

  loadPromise = fetch(`/api/v1/books/${bookId}/annotations?db_type=${dbType}`)
    .then((res) => res.json())
    .then((data) => {
      annotations = (data && data.success && Array.isArray(data.annotations)) ? data.annotations : [];
      return annotations;
    })
    .catch(() => {
      annotations = [];
      return annotations;
    });
  return loadPromise;
}

export function getAnnotations() {
  return annotations;
}

export function getAnnotationsForChapter(chapterIdx) {
  return annotations.filter((a) => a.format === 'epub' && Number(a.chapter_idx) === Number(chapterIdx));
}

export function getTxtAnnotations() {
  return annotations.filter((a) => a.format === 'txt');
}

export function addAnnotationLocal(annotation) {
  annotations.push(annotation);
}

export function updateAnnotationLocal(annotationId, patch) {
  const target = annotations.find((a) => Number(a.id) === Number(annotationId));
  if (target) Object.assign(target, patch);
}

export function removeAnnotationLocal(annotationId) {
  annotations = annotations.filter((a) => Number(a.id) !== Number(annotationId));
}

export function getAnnotationById(annotationId) {
  return annotations.find((a) => Number(a.id) === Number(annotationId)) || null;
}

export function clearAnnotationState() {
  currentBookId = null;
  currentDbType = null;
  annotations = [];
  loadPromise = null;
}
