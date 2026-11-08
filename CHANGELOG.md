# Changelog

## [0.2.0](https://github.com/Nayyelin-14/Logs-Manager/compare/v0.1.0...v0.2.0) (2026-11-08)


### Features

* add new pages and components for dashboard, logs, rules, and users ([a3e98ca](https://github.com/Nayyelin-14/Logs-Manager/commit/a3e98caf02a45269a97d8700361b7eb635c814e3))
* **backend:** FastAPI appliance - auth, multi-source ingestion, alerting, retention, syslog ([9a90a0a](https://github.com/Nayyelin-14/Logs-Manager/commit/9a90a0a14b456efd5ee42a58a993d542a99073d7))
* **frontend:** React dashboard updates plus Docker and nginx packaging ([e7a9390](https://github.com/Nayyelin-14/Logs-Manager/commit/e7a9390f2751067b65a2b5e48284213479248733))
* implement high-fidelity dark UI designs across all pages ([edf39f8](https://github.com/Nayyelin-14/Logs-Manager/commit/edf39f849bd68ce6543265d1798f698ac782f2f9))
* **retention:** add demo script and make target ([5bb0284](https://github.com/Nayyelin-14/Logs-Manager/commit/5bb0284470ee58cf89e2eb44839f4ae4333501ff))


### Bug Fixes

* add uuid import and ID generation in create_alert_rule route in ingest.py. This fixes the NOT NULL constraint violation on alert_rules.id column ([1ed6376](https://github.com/Nayyelin-14/Logs-Manager/commit/1ed63762409daabb72fec0fed549b87c2c379da6))
* alerting dedupe race, worker crash, RBAC, webhook duplication, source enum ([349fe7a](https://github.com/Nayyelin-14/Logs-Manager/commit/349fe7a35501616c520852ec550a0649a3f5621d))
* alerting dedupe race, worker crash, RBAC, webhook duplication, source enum ([10689e4](https://github.com/Nayyelin-14/Logs-Manager/commit/10689e4e2e7c31a8eb03f26a567e9bbbb15a53bb))
* **auth:** add real login rate limiting and per-email lockout ([67666b5](https://github.com/Nayyelin-14/Logs-Manager/commit/67666b5f5d9e0d3b73619ec180ab963dd5089c03))
* **auth:** use Redis storage for login rate limiter ([119fabe](https://github.com/Nayyelin-14/Logs-Manager/commit/119fabe10f603ee9d35b72bb000de1747a17cf69))
* **ci:** run Vercel CLI from repo root ([a0ba9f3](https://github.com/Nayyelin-14/Logs-Manager/commit/a0ba9f36519e6719c18f143e6c84df584b58e0c7))
* **deploy:** default appliance HTTP port to 80 ([4cda536](https://github.com/Nayyelin-14/Logs-Manager/commit/4cda5362b07b9c69d4df74d7f7c46a71704b1686))
* **health:** report the deployed commit when GIT_SHA is the unknown placeholder ([af50fbe](https://github.com/Nayyelin-14/Logs-Manager/commit/af50fbe8350f9df8431719c11837282df69e2f8a))
* **ingest:** strict input validation on /ingest ([bec9224](https://github.com/Nayyelin-14/Logs-Manager/commit/bec922438d15a0c43989def5f37dd0cdf4728c03))
* **normalizer:** map crowdstrike quarantine action to alert enum ([ee70f54](https://github.com/Nayyelin-14/Logs-Manager/commit/ee70f54d7d7454b3749d516c7aa11e8d32d8f973))
* strict isolation tests pass against real DB ([19ee4b3](https://github.com/Nayyelin-14/Logs-Manager/commit/19ee4b305b878b6b9e6c4750a6a872bb22d36144))
* **test:** repair stale otp import and update crowdstrike action tests ([e74382f](https://github.com/Nayyelin-14/Logs-Manager/commit/e74382fa17b8502af8a15e22436b59626003ce88))
* **test:** replace placeholder assert True tests with real API tests ([994aba2](https://github.com/Nayyelin-14/Logs-Manager/commit/994aba205c81ad1d945839301b71e8baa7ec40b6))
* **test:** reset rate limiter between tests ([194abe6](https://github.com/Nayyelin-14/Logs-Manager/commit/194abe6d808e4679587aaf617980048c11d30c71))
