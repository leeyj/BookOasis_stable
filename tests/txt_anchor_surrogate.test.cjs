const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const sourcePath = process.env.TXT_ANCHOR_SOURCE
  || path.resolve(__dirname, '../static/js/viewer/txt_anchor_utils.js');
const source = fs.readFileSync(sourcePath, 'utf8').replace(/^export\s+/gm, '');
const sandbox = { NodeFilter: { SHOW_TEXT: 4 } };
vm.runInNewContext(`${source}\nglobalThis.anchorApi = { getTxtAnchorInfoByMode, captureTxtPageAnchor, txtPageAnchorText };`, sandbox, {
  filename: sourcePath,
});

function makeFixture(text, visibleOffset = 0) {
  const textNode = { nodeValue: text };
  const block = {
    textContent: text,
    children: [],
    querySelector: () => null,
    getClientRects: () => [{ left: 0, right: 200, width: 200 }],
  };
  const contentArea = {
    querySelectorAll: () => [block],
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

function callAnchor({ text, format = 'txt', mode = 'page', visibleOffset = 0, scrollTop = 0 }) {
  const fixture = makeFixture(text, visibleOffset);
  if (scrollTop) {
    fixture.scrollWrapper.scrollTop = scrollTop;
    fixture.scrollWrapper.scrollHeight = 200;
  }
  const isEpub = format === 'epub';
  const rawChunk = isEpub ? `<p>${text}</p>` : text;
  const result = sandbox.anchorApi.getTxtAnchorInfoByMode({
    ...fixture,
    forcedMode: mode,
    storage: { getItem: () => null },
    isEpub,
    fullText: rawChunk,
    txtChunks: [rawChunk],
    currentChunkIdx: 0,
    stripHtml: (value) => String(value).replace(/<[^>]*>/g, ''),
  });
  return { ...fixture, result };
}

for (const format of ['txt', 'epub']) {
  test(`${format} page read anchor does not end with half an astral character`, () => {
    const text = `${'A'.repeat(29)}🙂${'B'.repeat(10)}`;
    const { result } = callAnchor({ text, format });
    assert.ok(result);
    assert.equal(result.anchorText, 'A'.repeat(29));
    assert.equal(result.anchorText.length, 29);
    assert.equal(result.anchorText.isWellFormed(), true);
  });

  test(`${format} page read anchor does not start inside an astral character or alter its UTF-16 offset`, () => {
    const text = `abc🙂${' hello'.repeat(8)}`;
    const fixture = makeFixture(text, 4); // UTF-16 offset 4 is the low surrogate of 🙂.
    const captured = sandbox.anchorApi.captureTxtPageAnchor({
      scrollWrapper: fixture.scrollWrapper,
      contentArea: fixture.contentArea,
      chunkIdx: 0,
    });
    assert.equal(captured.charOffset, 4);
    const anchorText = sandbox.anchorApi.txtPageAnchorText({ contentArea: fixture.contentArea, anchor: captured });
    assert.equal(anchorText, 'hello hello hello hello hello');
    assert.equal(captured.charOffset, 4);

    const { result } = callAnchor({ text, format, visibleOffset: 4 });
    assert.ok(result);
    assert.equal(result.anchorText, 'hello hello hello hello hello');
    assert.equal(result.anchorText.isWellFormed(), true);
    assert.equal(captured.charOffset, 4);
  });

  test(`${format} scroll read anchor does not start inside an astral character`, () => {
    const text = `abc🙂${' hello'.repeat(8)}`;
    const { result } = callAnchor({ text, format, mode: 'scroll', scrollTop: (4.5 / text.length) * 100 });
    assert.ok(result);
    assert.ok(result.anchorText.startsWith('hello'));
    assert.equal(result.anchorText.isWellFormed(), true);
    assert.ok(result.anchorText.length <= 30);
  });

  test(`${format} scroll read anchor keeps the 30 UTF-16-unit cap well-formed`, () => {
    const text = `${'A'.repeat(29)}🙂${'B'.repeat(10)}`;
    const { result } = callAnchor({ text, format, mode: 'scroll' });
    assert.ok(result);
    assert.equal(result.anchorText, 'A'.repeat(29));
    assert.equal(result.anchorText.length, 29);
    assert.equal(result.anchorText.isWellFormed(), true);
  });
}

test('ordinary English and Korean anchor text remains unchanged and capped at 30 UTF-16 units', () => {
  const text = 'English 한국어 문장 그대로 유지됩니다. More text for this anchor.';
  const { result } = callAnchor({ text });
  assert.ok(result);
  assert.equal(result.anchorText, text.slice(0, 30).trim());
  assert.equal(result.anchorText.length, 30);
  assert.equal(result.anchorText.isWellFormed(), true);
});
