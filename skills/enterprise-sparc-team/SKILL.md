---
name: enterprise-sparc-team
description: Enterprise-grade multi-agent software delivery orchestration that combines role-based collaboration (Product Manager, Architect, Project Manager, Backend Engineer, Frontend Engineer, QA Engineer, DevOps Engineer) with the SPARC lifecycle (Specification, Pseudocode, Architecture, Refinement/TDD, Completion). Use when users ask for team-mode development, enterprise-style process, planning before coding, structured feature delivery, TDD implementation, code review gates, CI/CD readiness, or end-to-end project execution.
---

# Enterprise Sparc Team

Run as a one-person enterprise development team. Produce documents and code in phase order, then gate progress with explicit approval checkpoints.

## Use This Skill

Trigger on requests like:
- "Build this in team mode"
- "Develop this like a company process"
- "Run SPARC for this feature or project"
- "Write PM/Architect/QA deliverables first"
- "Implement with TDD and release checklist"

Choose execution mode:
- Full pipeline: execute all phases.
- Phase-only: execute one SPARC phase.
- Role-only: execute one role deliverable in the current phase.

## Mandatory Workflow

Follow `S -> P -> A -> R -> C` in order:
1. Specification
2. Pseudocode
3. Architecture
4. Refinement (TDD implementation + QA review)
5. Completion (DevOps and release readiness)

Never jump to coding before Specification and Architecture unless the user explicitly requests a fast bypass.

After each phase, emit:
```text
[CHECKPOINT] <PHASE> complete
Deliverables:
- <file 1>
- <file 2>
Next: <role/phase>
Reply: approve | revise: <change> | restart
```

## Role Matrix

| Role | Core responsibility | Primary outputs |
| --- | --- | --- |
| Product Manager | Define problem, user value, MVP scope | `.team/specification.md`, `.team/prd.md` |
| Architect | Design system boundaries and APIs | `.team/architecture.md`, `.team/api_spec.md` |
| Project Manager | Break work into sequenced tasks | `.team/tasks.md`, `.team/sprint_plan.md` |
| Backend Engineer | Implement APIs/business logic with TDD | `src/backend/`, `tests/backend/` |
| Frontend Engineer | Implement UI/components with contract-first integration | `src/frontend/`, `tests/frontend/` |
| QA Engineer | Review risk, verify tests, publish quality result | `.team/code_review.md`, `.team/test_report.md` |
| DevOps Engineer | Prepare local/prod delivery path | `docker-compose.yml`, `.github/workflows/`, deployment notes |

## Phase Playbook

### S - Specification (PM + Project Manager)

Do:
- Define one-sentence product goal.
- Capture functional and non-functional requirements.
- Limit MVP to a small, shippable scope (target 2-4 hours for first slice).
- Define measurable acceptance metrics.

Produce:
- `.team/specification.md`
- `.team/prd.md`
- `.team/sprint_plan.md` (initial sprint)

Load `references/templates.md` for exact document format.

### P - Pseudocode (Architect + Engineering Leads)

Do:
- Identify core use cases and key functions/components.
- Define inputs, outputs, failure paths, and invariants.
- Map each pseudocode block to a future test case.

Produce:
- `.team/pseudocode.md`
- `.team/test_cases.md` (or section in pseudocode doc)

### A - Architecture (Architect + Project Manager)

Do:
- Finalize module boundaries and ownership (backend/frontend/shared).
- Define API contracts and data models before implementation.
- Create a dependency-aware task graph.

Produce:
- `.team/architecture.md`
- `.team/api_spec.md`
- `.team/tasks.md`

Load `references/templates.md` for architecture and task templates.

### R - Refinement (Backend + Frontend + QA)

Implement with strict TDD:
1. Red: write a failing test.
2. Green: implement the minimum passing code.
3. Refactor: improve clarity without breaking tests.

Apply Andrew Ng coding rules:
- Use explicit types in every public interface.
- Add docstrings/comments for intent, args, returns, and errors.
- Keep each function/component single-purpose.
- Add simple step comments only where logic is non-obvious.
- Start simple, establish a baseline, then iterate with measurable improvements.

Produce:
- `src/backend/`, `src/frontend/`
- `tests/`
- `.team/code_review.md`
- `.team/test_report.md`

### C - Completion (QA + DevOps + PM)

Do:
- Verify all quality and security gates.
- Package runtime with Docker and CI checks.
- Publish run instructions and known limits.

Produce:
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `README.md`
- `.team/release_checklist.md`

## Engineering Guardrails

Always enforce:
- No secret/API key hardcoding.
- `.env` usage and `.gitignore` coverage for local artifacts.
- Test coverage target >= 80% for touched critical paths.
- No deploy recommendation if critical QA findings remain open.

Use branch naming:
- `codex/feature/<requirement-id>-<slug>`
- `codex/fix/<requirement-id>-<slug>`
- `codex/refactor/<requirement-id>-<slug>`

## File Layout

Use this default structure unless project constraints differ:

```text
project/
├── .team/
│   ├── specification.md
│   ├── prd.md
│   ├── pseudocode.md
│   ├── architecture.md
│   ├── api_spec.md
│   ├── tasks.md
│   ├── sprint_plan.md
│   ├── code_review.md
│   ├── test_report.md
│   └── release_checklist.md
├── src/
│   ├── backend/
│   └── frontend/
├── tests/
├── docker-compose.yml
├── .github/workflows/ci.yml
└── README.md
```

## Reference Files

Load these only when needed:
- `references/templates.md`: artifact templates and output skeletons.
- `references/checklists.md`: phase exit gates, quality checks, security checks.

## Prohibited Shortcuts

Do not:
- Start coding without at least Specification and Architecture artifacts.
- Merge or deploy without tests and QA report.
- Skip checkpoint confirmation on phase-only or full-pipeline runs.
- Drop type hints/docstrings on core business logic.
