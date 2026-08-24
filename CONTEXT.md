# Hermes Agent Orchestration

Hermes coordinates bounded work across registered Agents while keeping operator intent,
Agent identity, and routing decisions explicit and traceable.

## Language

**Agent**:
An independently reachable worker that advertises capabilities and accepts bounded tasks.
_Avoid_: Bot, worker service, sub-agent

**Agent registration**:
The durable identity, transport target, capabilities, permissions, and operational state of an Agent.
_Avoid_: Agent config, Agent profile

**Declarative registration**:
An Agent registration owned by the configured `agents.yaml` desired state.
_Avoid_: Static Agent

**Runtime registration**:
An Agent registration owned through the authenticated control interface and preserved across restarts.
_Avoid_: Dynamic Agent

**Legacy registration**:
An Agent registration created before ownership was recorded and claimed by the first declarative or
runtime management operation after upgrade.
_Avoid_: Unknown Agent

**Agent selector**:
The task constraints that an eligible Agent must satisfy, including capabilities, permissions,
transport, and metadata.
_Avoid_: Filter, routing prompt

**Route decision**:
The deterministic, inspectable result of evaluating an Agent selector against current registrations.
_Avoid_: Agent guess, planner output

**Registry event**:
An immutable audit record of a registration lifecycle change and its resulting revision.
_Avoid_: Log message
