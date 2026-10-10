// 브라우저 ES 모듈은 URL이 다르면 별개 모듈로 평가된다. 템플릿이 진입 모듈을 static_asset_url()로
// '?v=…&asset=…'를 붙여 로드하는데 다른 모듈이 같은 파일을 쿼리 없이 import하면 인스턴스가 둘이 되어
// 부팅이 두 번 돌았다(2.8.9: tab_media_library.js, settings/queue.js, settings/mcp_pending.js).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const STATIC_JS = path.join(ROOT, 'static', 'js');

async function listFiles(dir, ext) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await listFiles(full, ext));
    else if (entry.name.endsWith(ext)) out.push(full);
  }
  return out;
}

function toStaticRel(absPath) {
  return path.relative(path.join(ROOT, 'static'), absPath).split(path.sep).join('/');
}

// 템플릿에서 static_asset_url()(쿼리가 붙는 헬퍼)로 로드하는 모듈 진입점: 'js/xxx.js'
async function versionedModuleEntries() {
  const entries = new Map();
  for (const file of await listFiles(path.join(ROOT, 'templates'), '.html')) {
    const html = await readFile(file, 'utf8');
    const re = /<script[^>]*type="module"[^>]*src="\{\{\s*static_asset_url\('([^']+)'\)\s*\}\}"/g;
    for (const m of html.matchAll(re)) entries.set(m[1], path.relative(ROOT, file));
  }
  return entries;
}

// static/js 안의 모든 import 지정자 → { importer, target('js/…'), query }
async function moduleImports() {
  const result = [];
  const re = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)['"](\.{1,2}\/[^'"]+)['"]/g;
  for (const file of await listFiles(STATIC_JS, '.js')) {
    if (file.includes(`${path.sep}lib${path.sep}`)) continue;
    const src = await readFile(file, 'utf8');
    for (const m of src.matchAll(re)) {
      const [spec, query = ''] = m[1].split('?');
      const target = toStaticRel(path.resolve(path.dirname(file), spec));
      result.push({ importer: toStaticRel(file), target, query });
    }
  }
  return result;
}

test('static_asset_url(?v=)로 로드하는 모듈 진입점은 다른 모듈이 import하지 않는다', async () => {
  const entries = await versionedModuleEntries();
  const offenders = (await moduleImports())
    .filter(({ target }) => entries.has(target))
    .map(({ importer, target }) => `${importer} → ${target} (템플릿: ${entries.get(target)})`);
  assert.deepEqual(offenders, [], `쿼리 붙은 진입점을 import하면 모듈이 두 번 평가됩니다:\n${offenders.join('\n')}`);
});

test('같은 모듈을 서로 다른 쿼리로 import하지 않는다', async () => {
  const queriesByTarget = new Map();
  for (const { importer, target, query } of await moduleImports()) {
    if (!queriesByTarget.has(target)) queriesByTarget.set(target, new Map());
    const byQuery = queriesByTarget.get(target);
    if (!byQuery.has(query)) byQuery.set(query, importer);
  }
  const offenders = [];
  for (const [target, byQuery] of queriesByTarget) {
    if (byQuery.size > 1) {
      offenders.push(`${target}: ${[...byQuery].map(([q, importer]) => `'${q || '(쿼리 없음)'}' ← ${importer}`).join(', ')}`);
    }
  }
  assert.deepEqual(offenders, [], `같은 파일을 다른 URL로 import하면 인스턴스가 나뉩니다:\n${offenders.join('\n')}`);
});
