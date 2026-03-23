---
title: Codex Global Skill Install Design
date: 2026-03-12
status: approved
---

# Codex Global Skill Install Design

## Goal

Install the following proven local agent skills as global Codex skills:

- deployment-readiness
- observability-driven-development
- architecture-decision-review
- api-design-review
- enterprise-security-audit

## Why these five

They match the current operating stage:

- deployment readiness
- observability and monitoring
- architecture reversibility
- API contract safety
- security review before release

## Installation approach

Copy the existing skill directories from:

- `/Users/min-kyungwook/.agents/skills/...`

to:

- `/Users/min-kyungwook/.codex/skills/...`

This is preferred over reauthoring because:

- the skills already exist locally
- one skill includes support files
- copying preserves exact tested behavior

## Verification

After installation:

- each skill directory must exist under `~/.codex/skills`
- each `SKILL.md` must be readable
- `enterprise-security-audit` must also include `owasp-checklist.md` and `threat-model-template.md`
