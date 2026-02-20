# Enterprise SPARC Checklists

Use this file to run consistent phase gates and quality checks.

## Phase Exit Gates

### S - Specification
- [ ] One-sentence goal is explicit.
- [ ] Functional requirements are testable.
- [ ] Non-functional requirements include performance and security.
- [ ] MVP scope is bounded (small first release).
- [ ] At least one measurable success metric is defined.

### P - Pseudocode
- [ ] Core functions/components are enumerated.
- [ ] Input/output contracts are defined.
- [ ] Failure paths are documented.
- [ ] Each pseudocode block maps to a test case.

### A - Architecture
- [ ] Module boundaries and ownership are clear.
- [ ] API contracts and schemas are concrete.
- [ ] Task dependencies are explicit.
- [ ] At least one major risk has mitigation.

### R - Refinement (TDD)
- [ ] Red -> Green -> Refactor loop was used.
- [ ] New/changed behavior has tests.
- [ ] Public interfaces include explicit typing.
- [ ] Core logic includes docstrings and intent comments.
- [ ] QA report records findings and decision.

### C - Completion
- [ ] CI passes.
- [ ] Deployment/runbook docs are updated.
- [ ] Critical and high issues are resolved or waived explicitly.
- [ ] Runtime packaging (Docker or equivalent) is verified.

## Andrew Ng Style Quality Gate

- [ ] Start simple with MVP-first implementation.
- [ ] Establish baseline behavior before optimization.
- [ ] Analyze errors/failures from test results.
- [ ] Track measurable metrics (latency, pass rate, defects).
- [ ] Keep functions/components single-purpose.

## Security Checklist

- [ ] No secrets in source files.
- [ ] `.env` is used for local secrets.
- [ ] `.gitignore` blocks `.env`, logs, cache, build artifacts.
- [ ] Sensitive user data is not logged.
- [ ] Third-party calls avoid leaking secrets.

## Branch and Commit Rules

Branch naming:
- `codex/feature/<requirement-id>-<slug>`
- `codex/fix/<requirement-id>-<slug>`
- `codex/refactor/<requirement-id>-<slug>`

Commit hygiene:
- Keep each commit focused on one change set.
- Reference requirement ID in commit message when available.
- Include tests with behavior changes.

## Checkpoint Message Template

```text
[CHECKPOINT] <PHASE> complete
Summary: <1-3 lines>
Deliverables:
- <file/path>
- <file/path>
Open Risks:
- <risk or "none">
Next: <role/phase>
Reply: approve | revise: <change> | restart
```
