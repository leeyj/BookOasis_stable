import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/favorite_toggle.js', import.meta.url), 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const {
  readNextFavoriteStatus,
  applyFavoriteState,
  snapshotFavoriteState,
  restoreFavoriteState,
  isFavoritePending,
  setFavoritePending,
} = await import(moduleUrl);

// 즐겨찾기 별 버튼(<button class="btn-card-fav-toggle"><i></i></button>)의 최소 스텁
function createButton({ active = false } = {}) {
  const classes = new Set(['btn-card-fav-toggle']);
  if (active) classes.add('active');
  const attributes = new Map([['data-next-status', active ? '0' : '1']]);
  const icon = { className: active ? 'fa-solid fa-star' : 'fa-regular fa-star' };
  return {
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name),
    },
    getAttribute: (name) => (attributes.has(name) ? attributes.get(name) : null),
    setAttribute: (name, value) => attributes.set(name, String(value)),
    removeAttribute: (name) => attributes.delete(name),
    querySelector: (selector) => (selector === 'i' ? icon : null),
    dataset: {},
    icon,
  };
}

test('consecutive clicks alternate between favoriting and unfavoriting', () => {
  const button = createButton({ active: false });

  const first = readNextFavoriteStatus(button);
  applyFavoriteState(button, first === 1); // 첫 클릭 성공(낙관적 적용 유지)
  const second = readNextFavoriteStatus(button);
  applyFavoriteState(button, second === 1);
  const third = readNextFavoriteStatus(button);

  assert.deepEqual([first, second, third], [1, 0, 1]);
});

test('applying a state keeps the class, icon and data attributes consistent', () => {
  const button = createButton({ active: false });

  applyFavoriteState(button, true);

  assert.equal(button.classList.contains('active'), true);
  assert.equal(button.icon.className, 'fa-solid fa-star');
  assert.equal(button.getAttribute('data-next-status'), '0');
  assert.equal(button.getAttribute('aria-pressed'), 'true');

  applyFavoriteState(button, false);

  assert.equal(button.classList.contains('active'), false);
  assert.equal(button.icon.className, 'fa-regular fa-star');
  assert.equal(button.getAttribute('data-next-status'), '1');
  assert.equal(button.getAttribute('aria-pressed'), 'false');
});

test('a failed request restores every part of the button, including attributes that did not exist', () => {
  const button = createButton({ active: false });
  const snapshot = snapshotFavoriteState(button);

  applyFavoriteState(button, true); // 낙관적 적용 후 요청 실패
  restoreFavoriteState(button, snapshot);

  assert.equal(button.classList.contains('active'), false);
  assert.equal(button.icon.className, 'fa-regular fa-star');
  assert.equal(button.getAttribute('data-next-status'), '1');
  assert.equal(button.getAttribute('aria-pressed'), null); // 원래 없던 속성은 다시 제거된다
});

test('restoring an active button after a failed unfavorite keeps it active', () => {
  const button = createButton({ active: true });
  const snapshot = snapshotFavoriteState(button);

  applyFavoriteState(button, false);
  restoreFavoriteState(button, snapshot);

  assert.equal(button.classList.contains('active'), true);
  assert.equal(button.icon.className, 'fa-solid fa-star');
  assert.equal(button.getAttribute('data-next-status'), '0');
});

test('the pending flag blocks a second click until the request finishes', () => {
  const button = createButton();

  assert.equal(isFavoritePending(button), false);
  setFavoritePending(button, true);
  assert.equal(isFavoritePending(button), true);
  setFavoritePending(button, false);
  assert.equal(isFavoritePending(button), false);
});

test('a missing button is handled without throwing', () => {
  assert.equal(readNextFavoriteStatus(null), 1);
  assert.doesNotThrow(() => applyFavoriteState(null, true));
  assert.doesNotThrow(() => restoreFavoriteState(null, null));
  assert.equal(isFavoritePending(null), false);
});
