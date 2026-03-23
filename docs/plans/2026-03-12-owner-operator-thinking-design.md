---
title: Owner Operator Thinking Skill Design
date: 2026-03-12
status: approved
---

# Owner Operator Thinking

## Goal

Create a global Codex skill that forces an owner-operator mindset:

- do not hide problems
- distinguish symptom relief from root-cause fixes
- optimize for user and business outcomes, not local code convenience
- keep responsibility until resolution or explicit handoff
- treat completion claims as operational commitments

## Why this skill should exist

The recurring failure mode is not lack of effort. It is local optimization:

- passing tests while user-facing gaps remain
- suppressing warnings and treating that as a structural fix
- claiming completion before end-to-end verification
- solving the nearest layer while leaving business risk intact

This skill should act as a decision lens, not a coding checklist.

## Research basis

The skill is informed by:

- Amazon Ownership and Highest Standards
- Atlassian blameless postmortems
- Google SRE postmortem culture
- GitLab RCA and DRI guidance

These sources align on the same point: surface bad news early, understand the system, assign clear ownership, and fix issues so they stay fixed.

## Recommended shape

Use a single global skill:

- name: `owner-operator-thinking`
- scope: planning, prioritization, reviews, debugging, completion claims, deployment decisions

This is better than a narrower "CEO review" skill because it is reusable across implementation and decision-making, not just status reporting.

## Core rules

1. Start from user impact and business impact.
2. State the actual problem before proposing a fix.
3. Separate structural fixes from mitigations, suppressions, and workarounds.
4. Escalate hidden risk instead of smoothing it over.
5. Own the full path until resolution or explicit handoff.
6. Do not call work complete without verification and residual-risk disclosure.
7. Prefer durable fixes that prevent recurrence.

## Non-goals

- motivational CEO roleplay
- vague "think like an owner" language with no checks
- project-specific policy

## Skill structure

The skill should contain:

- Overview
- When to Use
- Owner Questions
- Hard Rules
- Root Fix vs Mitigation Table
- CEO Priority Gate
- Completion Gate
- Common Failure Patterns

## Success criteria

The skill is successful if it changes behavior in these ways:

- bad news is reported earlier
- completion claims become narrower and evidence-backed
- mitigations are clearly labeled as mitigations
- end-to-end ownership is preserved across handoffs
- user/business impact is discussed before local implementation detail

## Root Fix vs Mitigation classification

The skill must force explicit classification:

- `root fix`: removes the underlying cause or changes the system boundary so the issue does not recur through the same path
- `mitigation`: reduces impact, noise, or probability without removing the underlying cause
- `suppression`: hides the signal without changing the underlying defect

The skill should require that mitigations and suppressions are never reported as structural fixes.

## CEO priority gate

Before recommending the next action, the skill should force a short executive gate:

1. Does this materially improve user outcome?
2. Does this reduce business or operational risk?
3. Is this reversible if wrong?
4. Is this the highest-leverage unresolved constraint?
5. What is the cost of not doing it now?

If the answer is mostly "no", the work should be deprioritized.
