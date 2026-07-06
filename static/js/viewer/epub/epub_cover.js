import { state } from '../../state.js';

export function getCoverFallbackFromState(bookId) {
  const idNum = Number(bookId || state.activeBookId);
  const pools = [
    Array.isArray(state.currentBooksData) ? state.currentBooksData : [],
    Array.isArray(state.allBooksData) ? state.allBooksData : []
  ];

  for (const pool of pools) {
    const found = pool.find(item => Number(item && item.id) === idNum);
    const cover = found && found.cover_image ? String(found.cover_image).trim() : '';
    if (cover) {
      return `/covers/${encodeURIComponent(cover)}`;
    }
  }

  return '';
}

export async function resolveActiveBookCoverFallbackUrl(bookId) {
  const fromState = getCoverFallbackFromState(bookId);
  if (fromState) {
    return fromState;
  }

  try {
    const dbType = encodeURIComponent(state.currentLibraryType || 'general');
    const id = encodeURIComponent(String(bookId || state.activeBookId || ''));
    if (!id) {
      return '/static/images/default_cover.jpg';
    }

    const res = await fetch(`/api/media/books/${id}/info?type=${dbType}`);
    if (res.ok) {
      const data = await res.json();
      const cover = data && data.cover_image ? String(data.cover_image).trim() : '';
      if (cover) {
        return `/covers/${encodeURIComponent(cover)}`;
      }
    }
  } catch (err) {
    console.warn('[Viewer-Epub-Cover] cover fallback api lookup failed:', err);
  }

  return '/static/images/default_cover.jpg';
}
