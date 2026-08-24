# Separate declarative and runtime registration ownership

Hermes treats `agents.yaml` as desired state and authenticated HTTP registrations as runtime state,
records the owner on every registration, and prevents runtime mutation of declarative registrations.
This avoids restart-time surprises and stale configuration while preserving persistent discovery for
Agents that join at runtime; existing unlabelled database records migrate as legacy registrations and
are claimed by the first declarative or runtime management operation after upgrade.
