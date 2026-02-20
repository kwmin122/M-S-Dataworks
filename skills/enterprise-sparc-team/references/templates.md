# Enterprise SPARC Templates

Use these templates for phase outputs. Copy only the sections needed for the current task.

## Specification + PRD

```markdown
# SPECIFICATION: <project>

## Goal
<one-sentence product goal>

## Functional Requirements
- [ ] FR-01: <requirement>
- [ ] FR-02: <requirement>

## Non-Functional Requirements
- Performance: <target>
- Security: <requirement>
- Reliability: <requirement>

## MVP Scope
In Scope:
- <item>
- <item>

Out of Scope:
- <item>
- <item>

## Success Metrics
- M-01: <metric and threshold>
- M-02: <metric and threshold>
```

```markdown
# PRD: <project>

## User Stories
- As a <persona>, I want <action>, so that <value>.

## Feature Table
| ID | Feature | Priority | Notes |
| --- | --- | --- | --- |
| F-01 | <feature> | Must | <note> |
| F-02 | <feature> | Should | <note> |
```

## Pseudocode

```text
FUNCTION: <name>
INPUT: <types and constraints>
OUTPUT: <type and contract>

PROCEDURE:
1. Validate input.
2. Branch on core condition(s).
3. Call helper(s) for side effects.
4. Return normalized output.

FAILURE PATHS:
- <error case 1> -> <error behavior>
- <error case 2> -> <error behavior>

TEST MAPPING:
- TC-01: <happy path>
- TC-02: <edge case>
- TC-03: <error path>
```

## Architecture + API

```markdown
# ARCHITECTURE: <project>

## System Context
Client -> API -> Service -> Database

## Module Boundaries
- frontend: <responsibility>
- backend: <responsibility>
- shared: <responsibility>

## Data Model
| Entity | Key Fields | Constraints |
| --- | --- | --- |
| User | id, email | email unique |

## Risks
- R-01: <risk> -> <mitigation>
```

```markdown
# API SPEC

| ID | Method | Endpoint | Request | Response | Errors |
| --- | --- | --- | --- | --- | --- |
| API-01 | GET | /api/v1/items | query params | 200 Item[] | 400/500 |
| API-02 | POST | /api/v1/items | JSON body | 201 Item | 400/409/500 |
```

## Tasks + Sprint Plan

```markdown
# TASKS

| ID | Task | Owner | Estimate | Dependency | Status |
| --- | --- | --- | --- | --- | --- |
| BE-01 | Create schema | Backend | 1h | - | Todo |
| BE-02 | Implement endpoint | Backend | 2h | BE-01 | Todo |
| FE-01 | Build screen | Frontend | 2h | API-01 | Todo |

# SPRINT PLAN

## Sprint 1
- Goal: <goal>
- Scope: <task ids>
- Exit Criteria:
  - <criterion>
  - <criterion>
```

## QA Reports

```markdown
# CODE REVIEW REPORT

## Summary
- Files reviewed: <n>
- Findings: <n> (Critical: <n>, High: <n>, Medium: <n>, Low: <n>)

## Findings
| ID | File | Severity | Description | Recommendation |
| --- | --- | --- | --- | --- |
| CR-01 | src/... | High | <issue> | <fix> |

## Decision
Approve | Hold | Reject
```

```markdown
# TEST REPORT

## Coverage
- Unit: <percent>
- Integration: <percent>

## Results
| Suite | Pass | Fail | Notes |
| --- | --- | --- | --- |
| unit | <n> | <n> | <note> |
| integration | <n> | <n> | <note> |

## Open Defects
- DEF-01: <description and impact>
```

## Completion + Deployment

```markdown
# RELEASE CHECKLIST

- [ ] All required tests pass
- [ ] Critical/High defects resolved
- [ ] Secrets are externalized to env
- [ ] README runbook updated
- [ ] CI pipeline green
```

```yaml
version: "3.8"
services:
  backend:
    build: ./src/backend
    ports: ["8000:8000"]
    env_file: .env
  frontend:
    build: ./src/frontend
    ports: ["3000:3000"]
```

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: <project test command>
```
