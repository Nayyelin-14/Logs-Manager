# Changelog

## [0.2.0](https://github.com/Nayyelin-14/Logs-Manager/compare/v0.1.0...v0.2.0) (2026-11-12)


### Features

* add new pages and components for dashboard, logs, rules, and users ([a3e98ca](https://github.com/Nayyelin-14/Logs-Manager/commit/a3e98caf02a45269a97d8700361b7eb635c814e3))
* add server-side source filter to dashboard and stats ([2800916](https://github.com/Nayyelin-14/Logs-Manager/commit/28009161bf262c2049c5facccf895ad0fb286a86))
* **backend:** FastAPI appliance - auth, multi-source ingestion, alerting, retention, syslog ([9a90a0a](https://github.com/Nayyelin-14/Logs-Manager/commit/9a90a0a14b456efd5ee42a58a993d542a99073d7))
* **email:** add Resend provider for alert delivery ([88ec88c](https://github.com/Nayyelin-14/Logs-Manager/commit/88ec88c8e51c09e8c5cedb0949f327d8a7563f27))
* **frontend:** React dashboard updates plus Docker and nginx packaging ([e7a9390](https://github.com/Nayyelin-14/Logs-Manager/commit/e7a9390f2751067b65a2b5e48284213479248733))
* implement high-fidelity dark UI designs across all pages ([edf39f8](https://github.com/Nayyelin-14/Logs-Manager/commit/edf39f849bd68ce6543265d1798f698ac782f2f9))
* **notifications:** reliable alert delivery and admin test endpoint ([0056fa5](https://github.com/Nayyelin-14/Logs-Manager/commit/0056fa59e0e0b763793b7cecc16651924cc05858))
* **retention:** add demo script and make target ([5bb0284](https://github.com/Nayyelin-14/Logs-Manager/commit/5bb0284470ee58cf89e2eb44839f4ae4333501ff))
* **syslog:** ingest syslog over HTTPS for SaaS deployments ([f9e525c](https://github.com/Nayyelin-14/Logs-Manager/commit/f9e525cde5a797565c5d4cae2b147b6de8c99fa7))


### Bug Fixes

* add uuid import and ID generation in create_alert_rule route in ingest.py. This fixes the NOT NULL constraint violation on alert_rules.id column ([1ed6376](https://github.com/Nayyelin-14/Logs-Manager/commit/1ed63762409daabb72fec0fed549b87c2c379da6))
* alerting dedupe race, worker crash, RBAC, webhook duplication, source enum ([349fe7a](https://github.com/Nayyelin-14/Logs-Manager/commit/349fe7a35501616c520852ec550a0649a3f5621d))
* alerting dedupe race, worker crash, RBAC, webhook duplication, source enum ([10689e4](https://github.com/Nayyelin-14/Logs-Manager/commit/10689e4e2e7c31a8eb03f26a567e9bbbb15a53bb))
* **alerting:** match event_type case- and underscore-insensitively ([3902f6f](https://github.com/Nayyelin-14/Logs-Manager/commit/3902f6fc1870931fe163dcd73098a568bf7b4229))
* align backend API contracts with the frontend ([b9e5c50](https://github.com/Nayyelin-14/Logs-Manager/commit/b9e5c50dba0bdd7e2ee2c6f4d6503dc31b2506b9))
* align frontend requests with backend API contracts ([61f2705](https://github.com/Nayyelin-14/Logs-Manager/commit/61f2705436fb4a8a9d9b9a1af22a211cbf4216f9))
* **auth:** add real login rate limiting and per-email lockout ([67666b5](https://github.com/Nayyelin-14/Logs-Manager/commit/67666b5f5d9e0d3b73619ec180ab963dd5089c03))
* **auth:** use Redis storage for login rate limiter ([119fabe](https://github.com/Nayyelin-14/Logs-Manager/commit/119fabe10f603ee9d35b72bb000de1747a17cf69))
* **ci:** run Vercel CLI from repo root ([a0ba9f3](https://github.com/Nayyelin-14/Logs-Manager/commit/a0ba9f36519e6719c18f143e6c84df584b58e0c7))
* classify verbatim router syslog as network, not firewall ([42c9290](https://github.com/Nayyelin-14/Logs-Manager/commit/42c929054aa643ba7f0da3ae8820c2a8b32988ec))
* coerce SYSLOG_SOURCE string default to Source enum in resolve_source ([093a975](https://github.com/Nayyelin-14/Logs-Manager/commit/093a975785526025dc48c1b08ee9ca704b71c3fe))
* **compose:** expose syslog on all interfaces with host port 514 ([1f273a2](https://github.com/Nayyelin-14/Logs-Manager/commit/1f273a2641df801fa2a3ae7719b4cb395938ee09))
* **dashboard:** scope tenant counts to the effective tenant ([74cbdbc](https://github.com/Nayyelin-14/Logs-Manager/commit/74cbdbcf373d21ef7570a119a345f575a1406ea9))
* **deploy:** default appliance HTTP port to 80 ([4cda536](https://github.com/Nayyelin-14/Logs-Manager/commit/4cda5362b07b9c69d4df74d7f7c46a71704b1686))
* **frontend:** drop invalid ignoreDeprecations setting ([3db1369](https://github.com/Nayyelin-14/Logs-Manager/commit/3db13698a9b3bb52d606eb5084b64e45b3346a77))
* **health:** report the deployed commit when GIT_SHA is the unknown placeholder ([af50fbe](https://github.com/Nayyelin-14/Logs-Manager/commit/af50fbe8350f9df8431719c11837282df69e2f8a))
* **ingest:** preserve supplied severity on JSON API events ([684efc0](https://github.com/Nayyelin-14/Logs-Manager/commit/684efc0b7795ee746e4663e75277f0bd444ed5c5))
* **ingest:** strict input validation on /ingest ([bec9224](https://github.com/Nayyelin-14/Logs-Manager/commit/bec922438d15a0c43989def5f37dd0cdf4728c03))
* keyset pagination and real search totals ([9f0ac8c](https://github.com/Nayyelin-14/Logs-Manager/commit/9f0ac8c1a606635676e0639a8d34bbd34ff4c9cd))
* **normalizer:** map crowdstrike quarantine action to alert enum ([ee70f54](https://github.com/Nayyelin-14/Logs-Manager/commit/ee70f54d7d7454b3749d516c7aa11e8d32d8f973))
* reject invalid [@timestamp](https://github.com/timestamp) per-row in file upload instead of silently using ingestion time ([acd1326](https://github.com/Nayyelin-14/Logs-Manager/commit/acd13260935315b7f96f70afb1f484466326137f))
* remove unreachable duplicate routes and add alert window test ([994fe70](https://github.com/Nayyelin-14/Logs-Manager/commit/994fe70fcc21c7dd1045b624afc7ec1d3a80cc67))
* **saas:** complete CSRF, ingestion, tenancy and demo seeding ([117b308](https://github.com/Nayyelin-14/Logs-Manager/commit/117b3085d6b05eed867f6e6b06340c5c6232c225))
* **saas:** complete CSRF, ingestion, tenancy and demo seeding ([4020e4f](https://github.com/Nayyelin-14/Logs-Manager/commit/4020e4f428f50ac7a98fb8f8d3bb016e00ee98f3))
* **samples:** document working file-upload route and fix syslog TCP hang ([9d6602b](https://github.com/Nayyelin-14/Logs-Manager/commit/9d6602b789ee196861d0e49f292db8a30dd91865))
* **security:** rate-limit ingestion and scope tenant admins ([bc915d9](https://github.com/Nayyelin-14/Logs-Manager/commit/bc915d943e3157809241c2f0acb8460cac853090))
* seed all seven sources and document dashboard source filter ([6222cc0](https://github.com/Nayyelin-14/Logs-Manager/commit/6222cc005b01fb5737c6236d27a9b737de72ab7d))
* show em dash instead of LOG for null action in logs table ([00cf1cf](https://github.com/Nayyelin-14/Logs-Manager/commit/00cf1cf5c07163e3887b1a1d41198c4361f81859))
* strict isolation tests pass against real DB ([19ee4b3](https://github.com/Nayyelin-14/Logs-Manager/commit/19ee4b305b878b6b9e6c4750a6a872bb22d36144))
* **test:** repair stale otp import and update crowdstrike action tests ([e74382f](https://github.com/Nayyelin-14/Logs-Manager/commit/e74382fa17b8502af8a15e22436b59626003ce88))
* **test:** replace placeholder assert True tests with real API tests ([994aba2](https://github.com/Nayyelin-14/Logs-Manager/commit/994aba205c81ad1d945839301b71e8baa7ec40b6))
* **test:** reset rate limiter between tests ([194abe6](https://github.com/Nayyelin-14/Logs-Manager/commit/194abe6d808e4679587aaf617980048c11d30c71))
