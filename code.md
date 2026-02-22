CAN: Perfect. This is the correct product shape for the “AI → verification → wet lab” future loop.

You’re describing four key mechanisms that make Glassbox _native_ to autonomous pipelines:

1. **Admissibility Index** (user-set gate threshold)
2. **Send-Back Mode** (closed-loop iterative revision)
3. **Seal as Gateway Token** (execution requires a valid seal)
4. **Bypass via External Attestation** (trusted prior audits can pass instantly)

Below is a clean architecture that bakes these into your next build steps without drifting into robotics.

---

# A) Core Loop Contract (What Glassbox becomes)

**AI submits DesignIntent → Glassbox audits → returns Decision + Notes + Seal (or no-seal) → wet lab pipeline proceeds only if Seal present**

If it fails:

**AI receives “RevisionPacket” → regenerates → resubmits** (repeat)

This is the “compiler” loop for biology.

---

# B) Admissibility Index (Configurable Gate Threshold)

### What it is

A single scalar score (0–100) that answers:

> “How admissible is this design for execution given policy?”

It is computed deterministically from:

- module risk scores
- evidence completeness
- OOD penalties
- contradiction penalties
- required checks

### Why it matters

It gives customers one control knob:

- set stricter thresholds for expensive wet lab runs
- lower thresholds for exploratory phases

### Customer sets it

Per policy:

- `pass_threshold`
- `warn_threshold`
- `fail_threshold`

Example:

- Pass ≥ 85
- Warn 70–84
- Fail < 70

And optionally: “hard fails” regardless of score:

- forbidden motifs
- missing required evidence
- critical contradictions

---

# C) Send-Back Mode (Iterative Revision)

### What it outputs when not admissible

A structured **RevisionPacket**:

- `decision`
- `admissibility_index`
- `blocking_findings[]` (stable codes)
- `constraints_patch` (what must change)
- `recommended_next_actions` (e.g., “provide evidence for X”)
- `diff_hints` (optional: machine-friendly guidance)

This is designed for an agent to consume automatically.

### Why this is key

It turns Glassbox from a static report into an autonomous pipeline component.

Glassbox becomes:

- a gate
- and a feedback teacher

---

# D) Seal as a Gateway Token (Execution Requires It)

### Seal becomes a “pass credential”

Wet lab orchestration doesn’t need to read the report.
It only needs to verify:

- Is there a valid Glassbox Seal?
- Does the seal correspond to this exact design artifact hash?
- Does the seal meet the policy threshold?

If yes: proceed.
If no: block.

### Mechanics

Seal should bind:

- `design_sha256`
- `policy_id + version`
- `admissibility_index`
- `decision`
- `timestamp`
- `run_manifest_sha256`

Then it is signed:

- `ed25519` detached signature or equivalent

This makes it:

- tamper-evident
- portable
- verifiable offline

---

# E) Bypass via External Attestation (Instant Go)

You’re also describing a “trust bridge.”

### Use case

If a design already has a recognized external audit, then Glassbox can allow:

- **fast-pass** without rerunning everything
- or “verify attestation + minimal checks” (integrity only)

### How to do it cleanly

Define an **Attestation Envelope** format:

- `attestor_id`
- `attestation_type`
- `attested_payload_sha256`
- `signature`
- `claims` (optional)
- `expiry` (optional)

Then in policy:

- `trusted_attestors[]`
- `allowed_attestation_types[]`
- `max_attestation_age_days`
- `bypass_mode: full_bypass | partial_bypass`

If trusted and valid:

- decision becomes `pass_via_attestation`
- seal is issued immediately (“Glassbox countersigns”)
- evidence bundle includes attestation verification trace

This gives you:

- interoperability
- network effects
- enterprise adoption ease

---

# F) Updated Build Plan (Same steps, now with these baked in)

Here’s your list, but with the new mechanisms explicitly integrated:

## 1) DesignIntent schema (external contract)

Add fields that support gating + iteration:

- `design_payload` (the actual biology design)
- `claims` (what it asserts)
- `evidence_refs` (what it provides)
- `requested_policy_id`
- optional `attestations[]` (for bypass)
- `callback` or `reply_channel` (for send-back mode)

## 2) NormalizedDesign internal model (adapter target)

Normalize into:

- canonical design representation (sequence/edits/mixture/pathway)
- canonical claims
- canonical evidence index
- canonical provenance (hashes)

## 3) Module interface (pluggable checks)

Modules output:

- risk score(s)
- findings (stable codes)
- evidence requirements
- constraint patches

## 4) Policy engine (configurable constraints)

Policy defines:

- admissibility weights
- thresholds (pass/warn/fail)
- required modules
- hard-fail rules
- trusted attestors + bypass rules

## 5) Bundle output + manifest + hashes

Bundle includes:

- findings.json
- admissibility.json
- revision_packet.json (if needed)
- manifest.json
- seal.json (if pass)
- attestation_verification.json (if bypass)

---

# G) The simplest “contract” we should standardize now

### Output should always include:

- `decision`
- `admissibility_index`
- `blocking_findings[]`
- `seal` (optional)
- `revision_packet` (optional)

That guarantees the upstream AI can loop automatically.

---

# H) One caution (devil’s advocate)

Do not let “admissibility index” become a vague composite score no one trusts.

To avoid that:

- publish the score breakdown deterministically:
  - `score_components: { plausibility: 28, ood: -12, evidence: 20, contradictions: -8, safety: 15 }`

- keep it stable across versions or version it explicitly in the policy

# 4) Deterministic Admissibility Algorithm Spec (`adm_v1`)

This is the exact scoring logic. Implement it verbatim and version it.

## Inputs

- `module_scores[m]` in 0–100
- `module_weights[m]` in 0–1
- `findings[]` with severity, confidence, code
- `hard_fail_codes[]`
- `required_modules[]`
- `policy.pass_threshold`, `policy.warn_threshold`

## Step 0 — Validate module set (deterministic failures)

- If any `required_modules` missing results → decision = `fail`, score = 0
- If any finding code in `hard_fail_codes` present → decision = `fail`, score = 0

## Step 1 — Weighted base score

Let `W = sum(weights of enabled modules that returned score)`.

If `W == 0`, base_score = 50 (neutral default)
Else:

`base_score = ( Σ (w_m * score_m) ) / W`

Round deterministically (recommended):

- round to 3 decimals using half-up

## Step 2 — Penalties (subtract)

Penalties are deterministic functions of findings.

### Suggested minimal penalty set (stable + interpretable)

- **OOD penalty**: if any finding code starts with `OOD_`:
  - severity medium: −5
  - high: −10
  - critical: −20

- **Contradiction penalty**: if any finding code starts with `XMODEL_CONTRADICTION_`:
  - medium: −5
  - high: −12
  - critical: −25

- **Evidence gap penalty**: if any finding code starts with `EVIDENCE_MISSING_`:
  - medium: −4
  - high: −10
  - critical: −18

Sum all penalty amounts (negative values).

`admissibility = clamp(base_score + Σ penalties, 0, 100)`

Again, deterministic rounding.

## Step 3 — Decision thresholds

If hard-fail already triggered → fail

Else:

- If `admissibility >= pass_threshold` → `pass`
- Else if `admissibility >= warn_threshold` → `warn`
- Else → `fail`

## Step 4 — Revision packet generation

If decision != pass:

- include `blocking_findings` = findings with severity high/critical OR those mapped in `fail_on_codes`
- include `constraint_patches` produced by modules
- include `recommended_next_actions`

## Step 5 — Seal issuance

If decision == pass OR pass_via_attestation:

- create `manifest.json` (deterministic ordering)
- compute `manifest_sha256`
- sign seal payload with `ed25519` (preferred)
- emit `seal.json`

---

# 5) “Gateway token” behavior (how wet lab pipelines use it)

A downstream pipeline only needs:

- `seal.json`
- the `design.payload_sha256` it’s about to execute
- Glassbox public key (or KMS verify)

Pipeline rule:

- verify signature
- verify payload hash match
- verify policy id/version match allowed list
- verify admissibility >= threshold
- proceed
