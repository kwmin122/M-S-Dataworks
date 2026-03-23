---
name: quality-signal-integrity
description: Prevents quality signal fraud by requiring proof of actual execution before completion claims
skill_type: rigid
---

# Quality Signal Integrity

**Purpose**: Prevent "완료된 것처럼 보이기" optimization. Block completion claims until actual execution is proven.

## When to Invoke (MANDATORY)

You MUST invoke this skill before:
- Any claim of "완료", "통과", "동작", "fixed", "works", "passing"
- Any commit message claiming tests pass or bugs are fixed
- Any request for approval or Task progression
- Any report of "green CI" or test results

## Core Principle

**Appearance ≠ Reality**

- Green CI ≠ tests passed (could be skipped)
- Compilation ≠ execution (error paths untested)
- Function call ≠ integration (preconditions unverified)
- Verification code ≠ verification done (could be fake)

## Mandatory Verification Checklist

Before claiming ANYTHING works, you MUST complete ALL items:

### 1. Test Execution Proof
```bash
# WRONG: Full suite (hides skips)
pytest -q  # 221 passed, 37 skipped ← your new tests might be in the 37!

# RIGHT: Run specific test with -v
pytest path/to/test.py::test_your_new_test -v

# If skipped: read WHY (fixture missing? DB not running?)
# If passed: verify it actually tested your code (check coverage/mocks)
```

**Required evidence:**
- [ ] Specific test name executed (not just suite)
- [ ] `-v` output showing PASSED (not SKIPPED)
- [ ] If skipped: documented WHY and whether it's acceptable
- [ ] Error paths tested (mock exceptions, verify logging/handling)

### 2. Integration State Verification
```bash
# WRONG: Assume preconditions met
asset.revision_id = revision.id  # Did revision get created?

# RIGHT: Verify preconditions before integration
# 1. Read code: where is revision created?
# 2. Trace call chain: is it before this line?
# 3. Add test: verify revision exists before asset link
```

**Required evidence:**
- [ ] Identified all preconditions (DB state, function calls, imports)
- [ ] Verified preconditions are met BEFORE your code runs
- [ ] Test covers the full integration flow (not just your function)

### 3. Mock/Patch Validation
```bash
# WRONG: Guess patch target
with patch("services.web_app.services.generation_service.get_s3_client"):
    # ↑ Assumes get_s3_client is at module level

# RIGHT: Verify actual import location
# 1. Read target file: where is it imported?
# 2. If inside function: patch the source module
# 3. Run test in isolation to verify patch works
```

**Required evidence:**
- [ ] Read target file to find actual import location
- [ ] Patch target matches actual import path
- [ ] Test runs in isolation (not just in full suite where it might skip)

### 4. Error Path Execution
```bash
# WRONG: Write error handling, assume it works
except Exception as e:
    logger.warning("Failed: %s", e)  # Is logger imported?

# RIGHT: Actually trigger the error path
# 1. Mock to raise exception
# 2. Run test
# 3. Verify logger was called (not NameError)
```

**Required evidence:**
- [ ] Every `except` block has a test that triggers it
- [ ] Every `logger.*` call has verified the logger exists
- [ ] Every fallback/degradation path has been executed

### 5. Claim Verification Matrix

Before claiming status, verify ACTUAL execution:

| Claim | Required Evidence | NOT Sufficient |
|-------|-------------------|----------------|
| "Tests pass" | `pytest path/to/test.py::test_name -v` shows PASSED | `pytest -q` green (might be skipped) |
| "Bug fixed" | Test that failed now passes, root cause addressed | Code changed, looks right |
| "Integration works" | Preconditions verified, full flow tested | Function called, no crash |
| "Error handling works" | Exception mocked, handler executed, verified | `except` block written |
| "Verification implemented" | Actual check runs (S3 head, DB query), not fake | `verified` status set |

## Red Flags (Stop and Verify)

If you find yourself saying:
- "Tests are green" → Check: how many skipped? Are MY tests in there?
- "It compiles" → Check: did I run it? What about error paths?
- "I added verification" → Check: does it actually verify, or just set a flag?
- "Integration complete" → Check: are preconditions met? Did I test the flow?
- "Fix committed" → Check: did the SPECIFIC test that failed now pass?

## Process

1. **Before ANY completion claim:**
   ```
   STOP. Open this skill. Run the checklist.
   ```

2. **For each checklist item:**
   - Run the actual command (don't assume)
   - Capture output (don't summarize)
   - Verify it proves what you claim (not just green)

3. **Evidence format:**
   ```
   Claim: "Test X now passes"
   Evidence:
   $ pytest path/to/test.py::test_X -v
   test_X PASSED ✓

   Claim: "Error path tested"
   Evidence:
   $ pytest path/to/test.py::test_error_case -v
   test_error_case PASSED ✓
   Mock verified: logger.warning called with expected message
   ```

4. **Only after ALL evidence collected:**
   - Write commit message (include evidence summary)
   - Report completion (cite evidence)
   - Request approval (link to proof)

## Anti-Patterns (Forbidden)

❌ **"Green CI = done"**
- Full suite passed, but your new tests were skipped
- Fix: Run your specific tests with `-v`

❌ **"Code looks right = works"**
- Function written, but never executed
- Fix: Actually run it (test, manual trigger, trace)

❌ **"I added logging = error handling works"**
- `logger.warning()` written, but logger not imported
- Fix: Mock exception, verify handler executes

❌ **"I called the function = integrated"**
- Function called, but preconditions not met
- Fix: Verify state before call, test full flow

❌ **"Status set to verified = verification done"**
- `status = "verified"` without actual check
- Fix: Implement real check (S3 head, DB query)

## Success Criteria

You have quality signal integrity when:
- ✅ Every claim has command output proof
- ✅ Every test result is PASSED, not SKIPPED
- ✅ Every error path has been executed
- ✅ Every integration has verified preconditions
- ✅ Every mock targets the actual import location

## Examples

### ❌ Bad: Quality Signal Fraud
```
"Fixed asset verification. Tests pass."

Evidence:
$ pytest -q
221 passed, 37 skipped

Problem: Which tests? Are the verification tests in the 37 skipped?
```

### ✅ Good: Quality Signal Integrity
```
"Fixed asset verification. All 3 verification tests now pass."

Evidence:
$ pytest services/web_app/tests/test_generation_service.py::test_verify_assets_with_etag_success -v
test_verify_assets_with_etag_success PASSED ✓

$ pytest services/web_app/tests/test_generation_service.py::test_verify_assets_without_etag_stays_uploaded -v
test_verify_assets_without_etag_stays_uploaded PASSED ✓

$ pytest services/web_app/tests/test_generation_service.py::test_verify_assets_s3_error_stays_uploaded -v
test_verify_assets_s3_error_stays_uploaded PASSED ✓

All 3 branches verified: ETag success, ETag missing, S3 exception.
```

### ❌ Bad: Assumed Integration
```
"Asset-revision linkage implemented."

Code:
asset.revision_id = revision.id

Problem: Where is revision created? Is it before this line?
```

### ✅ Good: Verified Integration
```
"Asset-revision linkage implemented. Verified revision created before asset link."

Evidence:
1. Read complete_document_run() (line 122-138): revision created
2. Read complete_document_run() (line 154-168): asset linkage after revision
3. Test test_complete_document_run_links_assets_to_revision():
   - Creates revision
   - Links asset
   - Asserts asset.revision_id == revision.id ✓
```

## Enforcement

This skill is RIGID. You cannot skip steps.

If you claim completion without evidence:
1. STOP
2. Run this checklist
3. Collect evidence
4. Only then report completion

If evidence reveals issues:
1. DO NOT claim completion
2. Fix the issues
3. Re-run verification
4. Repeat until evidence proves claims

## Integration with Other Skills

- **verification-before-completion**: General principle
- **quality-signal-integrity**: Specific checks to prevent fraud
- **systematic-debugging**: Use when evidence reveals bugs
- **test-driven-development**: Write tests before implementation

Use this skill AFTER writing code, BEFORE claiming it works.

---

**Remember**: The goal is not to appear complete. The goal is to BE complete.

Appearance without substance = quality signal fraud.
Evidence before claims = quality signal integrity.
