'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { runInNewContext } = require('node:vm');

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
