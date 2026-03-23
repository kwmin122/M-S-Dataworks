---
title: Codex Business Skill Refactor Design
date: 2026-03-12
status: approved
---

# Codex Business Skill Refactor

## Goal

Refactor three externally installed skills into Codex-native global skills:

- business-analyst
- market-researcher
- competitive-analyst

## Why refactor

The installed versions have three issues:

1. They use non-Codex frontmatter and workflow assumptions.
2. They contain framework-specific instructions (`bmad/*`, agent roleplay, subagent assumptions).
3. They are too verbose or too generic to act as reliable operating skills.

## Refactor principles

- frontmatter must use only `name` and `description`
- description must start with `Use when...`
- no BMAD paths, no agent-role ceremony, no unsupported tool declarations
- prefer durable thinking frameworks over long canned examples
- enforce evidence quality, uncertainty handling, and decision outputs

## Target shape

Each skill should contain:

- Overview
- When to Use
- Core Questions
- Process
- Output Standard
- Common Mistakes

## Expected outcome

After refactor:

- the skills are usable in Codex without translation
- they support reusable business work across projects
- they push toward evidence-backed decisions instead of generic brainstorming
