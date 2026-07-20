# Contributing

Keep contributions small, testable and provider-neutral.

1. Open an issue for behavior changes or security concerns.
2. Create a branch from `main`, make the smallest coherent change, and add tests.
3. Run `npm test`, `npm run config:validate`, and `node --check src/index.js`.
4. Explain Feishu API assumptions, compatibility impact and rollback steps in the pull request.

Use Node built-ins where practical. Keep secrets out of fixtures and logs; use `ou_example` and `oc_example` placeholders. Preserve explicit task transitions and do not make model prose authoritative for dispatch. Report vulnerabilities privately rather than publishing credentials or exploit details.
