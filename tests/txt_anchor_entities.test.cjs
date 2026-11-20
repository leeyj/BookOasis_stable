const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const repoRoot = path.resolve(__dirname, '..');
const anchorSourcePath = process.env.TXT_ANCHOR_SOURCE
  || path.join(repoRoot, 'static/js/viewer/txt_anchor_utils.js');
const textUtilsSourcePath = process.env.TXT_TEXT_UTILS_SOURCE
  || path.join(repoRoot, 'static/js/viewer/txt_text_utils.js');
const sandbox = { NodeFilter: { SHOW_TEXT: 4 } };

// The native browser decoder is exercised by the isolated Chrome fixture as well. This small
// DOM stand-in keeps the anchor contract tests dependency-free under node --test.
const namedEntities = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00a0',
  eacute: 'é', mdash: '—',
};
function decodeEntitiesForFixture(text) {
  return String(text).replace(/&(#(?:x[\da-f]+|\d+)|[a-z][\da-z]+);/gi, (whole, entity) => {
    if (entity[0] !== '#') return namedEntities[entity] ?? whole;
    const isHex = /^#x/i.test(entity);
    const codePoint = Number.parseInt(entity.slice(isHex ? 2 : 1), isHex ? 16 : 10);
    if (!Number.isInteger(codePoint) || codePoint < 0 || codePoint > 0x10ffff) return '\ufffd';
    try { return String.fromCodePoint(codePoint); } catch { return '\ufffd'; }
  });
}

vm.runInNewContext(fs.readFileSync(textUtilsSourcePath, 'utf8').replace(/^export\s+/gm, ''), sandbox, {
  filename: textUtilsSourcePath,
});
vm.runInNewContext(
  `globalThis.textApi = { stripHtml, stripHtmlForAnchor: typeof stripHtmlForAnchor === 'function' ? stripHtmlForAnchor : stripHtml };`,
  sandbox,
  { filename: textUtilsSourcePath },
);
vm.runInNewContext(
  `${fs.readFileSync(anchorSourcePath, 'utf8').replace(/^export\s+/gm, '')}\nglobalThis.anchorApi = { getTxtAnchorInfoByMode, restoreTxtAnchorInfoByMode, captureTxtPageAnchor };`,
  sandbox,
  { filename: anchorSourcePath },
);

function makeFixture(visibleText, { visibleOffset = 0, includeBlocks = true } = {}) {
  const textNode = { nodeValue: visibleText };
  const block = {
    textContent: visibleText,
    children: [],
    tagName: 'P',
    querySelector: () => null,
    getClientRects: () => [{ left: 0, right: 200, width: 200 }],
  };
  const contentArea = {
    querySelectorAll: () => includeBlocks ? [block] : [],
    querySelector: () => null,
  };
  const scrollWrapper = {
    scrollTop: 0,
    scrollLeft: 0,
    scrollHeight: 100,
    clientHeight: 100,
    scrollWidth: 200,
    clientWidth: 100,
    getBoundingClientRect: () => ({ left: 0, right: 100, width: 100, height: 100 }),
  };
  sandbox.document = {
    createElement: () => ({
      set innerHTML(value) { this.value = decodeEntitiesForFixture(String(value)); },
      value: '',
    }),
    createTreeWalker: () => {
      let visited = false;
      return { nextNode: () => (visited ? null : (visited = true, textNode)) };
    },
    createRange: () => {
      let startOffset = 0;
      return {
        setStart: (_node, offset) => { startOffset = offset; },
        setEnd: () => {},
        getClientRects: () => [startOffset >= visibleOffset
          ? { left: 1, right: 2, width: 1 }
          : { left: 0, right: 1, width: 1 }],
      };
    },
  };
  return { block, contentArea, scrollWrapper };
}

function getAnchor({ rawHtml, visibleText, mode = 'scroll', scrollTop = 0, includeBlocks = true }) {
  const fixture = makeFixture(visibleText, { includeBlocks });
  fixture.scrollWrapper.scrollTop = scrollTop;
  fixture.scrollWrapper.scrollHeight = scrollTop ? 200 : 100;
  const result = sandbox.anchorApi.getTxtAnchorInfoByMode({
    ...fixture,
    forcedMode: mode,
    storage: { getItem: () => null },
    isEpub: true,
    fullText: rawHtml,
    txtChunks: [rawHtml],
    currentChunkIdx: 0,
    stripHtml: sandbox.stripHtml,
    stripHtmlForAnchor: sandbox.stripHtmlForAnchor,
  });
  return { ...fixture, result };
}

// Exported functions in scripts run in a VM become globals, not sandbox object properties.
// Capture the actual functions after evaluation for the fixtures and injected callbacks.
sandbox.stripHtml = vm.runInNewContext('stripHtml', sandbox);
sandbox.stripHtmlForAnchor = vm.runInNewContext(
  "typeof stripHtmlForAnchor === 'function' ? stripHtmlForAnchor : stripHtml",
  sandbox,
);

test('EPUB scroll anchor uses visible decoded text rather than HTML entity spellings', () => {
  const rawHtml = '<p>Unique A&amp;B blue mountains and amber rivers cross the plain.</p>';
  const visibleText = 'Unique A&B blue mountains and amber rivers cross the plain.';
  const { result } = getAnchor({ rawHtml, visibleText });
  assert.ok(result);
  assert.ok(visibleText.includes(result.anchorText), `anchor not visible: ${result.anchorText}`);
  assert.equal(result.anchorText, visibleText.slice(0, 30).trim());
});

test('EPUB anchor decodes named, numeric, astral and nonbreaking-space entities once', () => {
  const rawHtml = '<p>&eacute;lan &#x1F642; &#160;start &lt;quoted&gt; &quot;literal &amp;amp; entity&quot; and enough words after.</p>';
  const visibleText = 'élan 🙂 start <quoted> "literal &amp; entity" and enough words after.';
  const decoded = sandbox.stripHtmlForAnchor(rawHtml);
  assert.equal(decoded, visibleText);
  assert.ok(decoded.includes('&amp;'), 'double-escaped visible text must be decoded only once');
  const { result } = getAnchor({ rawHtml, visibleText });
  assert.ok(result);
  assert.ok(visibleText.includes(result.anchorText), `anchor not visible: ${result.anchorText}`);
  assert.ok(result.anchorText.startsWith('élan 🙂'));
  assert.ok(!result.anchorText.includes('&eacute;'));
  assert.ok(result.anchorText.length <= 30);
  assert.equal(result.anchorText.isWellFormed(), true);
});

test('EPUB anchor near the end retains decoded astral entities without splitting UTF-16 pairs', () => {
  const rawHtml = '<p>Beginning has enough ordinary words before a final destination and &#x1F680;.</p>';
  const visibleText = 'Beginning has enough ordinary words before a final destination and 🚀.';
  const { result } = getAnchor({ rawHtml, visibleText, scrollTop: 100 });
  assert.ok(result);
  assert.ok(visibleText.includes(result.anchorText), `anchor not visible: ${result.anchorText}`);
  assert.ok(result.anchorText.endsWith('🚀.'));
  assert.ok(result.anchorText.length <= 30);
  assert.equal(result.anchorText.isWellFormed(), true);
});

test('EPUB page-ratio fallback uses decoded visible text when DOM capture has no blocks', () => {
  const rawHtml = '<p>Unique A&amp;B blue mountains and amber rivers cross the plain.</p>';
  const visibleText = 'Unique A&B blue mountains and amber rivers cross the plain.';
  const { result } = getAnchor({ rawHtml, visibleText, mode: 'page', includeBlocks: false });
  assert.ok(result);
  assert.equal(result.anchorText, visibleText.slice(0, 30).trim());
});

test('EPUB scroll restore fallback locates the decoded anchor and updates scrollTop', () => {
  const rawHtml = '<p>Prefix words before Alpha &amp; Beta blue mountains continue through the valley and beyond.</p>';
  const visibleText = 'Prefix words before Alpha & Beta blue mountains continue through the valley and beyond.';
  const fixture = makeFixture(visibleText, { includeBlocks: false });
  fixture.scrollWrapper.scrollHeight = 500;
  fixture.scrollWrapper.clientHeight = 100;
  const restored = sandbox.anchorApi.restoreTxtAnchorInfoByMode({
    anchorInfo: { chunkIdx: 0, anchorText: 'Alpha & Beta blue mountains' },
    ...fixture,
    storage: { getItem: () => 'scroll' },
    currentChunkIdx: 0,
    isEpub: true,
    fullText: rawHtml,
    txtChunks: [rawHtml],
    stripHtml: sandbox.stripHtml,
    stripHtmlForAnchor: sandbox.stripHtmlForAnchor,
  });
  assert.equal(restored, true);
  assert.ok(fixture.scrollWrapper.scrollTop > 0);
});

test('EPUB page restore fallback locates the decoded anchor and updates scrollLeft', () => {
  const rawHtml = '<p>Prefix words before Alpha &amp; Beta blue mountains continue through the valley and beyond.</p>';
  const visibleText = 'Prefix words before Alpha & Beta blue mountains continue through the valley and beyond.';
  const fixture = makeFixture(visibleText, { includeBlocks: false });
  fixture.scrollWrapper.scrollWidth = 500;
  fixture.scrollWrapper.clientWidth = 100;
  const restored = sandbox.anchorApi.restoreTxtAnchorInfoByMode({
    anchorInfo: { chunkIdx: 0, anchorText: 'Alpha & Beta blue mountains' },
    ...fixture,
    storage: { getItem: () => 'page' },
    currentChunkIdx: 0,
    getPageAdvanceWidth: () => 100,
    isEpub: true,
    fullText: rawHtml,
    txtChunks: [rawHtml],
    stripHtml: sandbox.stripHtml,
    stripHtmlForAnchor: sandbox.stripHtmlForAnchor,
  });
  assert.equal(restored, true);
  assert.ok(fixture.scrollWrapper.scrollLeft > 0);
});

test('EPUB anchor whitespace follows the same normalization as DOM restoration', () => {
  const rawHtml = '<p>&nbsp;Alpha&nbsp;&nbsp;&amp; Beta&#9;blue mountains and amber rivers.&#160;</p>';
  const visibleText = 'Alpha & Beta blue mountains and amber rivers.';
  const { result } = getAnchor({ rawHtml, visibleText });
  assert.equal(sandbox.stripHtmlForAnchor(rawHtml), visibleText);
  assert.ok(result);
  assert.equal(result.anchorText, visibleText.slice(0, 30));
});

test('TXT text containing the literal string &amp; is not decoded', () => {
  const text = 'Unique A&amp;B blue mountains and amber rivers cross the plain.';
  const fixture = makeFixture(text);
  const result = sandbox.anchorApi.getTxtAnchorInfoByMode({
    ...fixture,
    forcedMode: 'scroll',
    storage: { getItem: () => null },
    isEpub: false,
    fullText: text,
    txtChunks: [text],
    currentChunkIdx: 0,
    stripHtml: sandbox.stripHtml,
    stripHtmlForAnchor: sandbox.stripHtmlForAnchor,
  });
  assert.ok(result);
  assert.equal(result.anchorText, text.slice(0, 30).trim());
  assert.ok(result.anchorText.includes('&amp;'));
});
