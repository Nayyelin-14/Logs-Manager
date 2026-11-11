#!/usr/bin/env node
/**
 * Post-build guard for the deployed API base.
 *
 * A production bundle once shipped the literal placeholder `[SENSITIVE]` as
 * its axios baseURL, so every request hit the Vercel SPA route and returned
 * HTML. This script fails the build when a known-bad value is embedded.
 */
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const DIST = path.resolve(process.cwd(), "dist");
const FORBIDDEN = [
  /\[SENSITIVE\]/i,
  /"baseURL"\s*:\s*"local\.placeholder"/i,
];

const REQUIRED_FALLBACK = "/api";

async function listJsFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listJsFiles(full)));
    } else if (entry.name.endsWith(".js")) {
      files.push(full);
    }
  }
  return files;
}

const files = await listJsFiles(DIST);
if (files.length === 0) {
  console.error("FAIL: dist contains no JavaScript bundles. Run `vite build` first.");
  process.exit(1);
}

const offenders = [];
for (const file of files) {
  const text = await readFile(file, "utf8");
  for (const pattern of FORBIDDEN) {
    if (pattern.test(text)) {
      offenders.push(`${path.relative(DIST, file)} matches ${pattern}`);
    }
  }
}

if (offenders.length > 0) {
  console.error("FAIL: generated bundle contains an invalid API base URL:");
  for (const offender of offenders) console.error(`  - ${offender}`);
  process.exit(1);
}

const hasFallback = (
  await Promise.all(files.map((file) => readFile(file, "utf8")))
).some((text) => text.includes(REQUIRED_FALLBACK));
if (!hasFallback) {
  console.error("FAIL: generated bundle does not contain the /api fallback.");
  process.exit(1);
}

console.log(`OK: checked ${files.length} bundle files; API base has no placeholders.`);
