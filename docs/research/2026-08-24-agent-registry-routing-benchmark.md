# Agent Registry and Routing Benchmark

Research date: 2026-08-24  
Activity window: 2025-08-24 through 2026-08-24  
Target baseline: [`hermes-feishu-a2a` at `30f6945`](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/tree/30f6945f2f8717c6a939c05848ecb20a586cb14f)

## Executive summary

Hermes already has a useful small-system foundation: strict Pydantic Agent records, YAML preload, SQLite persistence, authenticated registration and heartbeats, bounded workflow execution, and a deterministic zero-credential demo. Its principal registry limitation is semantic rather than infrastructural: `POST /agents` is an implicit upsert, there is no complete runtime CRUD contract, and tasks still require a literal `agent_id` instead of a capability selector. Its CLI validates configuration and runs the demo, but does not initialize a project or diagnose local and remote readiness as a stable set of machine-readable checks.

The strongest practices to adopt are:

1. Keep Hermes' existing simple `capabilities` vocabulary, but add a typed selector and an explainable, deterministic route decision. A2A Agent Cards and AGNTCY Directory both treat structured capability metadata as the discovery contract; neither requires an LLM to choose an Agent.
2. Separate declarative preload from runtime ownership. Add explicit get, update, and delete behavior, revisions/timestamps, conflict handling, and an audit event for every registry mutation. Do not silently turn `POST` into both create and update.
3. Make `doctor` a stable data contract: named checks with `pass`, `warn`, `fail`, or `skip`, remediation text, offline mode, bounded network timeouts, and a non-zero exit code on failures.
4. Treat Agent endpoints as outbound network authority. Authentication of the registry caller is necessary but insufficient: reject URL credentials and fragments, constrain schemes and hosts, and require explicit opt-in for private or loopback HTTP targets outside the bundled demo.
5. Extend the existing credential-free demo so it proves capability routing and the runtime registry lifecycle. Preserve its temporary SQLite state and real loopback HTTP dispatch; these are stronger evidence than a mocked routing-only sample.

No new dependency is needed for these changes. Pydantic, FastAPI, Typer, `httpx`, `urllib.parse`, `ipaddress`, `socket`, SQLite, and the existing CI matrix are sufficient.

## Method

This review used only first-party material: repository source, documentation, GitHub commit metadata, and GitHub Releases. A repository qualified when its default branch or an official release showed activity during the 12-month window. Stars were not used as a selection or quality signal. Links below are pinned to the inspected commit where the evidence is implementation-specific.

The search covered:

- official Feishu/Lark Agent integration and command-line tooling;
- open Agent discovery and directory protocols;
- mainstream Agent runtime and orchestration projects with registry or CLI practices;
- self-hosted Agent gateways with explicit outbound and authorization controls.

The official [`larksuite/lark-openapi-mcp`](https://github.com/larksuite/lark-openapi-mcp) was screened but excluded from the active sample because its default branch's last push was 2025-08-14, ten days before the cutoff. This prevents a familiar repository name from being mistaken for recent engineering evidence.

## Current Hermes baseline

The baseline already does the following well:

- Agent configuration rejects unknown fields, validates transport-specific requirements, and bounds IDs and heartbeat intervals ([models](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/blob/30f6945f2f8717c6a939c05848ecb20a586cb14f/src/hermes_a2a/models.py#L22-L50)).
- SQLite persists Agents, workflows, runs, and claimed events behind a small replaceable store boundary ([store](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/blob/30f6945f2f8717c6a939c05848ecb20a586cb14f/src/hermes_a2a/store.py#L13-L43)).
- Registry list, create/upsert, and heartbeat APIs require the internal token ([API](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/blob/30f6945f2f8717c6a939c05848ecb20a586cb14f/src/hermes_a2a/api.py#L90-L107)).
- The workflow engine enforces dependencies, concurrency, timeout, retry, and Agent health, but a task without a literal `agent_id` fails ([workflow engine](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/blob/30f6945f2f8717c6a939c05848ecb20a586cb14f/src/hermes_a2a/workflows.py#L103-L144)).
- `validate-config` reports configuration errors and `demo` runs a real, temporary, zero-credential workflow ([CLI](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/blob/30f6945f2f8717c6a939c05848ecb20a586cb14f/src/hermes_a2a/cli.py#L29-L72)).

The resulting gaps are concrete:

- `POST /agents` is an upsert without create-conflict semantics; there is no `GET /agents/{id}`, update, or delete endpoint.
- YAML-preloaded and runtime-created records have no recorded ownership, revision, update time, or mutation history.
- `capabilities` can be advertised and changed by heartbeat, but cannot select a task target or explain why alternatives were rejected.
- Endpoint validation checks only the `http://`/`https://` prefix. It does not reject embedded credentials, fragments, unsafe resolved addresses, or unapproved hosts.
- There is no project initializer or diagnostic command that separates local checks from optional connectivity checks.

## Comparable projects and transferable strengths

### 1. Lark CLI (`larksuite/cli`)

Recency: default-branch commit [`7874dc1`, 2026-08-24](https://github.com/larksuite/cli/commit/7874dc144b6d94ba5986664dfe65b007dcd5e381); release [`v1.0.89`, 2026-08-21](https://github.com/larksuite/cli/releases/tag/v1.0.89).

This is official Lark tooling and the best direct model for Hermes' CLI behavior.

- `doctor` is explicitly read-only and checks configuration, identities, and connectivity. Each result has a stable name, `pass`/`warn`/`fail`/`skip` status, message, and remediation hint; `--offline` converts network probes into skips rather than failures ([doctor contract](https://github.com/larksuite/cli/blob/7874dc144b6d94ba5986664dfe65b007dcd5e381/cmd/doctor/doctor.go#L29-L88), [diagnostic stages](https://github.com/larksuite/cli/blob/7874dc144b6d94ba5986664dfe65b007dcd5e381/cmd/doctor/doctor.go#L90-L225)).
- Diagnostic probes use bounded timeouts and the same provider-aware HTTP path as real requests, reducing the chance that a green diagnostic tests a different network path from production ([network checks](https://github.com/larksuite/cli/blob/7874dc144b6d94ba5986664dfe65b007dcd5e381/cmd/doctor/doctor.go#L181-L230)).
- `config init` supports interactive and non-interactive modes, receives secrets from stdin rather than a process-list-visible flag, and refuses to create shadow configuration inside an existing Agent workspace unless the user explicitly overrides it ([init options and guard](https://github.com/larksuite/cli/blob/7874dc144b6d94ba5986664dfe65b007dcd5e381/cmd/config/init.go#L26-L115)).

Transfer to Hermes: implement `hermes-a2a init` as non-destructive scaffolding and `hermes-a2a doctor` as ordered checks with JSON output. Keep `--offline` available in credential-free CI. Never accept Feishu secrets as command-line option values.

### 2. Official OpenClaw Lark/Feishu plugin (`larksuite/openclaw-lark`)

Recency: default-branch commit [`dde0be3`, 2026-07-16](https://github.com/larksuite/openclaw-lark/commit/dde0be3680d6fd5443cab426c8f4b3216266346a).

This project supplies direct Feishu integration evidence rather than generic Agent-framework advice.

- Its runtime schema represents DM and group policies as explicit enums, constrains custom domains to HTTPS, separates allow and deny tool policies, and applies cross-field validation when a policy is opened ([policy primitives](https://github.com/larksuite/openclaw-lark/blob/dde0be3680d6fd5443cab426c8f4b3216266346a/src/core/config-schema.ts#L15-L50), [cross-field rule and generated schema](https://github.com/larksuite/openclaw-lark/blob/dde0be3680d6fd5443cab426c8f4b3216266346a/src/core/config-schema.ts#L209-L245)).
- The diagnostic implementation distinguishes credentials, account enablement, API connectivity, application scopes, and user scopes, and gives concrete remediation rather than a single healthy/unhealthy bit ([doctor checks and result vocabulary](https://github.com/larksuite/openclaw-lark/blob/dde0be3680d6fd5443cab426c8f4b3216266346a/src/commands/doctor.ts#L41-L123)).
- The project documents that group exposure and relaxed permission policies materially increase prompt-injection, data-leakage, and unauthorized-operation risk ([security warning](https://github.com/larksuite/openclaw-lark/blob/dde0be3680d6fd5443cab426c8f4b3216266346a/README.md#L24-L38)).
- Its multi-account isolation check makes implicit sharing a distinct unsafe state and can generate explicit per-account Agent bindings ([isolation states](https://github.com/larksuite/openclaw-lark/blob/dde0be3680d6fd5443cab426c8f4b3216266346a/src/core/security-check.ts#L17-L69), [fix generation](https://github.com/larksuite/openclaw-lark/blob/dde0be3680d6fd5443cab426c8f4b3216266346a/src/core/security-check.ts#L128-L188)).

Transfer to Hermes: keep Feishu readiness as a set of independent doctor checks; validate policy combinations before startup; make any broad allow policy explicit. Agent routing metadata must not accidentally collapse tenant or chat isolation.

### 3. Agent2Agent protocol (`a2aproject/A2A`)

Recency: default-branch commit [`16ba526`, 2026-08-18](https://github.com/a2aproject/A2A/commit/16ba52690519bf55b9388e34d4db356efa88aa51); release [`v1.0.1`, 2026-05-28](https://github.com/a2aproject/A2A/releases/tag/v1.0.1).

A2A provides the clearest interoperable vocabulary for declaring what an Agent can do without exposing its internals.

- An Agent Card separates identity, endpoint, protocol capabilities, authentication requirements, and skills. A skill can declare ID, name, description, tags, examples, input/output media types, and skill-specific security requirements ([discovery model](https://github.com/a2aproject/A2A/blob/16ba52690519bf55b9388e34d4db356efa88aa51/docs/topics/agent-discovery.md#L1-L16), [skill tutorial](https://github.com/a2aproject/A2A/blob/16ba52690519bf55b9388e34d4db356efa88aa51/docs/tutorials/python/3-agent-skills-and-card.md#L7-L40)).
- The official discovery guide recognizes three valid modes: well-known cards, curated registries searchable by skill/tag/capability, and direct private configuration. It also notes that the A2A specification does not standardize a curated-registry API ([discovery strategies](https://github.com/a2aproject/A2A/blob/16ba52690519bf55b9388e34d4db356efa88aa51/docs/topics/agent-discovery.md#L17-L71)).
- Sensitive capabilities and internal URLs belong behind authenticated extended cards or selective disclosure. Credentials should be obtained dynamically out of band, not embedded in the card ([secured discovery](https://github.com/a2aproject/A2A/blob/16ba52690519bf55b9388e34d4db356efa88aa51/docs/topics/agent-discovery.md#L73-L106)).
- Clients should inspect declared capabilities before invoking optional operations, and servers must reject operations that were not declared ([capability validation](https://github.com/a2aproject/A2A/blob/16ba52690519bf55b9388e34d4db356efa88aa51/docs/specification.md#L569-L578)).

Transfer to Hermes: evolve the existing registration shape compatibly instead of implementing the full A2A protocol. Normalize capability names, keep endpoint/auth data separate from capability claims, and leave room for later structured skills. Protect all registry reads because Hermes records contain internal endpoints.

### 4. AGNTCY Directory (`agntcy/dir`)

Recency: default-branch commit [`fe70a79`, 2026-08-24](https://github.com/agntcy/dir/commit/fe70a79c00da94436edcd0f14ae3a9025ed2b623); release [`v1.7.0`, 2026-08-18](https://github.com/agntcy/dir/releases/tag/v1.7.0).

AGNTCY Directory is the most directly comparable registry. Hermes should borrow its lifecycle clarity, not its distributed architecture.

- Directory uses structured OASF metadata and hierarchical taxonomies for capability matching, with provenance, signatures, validation, and content-addressed identity ([feature model](https://github.com/agntcy/dir/blob/fe70a79c00da94436edcd0f14ae3a9025ed2b623/README.md#L15-L41)).
- The CLI makes storage lifecycle explicit (`push`, `pull`, `delete`, `info`), separates publication from storage, and supports structured skill/domain filters plus trust and safety filters ([CLI responsibilities](https://github.com/agntcy/dir/blob/fe70a79c00da94436edcd0f14ae3a9025ed2b623/cli/README.md#L1-L18), [search behavior](https://github.com/agntcy/dir/blob/fe70a79c00da94436edcd0f14ae3a9025ed2b623/cli/cmd/search/search.go#L18-L85)).
- Its local daemon is credential-free, listens on localhost, and stores state in embedded SQLite/local OCI by default, while Compose and external stores remain available for production-like deployment ([local and Compose deployment](https://github.com/agntcy/dir/blob/fe70a79c00da94436edcd0f14ae3a9025ed2b623/README.md#L151-L175)).
- `doctor` resolves the same effective client context as real commands and reports config, TCP, gRPC, routing, and optional peer checks. Failed prerequisites produce explicit downstream skips, and any failed check causes a non-zero result ([doctor flow](https://github.com/agntcy/dir/blob/fe70a79c00da94436edcd0f14ae3a9025ed2b623/cli/cmd/doctor/doctor.go#L80-L166), [result schema](https://github.com/agntcy/dir/blob/fe70a79c00da94436edcd0f14ae3a9025ed2b623/cli/cmd/doctor/types.go#L6-L45)).
- Record validation is independently composable in CI, and its signing workflow cleans up records left unsigned after retry exhaustion ([validation action](https://github.com/agntcy/dir/blob/fe70a79c00da94436edcd0f14ae3a9025ed2b623/.github/actions/validate-record/README.md#L1-L47), [signing failure cleanup](https://github.com/agntcy/dir/blob/fe70a79c00da94436edcd0f14ae3a9025ed2b623/.github/actions/sign-record/README.md#L21-L50)).

Transfer to Hermes: keep SQLite and a centralized registry, add explicit CRUD and audit events, and validate declarative records in CI. Do not add DHT, OCI, semantic/LLM search, or cryptographic signing in this release; those solve a federation problem Hermes does not have.

### 5. CrewAI (`crewAIInc/crewAI`)

Recency: default-branch commit [`9e9a857`, 2026-08-23](https://github.com/crewAIInc/crewAI/commit/9e9a8577becc322f98a966ad88d7904251049744); release [`1.15.17`, 2026-08-20](https://github.com/crewAIInc/crewAI/releases/tag/1.15.17).

CrewAI is relevant for scaffolding and declarative authoring rather than registry security.

- A single CLI scaffolds crews, flows, tools, skills, and templates; it supports both an interactive default and explicit variants, while old aliases continue to work with deprecation warnings ([create command](https://github.com/crewAIInc/crewAI/blob/9e9a8577becc322f98a966ad88d7904251049744/docs/edge/en/concepts/cli.mdx#L35-L114)).
- Its classic scaffold separates Agent declarations and task declarations into YAML and keeps custom runtime logic in Python ([project layout](https://github.com/crewAIInc/crewAI/blob/9e9a8577becc322f98a966ad88d7904251049744/README.md#L230-L267)).
- The CLI exposes a compact lifecycle (`create`, `install`, `run`, `test`, `replay`) instead of asking users to assemble internal module commands ([CLI overview](https://github.com/crewAIInc/crewAI/blob/9e9a8577becc322f98a966ad88d7904251049744/docs/edge/en/concepts/cli.mdx#L15-L55), [run and test](https://github.com/crewAIInc/crewAI/blob/9e9a8577becc322f98a966ad88d7904251049744/docs/edge/en/concepts/cli.mdx#L197-L227)).

Transfer to Hermes: `init` should create a coherent minimal project (`.env`, declarative Agents, and an example workflow) in one operation, preserve existing files by default, and print the next validate/demo/serve commands. Avoid adopting CrewAI's model-dependent test path; Hermes' first run must remain deterministic and credential-free.

### 6. Agent Stack (`i-am-bee/agentstack`)

Recency: default-branch commit [`79c7860`, 2026-04-03](https://github.com/i-am-bee/agentstack/commit/79c786049d39684841d77fef9abfd8457a58b0bf); release [`v0.7.1`, 2026-03-30](https://github.com/i-am-bee/agentstack/releases/tag/v0.7.1).

Agent Stack demonstrates a full runtime Agent lifecycle built around A2A cards.

- Its CLI accepts versioned source or image locations, attempts Agent Card discovery when metadata is absent, and gives discovery a bounded timeout with explicit failed/no-card states ([discovery and add](https://github.com/i-am-bee/agentstack/blob/79c786049d39684841d77fef9abfd8457a58b0bf/apps/agentstack-cli/src/agentstack_cli/commands/agent.py#L202-L327)).
- Update is distinct from add, ambiguous textual Agent matches fail rather than selecting arbitrarily, and destructive removal requires confirmation unless explicitly bypassed for automation ([update and unambiguous selection](https://github.com/i-am-bee/agentstack/blob/79c786049d39684841d77fef9abfd8457a58b0bf/apps/agentstack-cli/src/agentstack_cli/commands/agent.py#L330-L442), [removal](https://github.com/i-am-bee/agentstack/blob/79c786049d39684841d77fef9abfd8457a58b0bf/apps/agentstack-cli/src/agentstack_cli/commands/agent.py#L445-L514)).
- A small declarative registry pins reference Agent images by version rather than using mutable latest tags ([registry file](https://github.com/i-am-bee/agentstack/blob/79c786049d39684841d77fef9abfd8457a58b0bf/agent-registry.yaml#L1-L5)).

Transfer to Hermes: make create/update/delete explicit, return a conflict for ambiguous ownership, and never silently select between equal route candidates. Full container discovery and build management are outside Hermes' scope.

### 7. Agentgateway (`agentgateway/agentgateway`)

Recency: default-branch commit [`75b4e6c`, 2026-08-21](https://github.com/agentgateway/agentgateway/commit/75b4e6ce6e0e1ac7959d5548ebe8dbeaede4f180); release [`v1.4.1`, 2026-07-29](https://github.com/agentgateway/agentgateway/releases/tag/v1.4.1).

Agentgateway is useful as a security boundary reference.

- It separates static process configuration from local declarative routing/policy configuration and remote control-plane configuration, translating both dynamic sources to one runtime representation ([configuration layers](https://github.com/agentgateway/agentgateway/blob/75b4e6ce6e0e1ac7959d5548ebe8dbeaede4f180/architecture/configuration.md#L1-L31)).
- Backend types are explicit and mutually exclusive. Its dynamic forward proxy carries a source warning that arbitrary destinations require proper access controls, while ordinary A2A backends name a bounded host and port ([backend contract and warning](https://github.com/agentgateway/agentgateway/blob/75b4e6ce6e0e1ac7959d5548ebe8dbeaede4f180/controller/api/v1alpha1/agentgateway/agentgateway_backend_types.go#L55-L92), [A2A backend](https://github.com/agentgateway/agentgateway/blob/75b4e6ce6e0e1ac7959d5548ebe8dbeaede4f180/controller/api/v1alpha1/agentgateway/agentgateway_backend_types.go#L115-L146)).
- Authorization semantics prefer positive `Allow`/`Require` rules and warn that deny rules can fail open when expression evaluation fails ([RBAC semantics](https://github.com/agentgateway/agentgateway/blob/75b4e6ce6e0e1ac7959d5548ebe8dbeaede4f180/controller/api/v1alpha1/agentgateway/rbac.go#L3-L24)).

Transfer to Hermes: model Agent endpoint access as an allow policy, not a deny list. A runtime registration API that accepts arbitrary URLs would otherwise become an authenticated SSRF primitive.

## Recommended Hermes design

### Registry contract

Preserve the existing registration fields and add only compatible server-managed fields:

- `managed_by`: `declarative` or `runtime`;
- `revision`: monotonically increasing integer;
- `updated_at`, alongside the existing `registered_at`;
- optional `load` copied from the latest heartbeat;
- normalized, unique capability and permission strings.

Expose an explicit lifecycle:

- `POST /agents`: create a runtime record, return `201`; return `409` if the ID exists.
- `GET /agents` and `GET /agents/{agent_id}`: preserve token protection because endpoints and metadata may be sensitive.
- `PUT /agents/{agent_id}`: complete runtime registration replacement, require a revision precondition or reject stale writes with `409`.
- `DELETE /agents/{agent_id}`: idempotent `204` for runtime records; reject deletion of declarative records with `409` and a remediation that points to the YAML file.
- `POST /agents/{agent_id}/heartbeat`: update health, load, and live capabilities without changing ownership or transport identity.

Persist an append-only registry audit event containing event ID, Agent ID, action, revision, owner, and timestamp. Do not log endpoint credentials or arbitrary metadata values.

At startup, declarative YAML should be reconciled deliberately:

- create or refresh records owned by `declarative`;
- never overwrite a runtime-owned ID silently; fail readiness with a clear ownership conflict;
- decide and document whether removing a YAML entry deletes its prior declarative record. For the smallest predictable implementation, delete stale declarative records during reconciliation but never runtime records.

### Capability selector and explainable routing

Add a typed selector that supports:

- all required capabilities;
- all required permissions;
- optional transport;
- exact-match metadata constraints over scalar values only;
- excluded Agent IDs;
- an explicit `allow_degraded` flag, default false.

A task should contain exactly one of `agent_id` or `selector`; this retains every existing workflow while enabling discovery.

Use hard filtering and deterministic ranking, without semantic embeddings or an LLM:

1. Reject offline and busy Agents; reject degraded Agents unless the selector allows them.
2. Require set inclusion for capabilities and permissions.
3. Apply transport, metadata, and exclusion constraints.
4. Rank eligible Agents by health class, then lowest reported load (unknown load last), then oldest `last_heartbeat_at` or stable Agent ID. Choose and document one final tie-break; Agent ID is easiest to reproduce across restarts.

Return a route decision with:

- the normalized selector;
- selected Agent ID or null;
- a summary explanation;
- every candidate's eligibility, score/rank inputs, and concrete reasons such as `missing capability: review`, `status offline`, or `selected by lower load`.

Provide a protected dry-run endpoint such as `POST /agents/route` so callers and `doctor` can inspect a decision without launching a workflow. Persist the selected Agent ID and route explanation with each task result so later changes to the registry do not rewrite history.

### Outbound endpoint security

Use a positive policy with no new dependency:

- parse with `urllib.parse`; allow only HTTP(S), require a hostname, and reject userinfo, fragments, and malformed ports;
- require HTTPS in production unless a hostname or CIDR is explicitly listed for HTTP;
- resolve hostnames and reject unspecified, multicast, link-local, reserved, and metadata-service addresses; require explicit configuration for loopback and private ranges;
- re-check the resolved peer at dispatch time to reduce DNS-rebinding risk;
- keep redirects disabled, bound connect/read timeouts, and cap response bytes;
- make the bundled demo's loopback/Compose hosts an isolated development exception, never an implicit production exception.

The same validation function should run for YAML load, runtime create/update, `validate-config`, `doctor`, and dispatch. This avoids a validator that certifies a path different from the runtime path.

### CLI

`hermes-a2a init`:

- create `.env`, `config/agents.yaml`, and one workflow example from packaged templates;
- never overwrite an existing file unless `--force` is supplied;
- use atomic writes and report `created`, `preserved`, and `failed` paths;
- avoid soliciting secrets; generated values remain placeholders and the command prints the next `validate-config`, `demo`, and `serve` steps;
- support a non-interactive mode on macOS, Windows, and Linux.

`hermes-a2a validate-config`:

- retain current human output and exit behavior;
- add a stable JSON mode containing normalized Agent IDs and all errors;
- validate ownership conflicts, selectors, endpoint policy, and duplicate normalized capabilities;
- separate production credential errors from offline demo validity so a developer can validate the demo without Feishu.

`hermes-a2a doctor`:

- always run local checks: version, Python, writable data directory, environment/settings parse, registry YAML parse/reconcile preview, database open/migration, and endpoint policy;
- in connected mode, add bounded `/healthz`, authenticated `/readyz`, registry list, and optional Agent endpoint probes;
- in `--offline` mode, mark all network checks `skip`;
- emit `{ok, checks:[{name,status,message,hint,elapsed_ms}]}` and exit non-zero only when any check is `fail`;
- never print token or secret values.

### Demo, tests, and documentation

Extend the existing zero-credential demo rather than creating another demo system:

- declaratively preload one Agent and create another through the runtime API;
- route at least one task by capability rather than literal ID;
- print the selected Agent and explanation;
- update and delete the runtime Agent, proving persistence and lifecycle semantics;
- continue using temporary SQLite, synthetic text, real loopback HTTP adapters, and cleanup on every exit path.

Required tests:

- CRUD status codes, persistence across restart, stale revision, declarative/runtime ownership collision, and audit-event redaction;
- selector normalization, every exclusion reason, no-match behavior, deterministic tie-break, degraded opt-in, and route-decision persistence;
- URL userinfo/fragment/scheme cases, IPv4 and IPv6 address classes, allowlisted private target, DNS rebinding simulation, redirect rejection, and response bound;
- `init` preservation/force/atomic failure, JSON validation output, offline doctor, connected doctor with failure/skip propagation, and secret redaction;
- CLI demo on all three operating systems and Compose end-to-end on Linux, retaining the existing Python, type, lint, build, multi-architecture, and secret-scan jobs.

README synchronization should present one copyable progression in both languages:

1. run the zero-credential demo;
2. initialize a project;
3. validate and diagnose it;
4. register/discover an Agent by capability;
5. explain a route decision;
6. configure production Feishu and endpoint allow policies.

Keep API details in a compact table and link the deeper security model from the README. Publish the final README once with the code release, not in formatting-only intermediate commits.

## Practices deliberately not adopted

- **No DHT, federation, OCI registry, signatures, or external schema service.** AGNTCY needs them for cross-organization discovery; Hermes is a self-hosted coordinator with an authenticated local registry.
- **No semantic or LLM-based routing.** Exact capability constraints are offline, reproducible, explainable, and compatible with the zero-credential promise.
- **No full A2A protocol implementation.** A2A's Agent Card vocabulary is useful, but adding transports, streaming, push notification configuration, and extended cards would exceed this release's confirmed scope.
- **No runtime container build/discovery manager.** Agent Stack demonstrates the concept, but it would materially expand Hermes' privilege and dependency surface.
- **No cloud control plane, UI, or required telemetry.** These conflict with the confirmed self-hosted and optional-external-service boundary.
- **No dynamic forward proxy.** Runtime Agent URLs must remain within an explicit outbound allow policy.

## Implementation order

1. Endpoint validation and declarative/runtime ownership semantics.
2. Persistent CRUD, revisions, and audit events.
3. Selector model, pure route evaluator, explanation schema, and dry-run API.
4. Workflow integration with route-decision persistence.
5. `init`, structured validation, and `doctor`.
6. Demo and Compose proof, then bilingual README and release material.

This order keeps each slice independently testable and prevents the new runtime registry from being exposed before its outbound security policy is enforced.
