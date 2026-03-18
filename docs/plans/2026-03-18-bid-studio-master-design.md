# Bid Studio Master Design

## One-Line Definition

Bid Studio is an expert workspace that classifies the required submission package for a bid, connects company assets and style skills, generates the documents that can be automated, and manages the evidence and checklist items that still require human action.

---

## Why This Exists

The current product is fragmented:

- `Chat` is good for exploration, search, and analysis, but it is not a reliable production path for bid documents.
- Company data exists in multiple places with different lifetimes and different effects on generation quality.
- Users do not just need "a proposal". They need a submission package, and the required package changes by procurement type, contract method, and evaluation method.

The business problem is not "write a proposal faster". The real problem is:

1. determine what must be submitted for this bid,
2. identify what can be generated automatically,
3. identify what evidence must be collected manually,
4. connect company assets and learned style,
5. produce a submission package that can actually be used.

---

## Product Scope

### Included

- Services (`용역`)
- Goods (`물품`)
- Construction (`공사`)

### Automation Level

Bid Studio is a full-package orchestrator:

- It classifies the required submission package for a project.
- It automatically generates the documents that can be generated.
- It manages evidence, administrative documents, and checklist items that still need human preparation.

### Explicitly Not the Goal

- Replacing all legal/administrative review with AI
- Automatically fabricating evidence documents that must be submitted from authoritative sources
- Immediate removal of Chat as an exploration surface

---

## Product Boundary

### Chat

Role: exploration

- bid search
- bid analysis
- general document analysis
- questions and quick exploration
- alerts and forecast

Chat remains the top-of-funnel research and discovery surface.

### Studio

Role: official bid package production path

- package classification
- project-scoped staging assets
- style learning and pinning
- document generation
- evidence and checklist management
- review and relearning

### Settings

Role: shared master administration

- company shared assets
- shared default style
- account/subscription/administrative settings

---

## Core Product Flow

1. User selects or uploads an RFP
2. Studio analyzes the project and classifies the submission package
3. Studio shows:
   - required generated documents
   - required uploaded evidence
   - required administrative/price items
4. User connects company assets and style
5. Studio generates the automatable documents
6. User uploads or confirms the remaining evidence and administrative items
7. User reviews and edits outputs
8. User can relearn from edits and promote assets/styles to shared defaults

---

## Domain Model

### 1. Bid Project

`bid_projects` remains the project root, extended for Studio.

Required additions:

- `project_type` (`chat` | `studio`)
- `studio_stage`
- `pinned_style_skill_id`
- `active_analysis_snapshot_id`

### 2. Analysis Snapshot

`analysis_snapshots` remains the canonical analysis result.

For Chat -> Studio handoff, the snapshot is cloned:

- new row
- new id
- same org ownership
- original row untouched
- cloned row bound to the new Studio project

### 3. Project Company Assets

New table: `project_company_assets`

Purpose:

- hold project-scoped company staging data
- allow experimentation without polluting shared CompanyDB
- track promote actions

Asset categories:

- track record
- personnel
- technology
- certification
- raw company notes/documents

### 4. Project Style Skills

New table: `project_style_skills`

Purpose:

- store project-scoped style versions
- support derive/pin/promote/rollback
- render `profile_md_content` from structured style JSON

Important constraints:

- project-local version uniqueness
- exactly one shared default per org
- project pin stored on `bid_projects.pinned_style_skill_id`

### 5. Project Package Items

New table: `project_package_items`

Purpose:

- represent the required submission package for a single Studio project
- track generated documents, evidence uploads, price items, and administrative items

Fields should include:

- `project_id`
- `org_id`
- `package_category` (`generated_document` | `evidence` | `administrative` | `price`)
- `document_code`
- `document_label`
- `required`
- `status` (`missing` | `ready_to_generate` | `generated` | `uploaded` | `verified` | `waived`)
- `generation_target` (nullable)
- `asset_id` / `source_document_id` (nullable)
- `notes_json`

This is the missing control plane that turns Studio from "document generator" into "submission package workspace".

### 6. Shared Company Data

Shared data remains in CompanyDB-related models and company profile models.

Rule:

- Studio reads shared data
- Studio writes to project staging
- shared master changes require explicit promote

### 7. Document Run / Revision / Asset

Existing run/revision/asset models remain the persistence layer for generated outputs.

Each generated document must be traceable to:

- analysis snapshot version
- company staging/shared snapshot
- pinned style skill version
- generation contract

---

## Package-First Architecture

### Layer 1. Package Classifier

Input:

- analyzed RFP snapshot

Output:

- procurement domain (`service`, `goods`, `construction`)
- contract/evaluation mode
- required package items
- which of those items are automatable

This must happen before any document generation.

### Layer 2. Asset & Skill Layer

Inputs:

- shared CompanyDB
- project company staging
- pinned style skill

Outputs:

- effective company context
- effective style/profile context

### Layer 3. Generation Layer

Uses existing orchestrators:

- `proposal_orchestrator`
- `wbs_orchestrator`
- `ppt_orchestrator`
- `track_record_orchestrator`

No new generation engine is introduced in the first wave.

### Layer 4. Checklist & Evidence Layer

Tracks everything that cannot or should not be auto-generated:

- supporting evidence
- administrative documents
- price package items
- completion state

### Layer 5. Review & Relearning

Captures edited outputs and derives new project-scoped style versions from diff/feedback.

---

## Procurement Classification Strategy

### Services

Common package patterns:

- negotiated contract package
- qualification/PQ package
- adequacy review / price-focused package

Likely generated items:

- proposal
- technical proposal
- execution plan
- presentation deck
- track record narrative

Likely uploaded evidence:

- experience certificates
- personnel evidence
- licenses/certifications
- tax/payment certificates

### Goods

Common package patterns:

- spec + price package
- negotiated goods proposal package
- catalog/spec compliance package

Likely generated items:

- technical/spec proposal
- comparative response document
- presentation deck

Likely uploaded evidence:

- catalog
- test reports
- certifications
- compliance documents

### Construction

Common package patterns:

- qualification/PQ package
- technical proposal package
- construction execution / methodology package
- price package

Likely generated items:

- technical proposal
- execution or construction plan narrative
- presentation deck

Likely uploaded evidence:

- engineer/technician proof
- major works performance
- equipment or qualification evidence

---

## Studio Information Architecture

Studio should use seven stages, not five.

1. `공고`
   - search, upload, or text input
   - analysis snapshot
2. `제출 패키지`
   - required package auto-classification
   - generated vs upload-required vs administrative split
3. `회사 역량`
   - shared data + project staging
4. `스타일 학습`
   - past proposal/execution plan/deck -> style skill
5. `생성`
   - generate automatable documents
6. `검토/보완`
   - review generated outputs and fill evidence gaps
7. `재학습`
   - derive new style versions from edits

Why seven stages:

- package classification is a first-class product value
- evidence completion is a first-class operational step
- these should not be hidden inside "analysis" or "review"

---

## Trust & Transparency Rules

Every generated output must show:

- which RFP snapshot was used
- which shared company assets were used
- which project staging assets were used
- which style version was pinned
- which package item it satisfies

Every non-generated requirement must show:

- why it was not generated
- what the user still needs to upload or confirm

Studio must answer:

1. What must I submit?
2. What has been generated?
3. What is still missing?
4. What input data was used?
5. What changed after relearning?

---

## Migration Strategy

### Step 1

Keep Chat as exploration, expose Studio as the new official production path.

### Step 2

Add Studio shell and package-first project flow.

### Step 3

Move generation trust from Chat to Studio.

### Step 4

Use feature flags:

- `studio_visible`
- `chat_generation_cutover`

### Step 5

Once Studio is verified end-to-end, turn Chat generation buttons into Studio CTAs.

---

## Delivery Strategy

This is too large for a horizontal build-out.

The correct delivery mode is vertical slices.

### Slice 1

- Studio shell
- RFP intake
- package classifier v1
- company staging
- style pinning
- proposal generation
- contract transparency

### Slice 2

- execution plan
- package checklist state
- promote flows

### Slice 3

- PPT
- track record
- evidence uploads
- review/relearning

### Slice 4

- Chat cutover
- full domain coverage hardening
- HTML PPT preview

---

## MVP vs Master Scope

This design intentionally supports:

- services
- goods
- construction

But implementation should still progress by vertical slices, beginning with the package classifier and a single generated document path.

The first real success condition is not "one proposal generated".

The first real success condition is:

> Given one real RFP, Studio correctly identifies the submission package, generates the automatable document(s), and shows the remaining evidence/checklist items clearly enough for a user to act.

---

## Success Criteria

Studio succeeds when:

1. A user can start from an RFP and see the required submission package
2. Company and style inputs are project-scoped and safe to experiment with
3. Generated outputs are traceable to specific inputs and versions
4. Missing evidence and administrative items are visible and actionable
5. Edited outputs can be relearned without contaminating shared defaults unless explicitly promoted
6. Chat remains useful for exploration but is no longer the official production path

---

## Non-Goals for the First Wave

- Full replacement of Settings with Studio
- Direct switch to `document_orchestrator + pack` as the only generation engine
- Session RAG bridge expansion
- Big-bang removal of legacy Chat generation before Studio is proven

---

## Recommended Next Step

Write the implementation plan around vertical slices, not around UI sections.

The first slice should be:

- Studio project
- RFP intake
- package classifier
- company staging
- pinned style
- proposal generation
- contract transparency

That slice establishes the new canonical path without pretending the whole system is finished.
