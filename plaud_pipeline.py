#!/usr/bin/env python3
"""
Plaud Pipeline helpers — classify, status overview, rename.

Usage:
    python3 plaud_pipeline.py status              # pipeline overview
    python3 plaud_pipeline.py classify             # assign sensitivity to all
    python3 plaud_pipeline.py classify --dry-run   # preview without changes
    python3 plaud_pipeline.py list-hold            # show HOLD items
    python3 plaud_pipeline.py list-date 2026-03-09 # recordings for a date
"""

import argparse
import os
import re
import sys
from pathlib import Path


PLAUD_DIR = Path(os.path.expanduser("~/Obsidian/Personal/_inputs/Plaud"))


def read_frontmatter(path: Path) -> dict:
    """Read YAML frontmatter from a markdown file."""
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"')
    return fm


def write_frontmatter_field(path: Path, field: str, value: str):
    """Add or update a frontmatter field."""
    content = path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) < 3:
        return

    fm_text = parts[1]
    # Check if field exists
    pattern = re.compile(rf"^{field}:.*$", re.MULTILINE)
    if pattern.search(fm_text):
        fm_text = pattern.sub(f"{field}: {value}", fm_text)
    else:
        # Add before closing ---
        fm_text = fm_text.rstrip("\n") + f"\n{field}: {value}\n"

    new_content = f"---{fm_text}---{parts[2]}"
    path.write_text(new_content, encoding="utf-8")


def classify_sensitivity(category: str, device: str) -> str:
    """
    Determine sensitivity from category + device.
    Rules from Plaud Protocol v4.
    """
    # Personal categories
    if category == "personal-diary":
        return "personal"
    if category == "personal-conversation":
        # Could be personal or private — default personal, flag for review
        return "personal"

    # Work categories
    if category in ("work-meeting", "work-1on1", "interview"):
        if device == "pin":
            return "work"  # but might be mixed — flagged separately
        return "work"

    # Voice memo — depends on device
    if category == "voice-memo":
        if device == "pin":
            return "personal"
        return "unknown"

    return "unknown"


def cmd_status(args):
    """Show pipeline status overview."""
    statuses = {}
    categories = {}
    sensitivities = {}
    devices = {}
    total = 0

    for folder in sorted(PLAUD_DIR.iterdir()):
        t = folder / "transcript.md"
        if not t.exists():
            continue
        total += 1
        fm = read_frontmatter(t)
        s = fm.get("status", "unknown")
        c = fm.get("category", "unknown")
        sens = fm.get("sensitivity", "none")
        d = fm.get("device", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
        categories[c] = categories.get(c, 0) + 1
        sensitivities[sens] = sensitivities.get(sens, 0) + 1
        devices[d] = devices.get(d, 0) + 1

    print(f"Total recordings: {total}\n")
    print("Pipeline status:")
    for s, n in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {s:15} {n:3}")
    print("\nCategories:")
    for c, n in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {c:25} {n:3}")
    print("\nSensitivity:")
    for s, n in sorted(sensitivities.items(), key=lambda x: -x[1]):
        print(f"  {s:15} {n:3}")
    print("\nDevices:")
    for d, n in sorted(devices.items(), key=lambda x: -x[1]):
        print(f"  {d:10} {n:3}")


def cmd_classify(args):
    """Assign sensitivity based on category + device."""
    updated = 0
    skipped = 0

    for folder in sorted(PLAUD_DIR.iterdir()):
        t = folder / "transcript.md"
        if not t.exists():
            continue
        fm = read_frontmatter(t)

        # Skip if already has sensitivity (unless --force)
        if fm.get("sensitivity") and fm["sensitivity"] != "none" and not args.force:
            skipped += 1
            continue

        category = fm.get("category", "unknown")
        device = fm.get("device", "unknown")
        sensitivity = classify_sensitivity(category, device)

        if args.dry_run:
            print(f"  {folder.name[:50]:50} {category:25} {device:6} → {sensitivity}")
        else:
            write_frontmatter_field(t, "sensitivity", sensitivity)
            # Update status to indexed if still synced
            if fm.get("status") == "synced":
                write_frontmatter_field(t, "status", "indexed")
            updated += 1

    if args.dry_run:
        print(f"\nDry run: {updated + skipped} files checked")
    else:
        print(f"Updated: {updated}, Skipped: {skipped}")


def cmd_list_hold(args):
    """Show recordings in HOLD (unknown/private sensitivity)."""
    for folder in sorted(PLAUD_DIR.iterdir()):
        t = folder / "transcript.md"
        if not t.exists():
            continue
        fm = read_frontmatter(t)
        sens = fm.get("sensitivity", "none")
        if sens in ("unknown", "private", "none", "private?"):
            cat = fm.get("category", "?")
            dev = fm.get("device", "?")
            date = fm.get("recorded", "?")
            title = fm.get("title", folder.name)[:60]
            print(f"  {date} [{sens:8}] {dev:5} {cat:22} {title}")


def cmd_list_date(args):
    """Show recordings for a specific date."""
    for folder in sorted(PLAUD_DIR.iterdir()):
        t = folder / "transcript.md"
        if not t.exists():
            continue
        fm = read_frontmatter(t)
        if fm.get("recorded") == args.date:
            cat = fm.get("category", "?")
            dev = fm.get("device", "?")
            sens = fm.get("sensitivity", "?")
            status = fm.get("status", "?")
            time = fm.get("recorded_time", "?")
            title = fm.get("title", folder.name)[:50]
            print(f"  {time} {dev:5} {cat:22} {sens:10} {status:10} {title}")


def main():
    parser = argparse.ArgumentParser(description="Plaud Pipeline helpers")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Pipeline overview")

    cls = sub.add_parser("classify", help="Assign sensitivity")
    cls.add_argument("--dry-run", action="store_true")
    cls.add_argument("--force", action="store_true", help="Re-classify even if already set")

    sub.add_parser("list-hold", help="Show HOLD items")

    ld = sub.add_parser("list-date", help="Recordings for a date")
    ld.add_argument("date", help="YYYY-MM-DD")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "status":
        cmd_status(args)
    elif args.command == "classify":
        cmd_classify(args)
    elif args.command == "list-hold":
        cmd_list_hold(args)
    elif args.command == "list-date":
        cmd_list_date(args)


if __name__ == "__main__":
    main()
