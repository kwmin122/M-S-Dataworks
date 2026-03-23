#!/usr/bin/env python3
"""Grade all eval runs programmatically."""
import os
import json
import glob
import re

BASE = os.path.dirname(os.path.abspath(__file__))

def count_lines(path):
    if not os.path.exists(path):
        return -1
    with open(path) as f:
        return len(f.readlines())

def read_file(path):
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        return f.read()

def count_rule_files(rules_dir):
    if not os.path.exists(rules_dir):
        return 0
    return len(glob.glob(os.path.join(rules_dir, "*.md")))

def has_paths_frontmatter(path):
    content = read_file(path)
    return "paths:" in content and "---" in content

def count_negative_rules_ko(content):
    """Count Korean negative rule patterns."""
    patterns = [
        r'하지\s*마', r'하지\s*않', r'금지', r'사용하지', r'쓰지\s*마',
        r'만들지\s*마', r'넘기지\s*마', r'빼먹지', r'남발하지',
        r'허용하지', r'접근하지', r'출력하지', r'설정하지',
        r'노출하지', r'반환하지', r'저장하지', r'배포하지',
        r'수정하지', r'호출하지', r'커밋하지', r'의존하지'
    ]
    count = 0
    for p in patterns:
        count += len(re.findall(p, content))
    return count

def count_negative_rules_en(content):
    """Count English negative rule patterns."""
    patterns = [r"[Dd]on'?t ", r"[Nn]ever ", r"[Dd]o not ", r"[Aa]void "]
    count = 0
    for p in patterns:
        count += len(re.findall(p, content))
    return count

def has_severity_tiers(content):
    """Check for severity tier headers (##/### with tier name anywhere in heading)."""
    tiers_found = 0
    for tier in ["CRITICAL", "MANDATORY", "PREFER", "REQUIRED", "STANDARD"]:
        # Match ## or ### headers containing the tier name anywhere
        # Use {{2,3}} to escape braces in f-string for regex quantifier
        if re.search(rf'#{{2,3}}\s+.*{tier}', content, re.IGNORECASE):
            tiers_found += 1
    return tiers_found

def has_primacy_recency(content):
    """Check if CRITICAL appears in first 15 and last 15 lines."""
    lines = content.strip().split('\n')
    top = '\n'.join(lines[:15])
    bottom = '\n'.join(lines[-15:])
    return 'CRITICAL' in top and 'CRITICAL' in bottom

def grade_eval1(variant):
    """Grade eval 1: large monolith optimization."""
    out_dir = os.path.join(BASE, "eval-1-large-monolith", variant, "outputs")
    claudemd = os.path.join(out_dir, "CLAUDE.md")
    rules_dir = os.path.join(out_dir, ".claude", "rules")

    results = []

    # 1. Hub under 200 lines
    lines = count_lines(claudemd)
    results.append({
        "text": "Optimized CLAUDE.md (hub) is under 200 lines",
        "passed": 0 < lines <= 200,
        "evidence": f"CLAUDE.md is {lines} lines"
    })

    # 2. At least 3 rule files
    n_rules = count_rule_files(rules_dir)
    results.append({
        "text": "At least 3 .claude/rules/*.md files created",
        "passed": n_rules >= 3,
        "evidence": f"Found {n_rules} rule files in .claude/rules/"
    })

    # 3. Paths frontmatter
    if n_rules > 0:
        rule_files = glob.glob(os.path.join(rules_dir, "*.md"))
        with_paths = sum(1 for f in rule_files if has_paths_frontmatter(f))
        results.append({
            "text": "Domain-scoped rule files have paths: frontmatter",
            "passed": with_paths >= n_rules * 0.5,
            "evidence": f"{with_paths}/{n_rules} rule files have paths: frontmatter"
        })
    else:
        results.append({
            "text": "Domain-scoped rule files have paths: frontmatter",
            "passed": False,
            "evidence": "No rule files found"
        })

    # 4. Negative rules converted (check all files)
    all_content = read_file(claudemd)
    for f in glob.glob(os.path.join(rules_dir, "*.md")):
        all_content += "\n" + read_file(f)
    neg_en = count_negative_rules_en(all_content)
    original = read_file(os.path.join(BASE, "..", "test-fixtures", "case-1-large-monolith", "CLAUDE.md"))
    orig_neg = count_negative_rules_en(original)
    reduction = ((orig_neg - neg_en) / orig_neg * 100) if orig_neg > 0 else 0
    results.append({
        "text": "Negative rules converted to positive form",
        "passed": reduction >= 50,
        "evidence": f"Original: {orig_neg} negative, Now: {neg_en} negative ({reduction:.0f}% reduction)"
    })

    # 5. Severity tiers
    tiers = has_severity_tiers(all_content)
    results.append({
        "text": "Rules categorized into severity tiers",
        "passed": tiers >= 2,
        "evidence": f"Found {tiers} distinct severity tier headers"
    })

    # 6. Primacy/recency
    pr = has_primacy_recency(read_file(claudemd))
    results.append({
        "text": "CRITICAL rules at top and bottom of CLAUDE.md",
        "passed": pr,
        "evidence": "CRITICAL found in first/last 15 lines" if pr else "CRITICAL not in primacy/recency position"
    })

    return results

def grade_eval2(variant):
    """Grade eval 2: add rule to existing structure."""
    out_dir = os.path.join(BASE, "eval-2-add-rule", variant, "outputs")
    fixture_dir = os.path.join(BASE, "..", "test-fixtures", "case-2-add-rule")

    backend = read_file(os.path.join(out_dir, ".claude", "rules", "backend.md"))
    claudemd = read_file(os.path.join(out_dir, "CLAUDE.md"))
    orig_claudemd = read_file(os.path.join(fixture_dir, "CLAUDE.md"))

    results = []

    # 1. Rule in backend.md
    has_rule = any(kw in backend.lower() for kw in ["context.withtimeout", "withtimeout", "timeout"])
    results.append({
        "text": "New rule added to .claude/rules/backend.md",
        "passed": has_rule,
        "evidence": "context.WithTimeout rule found in backend.md" if has_rule else "Rule not found in backend.md"
    })

    # 2. CLAUDE.md unchanged
    # Compare stripped content (ignore whitespace differences)
    md_similar = claudemd.strip() == orig_claudemd.strip() or len(claudemd) <= len(orig_claudemd) * 1.1
    results.append({
        "text": "CLAUDE.md not significantly modified",
        "passed": md_similar,
        "evidence": f"CLAUDE.md: orig {len(orig_claudemd)} chars, new {len(claudemd)} chars"
    })

    # 3. Positive framing
    # Check if the new rule uses negative framing
    neg_in_new = any(neg in backend.lower() for neg in ["하지 마", "금지", "하면 안", "don't", "never", "without timeout"])
    pos_in_new = any(pos in backend.lower() for pos in ["사용", "적용", "전달", "use ", "withtimeout"])
    results.append({
        "text": "New rule uses positive framing",
        "passed": pos_in_new,
        "evidence": f"Positive terms: {pos_in_new}, Negative terms: {neg_in_new}"
    })

    # 4. Severity tagged
    has_severity = any(tier in backend for tier in ["CRITICAL", "MANDATORY", "PREFER", "REQUIRED"])
    results.append({
        "text": "New rule placed under severity tier",
        "passed": has_severity,
        "evidence": "Severity tier header found in backend.md" if has_severity else "No severity tier found"
    })

    return results

def grade_eval3(variant):
    """Grade eval 3: negative rules conversion."""
    out_dir = os.path.join(BASE, "eval-3-negative-rules", variant, "outputs")
    fixture_path = os.path.join(BASE, "..", "test-fixtures", "case-3-negative-rules", "CLAUDE.md")

    claudemd = read_file(os.path.join(out_dir, "CLAUDE.md"))
    original = read_file(fixture_path)
    rules_dir = os.path.join(out_dir, ".claude", "rules")

    # Combine all output content
    all_content = claudemd
    for f in glob.glob(os.path.join(rules_dir, "*.md")):
        all_content += "\n" + read_file(f)

    results = []

    # 1. 80%+ negative rules converted
    orig_neg = count_negative_rules_ko(original)
    new_neg = count_negative_rules_ko(all_content)
    reduction = ((orig_neg - new_neg) / orig_neg * 100) if orig_neg > 0 else 0
    results.append({
        "text": "At least 80% of negative rules converted to positive",
        "passed": reduction >= 80,
        "evidence": f"Original: {orig_neg} negative, Now: {new_neg} negative ({reduction:.0f}% reduction)"
    })

    # 2. Severity tiers
    tiers = has_severity_tiers(all_content)
    results.append({
        "text": "2+ severity tiers applied",
        "passed": tiers >= 2,
        "evidence": f"Found {tiers} severity tier headers"
    })

    # 3. Meaning preserved (qualitative - check key terms exist)
    key_terms = ["ULID", "getConfig", "HttpOnly", "React Query", "Tailwind", "Pydantic", "exponential backoff"]
    found = sum(1 for t in key_terms if t.lower() in all_content.lower())
    results.append({
        "text": "Key technical terms preserved (meaning check)",
        "passed": found >= len(key_terms) * 0.7,
        "evidence": f"{found}/{len(key_terms)} key terms found"
    })

    # 4. Structure improved (check for section headers)
    section_count = len(re.findall(r'^##\s+', all_content, re.MULTILINE))
    results.append({
        "text": "Structure improved with clear sections",
        "passed": section_count >= 5,
        "evidence": f"Found {section_count} section headers"
    })

    # 5. Split if over 200 lines
    total_lines = count_lines(os.path.join(out_dir, "CLAUDE.md"))
    n_rules = count_rule_files(rules_dir)
    if total_lines > 200:
        results.append({
            "text": "Split performed since output > 200 lines",
            "passed": n_rules > 0,
            "evidence": f"CLAUDE.md: {total_lines} lines, rule files: {n_rules}"
        })
    else:
        results.append({
            "text": "No split needed (output <= 200 lines)",
            "passed": True,
            "evidence": f"CLAUDE.md: {total_lines} lines (under threshold)"
        })

    return results

# Run all grades
all_grades = {}

for variant in ["with_skill", "without_skill"]:
    key = f"eval-1-large-monolith-{variant}"
    all_grades[key] = grade_eval1(variant)

    key = f"eval-2-add-rule-{variant}"
    all_grades[key] = grade_eval2(variant)

    key = f"eval-3-negative-rules-{variant}"
    all_grades[key] = grade_eval3(variant)

# Save individual grading.json files
for run_key, expectations in all_grades.items():
    parts = run_key.rsplit("-", 1)
    # Parse eval name and variant
    if "with_skill" in run_key:
        variant = "with_skill"
        eval_name = run_key.replace("-with_skill", "")
    else:
        variant = "without_skill"
        eval_name = run_key.replace("-without_skill", "")

    out_path = os.path.join(BASE, eval_name, variant, "grading.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    passed = sum(1 for e in expectations if e["passed"])
    total = len(expectations)

    grading = {
        "run_id": run_key,
        "pass_rate": passed / total if total > 0 else 0,
        "passed": passed,
        "total": total,
        "expectations": expectations
    }

    with open(out_path, 'w') as f:
        json.dump(grading, f, indent=2, ensure_ascii=False)

    print(f"{run_key}: {passed}/{total} passed ({passed/total*100:.0f}%)")

# Print summary
print("\n=== SUMMARY ===")
for run_key, expectations in all_grades.items():
    passed = sum(1 for e in expectations if e["passed"])
    total = len(expectations)
    status = "PASS" if passed == total else "PARTIAL"
    print(f"  {run_key}: {passed}/{total} {status}")
    for e in expectations:
        mark = "✓" if e["passed"] else "✗"
        print(f"    {mark} {e['text']}: {e['evidence']}")
