import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { discoverCsv, resolveInputs, buildAuditArgs } from '../bin/infinity-ads-audit.js';

function fixture() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ads-audit-cli-'));
}

test('discovers one ADS SCRIPTS and one working CSV recursively', () => {
  const root = fixture();
  fs.mkdirSync(path.join(root, 'config'), { recursive: true });
  fs.writeFileSync(path.join(root, 'config', 'ADS SCRIPTS.csv'), 'Name,ID,Ads type\n');
  fs.writeFileSync(path.join(root, 'config', 'working file.csv'), 'Task Detail,Document\n');
  assert.match(discoverCsv(root, 'ads'), /ADS SCRIPTS\.csv$/);
  assert.match(discoverCsv(root, 'working'), /working file\.csv$/);
});

test('explicit paths take precedence over discovery', () => {
  const root = fixture();
  const ads = path.join(root, 'chosen.csv');
  const working = path.join(root, 'chosen-working.csv');
  fs.writeFileSync(ads, '');
  fs.writeFileSync(working, '');
  const resolved = resolveInputs(root, ads, working);
  assert.deepEqual(resolved, { adsScript: path.resolve(ads), workingFile: path.resolve(working) });
});

test('multiple candidates fail with the explicit flag name', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, 'ADS SCRIPTS.csv'), '');
  fs.writeFileSync(path.join(root, 'ADS SCRIPTS backup.csv'), '');
  assert.throws(() => discoverCsv(root, 'ads'), /--ads-script/);
});

test('builds Python arguments with resolved CSV paths', () => {
  const args = buildAuditArgs('.', '/tmp/ads.csv', '/tmp/working.csv', ['--no-webhook']);
  assert.deepEqual(args, ['scripts/run_audit.py', '--project', '.', '--ads-script', '/tmp/ads.csv', '--working-file', '/tmp/working.csv', '--no-webhook']);
});
