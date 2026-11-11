import assert from "node:assert/strict";
import test from "node:test";

import { resolveApiBase } from "../src/lib/apiBase.ts";

test("relative /api is kept", () => {
  assert.equal(resolveApiBase("/api", "logs-manager.vercel.app"), "/api");
});

test("a production Render origin is kept", () => {
  assert.equal(
    resolveApiBase("https://nayyelin-logs-api.onrender.com/api", "logs-manager.vercel.app"),
    "https://nayyelin-logs-api.onrender.com/api"
  );
});

test("the [SENSITIVE] placeholder falls back to /api", () => {
  assert.equal(resolveApiBase("[SENSITIVE]", "logs-manager.vercel.app"), "/api");
});

test("an empty value falls back to /api", () => {
  assert.equal(resolveApiBase("", "logs-manager.vercel.app"), "/api");
  assert.equal(resolveApiBase(undefined, "logs-manager.vercel.app"), "/api");
});

test("a malformed URL falls back to /api", () => {
  assert.equal(resolveApiBase("not a url", "logs-manager.vercel.app"), "/api");
});

test("localhost API is rejected in a production browser", () => {
  assert.equal(
    resolveApiBase("http://localhost:4500/api", "logs-manager.vercel.app"),
    "/api"
  );
  assert.equal(
    resolveApiBase("http://127.0.0.1:4500/api", "logs-manager.vercel.app"),
    "/api"
  );
});

test("localhost API is kept when the app runs locally", () => {
  assert.equal(
    resolveApiBase("http://localhost:4500/api", "localhost"),
    "http://localhost:4500/api"
  );
});
