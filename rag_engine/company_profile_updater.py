"""Company Profile Updater — update profile.md sections from learned patterns.

Triggered by auto_learner when patterns reach 3+ occurrences.
Maintains version history for rollback capability.

Storage: data/company_skills/{company_id}/profile_history/
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


def update_profile_section(
    company_dir: str,
    section_name: str,
    new_content: str,
    backup: bool = True,
    append_history: bool = True,
) -> bool:
    """Update a specific section in profile.md.

    Args:
        company_dir: Path to company_skills/{company_id}/.
        section_name: Section heading (without ##) to replace.
        new_content: New content for the section body.
        backup: Whether to create a version backup first.

    Returns:
        True if update succeeded, False otherwise.
    """
    profile_path = os.path.join(company_dir, "profile.md")
    if not os.path.isfile(profile_path):
        return False

    with open(profile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find section boundaries: ## SectionName\n ... until next ## or end of file
    pattern = re.compile(
        rf"(## {re.escape(section_name)}\n)(.*?)(?=\n## |\Z)",
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        logger.warning("Section '%s' not found in profile.md", section_name)
        return False

    if backup:
        backup_profile_version(company_dir, reason=f"{section_name} 섹션 업데이트")

    # Replace section content
    new_section = f"## {section_name}\n{new_content}\n"
    updated = content[:match.start()] + new_section + content[match.end():]

    # Append to learning history (skip when caller manages history externally)
    if append_history:
        today = date.today().isoformat()
        history_line = f"- {today}: {section_name} 섹션 업데이트 (auto_learner)"
        if "## 학습 이력" in updated:
            updated = updated.rstrip() + f"\n{history_line}\n"
        else:
            updated += f"\n## 학습 이력\n{history_line}\n"

    # Atomic write
    tmp_path = profile_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(updated)
    os.replace(tmp_path, profile_path)

    return True


def backup_profile_version(company_dir: str, reason: str = "") -> int:
    """Backup current profile.md to profile_history/.

    Returns:
        Version number of the backup.
    """
    profile_path = os.path.join(company_dir, "profile.md")
    history_dir = os.path.join(company_dir, "profile_history")
    os.makedirs(history_dir, exist_ok=True)

    # Determine version number
    changelog = load_changelog(company_dir)
    version = len(changelog.get("versions", [])) + 1

    # Copy profile
    backup_name = f"profile_v{version:03d}.md"
    shutil.copy2(profile_path, os.path.join(history_dir, backup_name))

    # Update changelog
    changelog.setdefault("versions", []).append({
        "version": version,
        "date": date.today().isoformat(),
        "reason": reason,
        "proposals_after": 0,
        "edit_rate_after": None,
    })
    _save_changelog(company_dir, changelog)

    return version


def load_changelog(company_dir: str) -> dict:
    """Load changelog.json from profile_history/."""
    path = os.path.join(company_dir, "profile_history", "changelog.json")
    if not os.path.isfile(path):
        return {"versions": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_changelog(company_dir: str, changelog: dict) -> None:
    """Save changelog.json atomically."""
    history_dir = os.path.join(company_dir, "profile_history")
    os.makedirs(history_dir, exist_ok=True)
    path = os.path.join(history_dir, "changelog.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(changelog, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
