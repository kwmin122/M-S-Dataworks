---
name: owner-quality-gate
description: Use when reviewing code, architecture, tests, or implementation status to determine whether changes structurally improve product quality or merely mitigate or suppress defects, especially when green tests may hide an incomplete user path.
---

# Owner Quality Gate

## Overview

Review like the accountable owner, not a local implementer.

The job is to decide whether the system is becoming truly higher quality for the user, or whether the work only makes the status look greener.

This skill is specifically for answering two questions:

1. Is the system moving toward real product quality?
2. Are there workaround-style fixes, semantic shortcuts, or fake completion signals left?

## When to Use

Use this when:

- reviewing implementation progress for a feature or phase
- checking whether a fix is structural or only local
- evaluating “is this really ready?” before moving to the next task
- judging whether tests passing reflects user reality
- the user asks if there are shortcuts, workarounds, or fake semantics

Do not use this for generic style feedback or minor refactoring review.

## Hard Rules

- Do not treat passing tests as proof if the end-to-end user path is still open.
- Do not call a status rename a fix if the underlying verification is still missing.
- Do not accept “placeholder for now” as complete behavior.
- Do not hide residual risk to preserve momentum.
- Do not call mitigation or suppression a root fix.

## Review Protocol

### 1. Define the real user outcome

State the user-visible job in one sentence.

Examples:

- “User can generate a proposal from a project and download the verified file.”
- “User can trust that a generated asset marked verified really exists in object storage.”

### 2. Trace the full path

Follow the end-to-end path, not just the local diff.

Check:

- entry point exists
- routing/wiring exists
- service boundary is connected
- persistence is real
- returned state matches reality
- download/review path can use the result

### 3. Classify every important change

Use exactly one label for each significant fix:

- `Root fix`: underlying failure path is removed
- `Mitigation`: user pain or risk is reduced, but the cause remains
- `Suppression`: signal is hidden, threshold relaxed, or status made greener without removing the defect

If the same defect can still occur through the same path, it is not a root fix.

### 4. Check semantic honesty

Look for meaning drift between labels, state, and reality.

Red flags:

- `verified` without real external verification
- file type label differs from actual bytes
- fallback output changes meaning but metadata is unchanged
- response says success while downstream path is unwired
- contract fields exist but are still dummy values

### 5. Check evidence quality

Ask whether the verification actually proves the claim.

Weak evidence:

- unit test only, no integration for the risky boundary
- model field assertions without behavior assertions
- mock-only proof for storage/network/database semantics
- old test results used to justify new claims

### 6. Produce the verdict

Always report in this exact order:

#### Findings

List issues in severity order with file references.

#### Classification

For each key fix or risky area, state:

- `Root fix`
- `Mitigation`
- `Suppression`

#### End-to-end Status

Say one of:

- `closed`
- `partially closed`
- `open`

#### Residual Risk

State what can still fail for the user or business.

#### Owner Judgment

End with one short judgment:

- `not ready`
- `progressing but not ready`
- `execution-ready`
- `production-ready`

## Output Template

Use this template:

```md
**Findings**
- `High`: …

**Classification**
- `Root fix`: …
- `Mitigation`: …
- `Suppression`: …

**End-to-end Status**
- `partially closed`: …

**Residual Risk**
- …

**Owner Judgment**
- `progressing but not ready`
```

## Common Shortcut Patterns

- Green test, broken user path
- Placeholder verification promoted to final semantics
- “Temporary” hardcoded defaults inside a supposedly dynamic contract
- API or model added without UI or router wiring
- Fallback that hides a format or storage mismatch
- Narrow local patch while shared boundary remains inconsistent

## Bottom Line

A system is not high quality because the diff looks careful. It is high quality when the user path is truly closed, the semantics are honest, and the remaining risk is explicitly surfaced.
