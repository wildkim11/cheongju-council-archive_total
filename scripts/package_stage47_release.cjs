'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { runInNewContext } = require('node:vm');

function attachmentSearch(rows) {
  const encoded = JSON.stringify(rows).replace(/</g, '\\u003c');
  return `<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>청주시의회 연구단체 첨부 검색</title>
<h1>연구단체 첨부 검색</h1>
<p>공식 원문 링크와 제목을 검색합니다.</p>
<label>제목·파일 형식·자료 ID <input type="search" id="query"></label>
<p id="count" aria-live="polite"></p><ul id="results"></ul>
<script type="application/json" id="rows">${encoded}</script>
<script>
const rows = JSON.parse(document.getElementById('rows').textContent);
const query = document.getElementById('query');
const results = document.getElementById('results');
function render() {
  const tokens = query.value.normalize('NFC').toLowerCase().trim().split(/\\s+/);
  const matches = rows.filter(row => {
    const searchable = [row.title, row.file_type, row.parent_id].join(' ').normalize('NFC').toLowerCase();
    return tokens.every(token => searchable.includes(token));
  });
  results.replaceChildren(...matches.map(row => {
    const item = document.createElement('li');
    const link = document.createElement('a');
    const url = new URL(row.official_url);
    if (url.protocol !== 'https:' || !['council.cheongju.go.kr', 'councilrec.cheongju.go.kr'].includes(url.hostname)) {
      throw Error('첨부 원문 주소 오류');
    }
    link.href = url.href;
    link.textContent = row.title || url.href;
    item.append(link, ' · ' + row.parent_id);
    return item;
  }));
  document.getElementById('count').textContent = matches.length + '건';
}
query.addEventListener('input', render);
render();
</script></html>\n`;
}

async function main() {
  const [htmlPath, candidatePath, outputPath] = process.argv.slice(2);
  if (!htmlPath || !candidatePath || !outputPath) {
    throw Error('Usage: node package_stage47_release.cjs MASTER.html CANDIDATE.json NEW_OUTPUT_DIR');
  }
  const html = fs.readFileSync(htmlPath, 'utf8');
  const runtime = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
    .map(match => match[1]).find(code => code.includes('root.CouncilRelease=api'));
  const embedded = html.match(/<script id="release-bundle" type="application\/json">([\s\S]*?)<\/script>/);
  if (!runtime || !embedded) throw Error('Stage47 release runtime or baseline missing');

  const scope = { TextDecoder, crypto: require('node:crypto').webcrypto };
  runInNewContext(runtime, scope);
  const { accept, validate } = scope.CouncilRelease;
  const baseline = validate(JSON.parse(embedded[1]));
  const candidate = validate(JSON.parse(fs.readFileSync(candidatePath, 'utf8')));
  if (baseline.audience.kind !== 'master') throw Error('Expected a master baseline');

  function serialize(bundle) {
    return Buffer.from(JSON.stringify(bundle) + '\n', 'utf8');
  }

  function manifest(bundle, bytes) {
    return {
      schema: 'cheongju-offline-release/1',
      sequence: bundle.sequence,
      release_id: bundle.release_id,
      payload_file: 'council_bundle.json',
      bytes: bytes.length,
      sha256: createHash('sha256').update(bytes).digest('hex'),
    };
  }

  // The shared browser payload can be sliced into a member edition.
  // Keep master-wide source inventories in separate distribution files.
  const inventory = candidate.source.incremental_inventory;
  delete candidate.source.incremental_inventory;
  candidate.update_manifest_url = null;
  candidate.production_approved = false;
  const input = serialize(candidate);
  const bundle = await accept(manifest(candidate, input), input, baseline);
  const payload = serialize(bundle);
  const metadata = manifest(bundle, payload);
  await accept(metadata, payload, baseline);

  const parent = path.dirname(path.resolve(outputPath));
  const temporary = fs.mkdtempSync(path.join(parent, '.stage47-'));
  try {
    fs.writeFileSync(path.join(temporary, metadata.payload_file), payload);
    fs.writeFileSync(path.join(temporary, 'manifest.json'), JSON.stringify(metadata, null, 2) + '\n');
    if (inventory) {
      fs.writeFileSync(path.join(temporary, 'source_inventory.json'), serialize({
        schema: 'cheongju-stage47-source-inventory/1',
        release_id: bundle.release_id,
        archive_commit: bundle.source.incremental_archive_commit,
        ...inventory,
      }));
      fs.writeFileSync(path.join(temporary, 'research_attachments.html'),
        attachmentSearch(inventory.research_attachments));
    }
    if (fs.existsSync(outputPath)) throw Error('Output directory already exists');
    fs.renameSync(temporary, outputPath);
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
  console.log(JSON.stringify(metadata));
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
