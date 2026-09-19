import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/sidebar_manager.js', import.meta.url), 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;

// 사이드바 DOM/뷰포트/프레임 스케줄러를 스텁해서 "메뉴 닫힘 → 한 프레임 양보 → 콜백" 순서를 검증한다.
function setupEnvironment({ mobile }) {
  const frames = [];
  const timers = [];
  const content = {
    hidden: false,
    dataset: { open: '1' },
    scrollTop: 0,
    classList: { remove() {}, add() {}, contains: () => true },
  };
  const btnIcon = { className: '' };
  const btn = { setAttribute() {}, querySelector: () => btnIcon };
  const elements = { 'sidebar-collapsible-content': content, 'btn-sidebar-toggle': btn };
  globalThis.document = {
    getElementById: (id) => elements[id] || null,
    querySelector: () => null,
  };
  globalThis.window = {
    matchMedia: () => ({ matches: mobile }),
    requestAnimationFrame: (callback) => frames.push(callback),
    setTimeout: (callback) => timers.push(callback),
  };
  const flush = () => {
    frames.splice(0).forEach((callback) => callback());
    timers.splice(0).forEach((callback) => callback());
  };
  return { content, flush };
}

// 모듈 최상단이 window.toggleSidebarMenu 등을 대입하므로, 임포트 전에 빈 window를 둔다.
globalThis.window = {};
globalThis.document = {};
const { runAfterMobileSidebarClose } = await import(moduleUrl);

test('on mobile the menu closes first and the navigation runs after a yielded frame', () => {
  const { content, flush } = setupEnvironment({ mobile: true });
  const order = [];

  runAfterMobileSidebarClose(() => order.push(`navigate(menu hidden=${content.hidden})`));

  assert.equal(content.hidden, true);
  assert.deepEqual(order, []);
  flush();
  assert.deepEqual(order, ['navigate(menu hidden=true)']);
});

test('on mobile only the most recent rapid tap navigates', () => {
  const { flush } = setupEnvironment({ mobile: true });
  const calls = [];

  runAfterMobileSidebarClose(() => calls.push('first'));
  runAfterMobileSidebarClose(() => calls.push('second'));
  flush();

  assert.deepEqual(calls, ['second']);
});

test('on desktop the navigation runs immediately without touching the menu', () => {
  const { content, flush } = setupEnvironment({ mobile: false });
  const calls = [];

  runAfterMobileSidebarClose(() => calls.push('navigate'));

  assert.deepEqual(calls, ['navigate']);
  assert.equal(content.hidden, false);
  flush();
  assert.deepEqual(calls, ['navigate']);
});

test('a non-function callback is ignored', () => {
  const { content, flush } = setupEnvironment({ mobile: true });

  assert.doesNotThrow(() => runAfterMobileSidebarClose(undefined));
  flush();
  assert.equal(content.hidden, false);
});
