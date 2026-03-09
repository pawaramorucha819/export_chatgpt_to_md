#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from collections import defaultdict


def safe_filename(name: str, max_len: int = 120) -> str:
    name = name.strip() or "untitled"
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name


def ts_to_iso(ts):
    if ts is None:
        return None
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def conv_create_time_key(c):
    t = c.get("create_time")
    try:
        return float(t) if t is not None else 0.0
    except Exception:
        return 0.0


def extract_linear_messages(conv: dict):
    """
    Reconstruct a linear conversation from ChatGPT export mapping tree.
    We follow current_node -> parent -> ... then reverse.
    """
    mapping = conv.get("mapping") or {}
    current = conv.get("current_node")

    chain = []
    seen = set()

    while current and current in mapping and current not in seen:
        seen.add(current)
        node = mapping[current]
        msg = node.get("message")
        if msg:
            author = (msg.get("author") or {}).get("role")
            content = msg.get("content") or {}
            parts = content.get("parts") or []
            # parts can include non-string in rare cases; keep strings only
            text = "\n".join([p for p in parts if isinstance(p, str)]).strip()
            if author in ("user", "assistant") and text:
                chain.append({
                    "role": author,
                    "text": text,
                    "create_time": ts_to_iso(msg.get("create_time")),
                })
        current = node.get("parent")

    chain.reverse()
    return chain


def render_conv_to_md(conv: dict, include_frontmatter: bool = True) -> str:
    title = conv.get("title") or "Untitled"
    cid = conv.get("id") or ""
    created = ts_to_iso(conv.get("create_time"))
    updated = ts_to_iso(conv.get("update_time"))

    msgs = extract_linear_messages(conv)

    lines = []

    if include_frontmatter:
        lines.append("---")
        escaped_title = title.replace(chr(34), r"\"")
        lines.append(f'title: "{escaped_title}"')
        if cid:
            lines.append(f'chatgpt_conversation_id: "{cid}"')
        if created:
            lines.append(f"created_utc: {created}")
        if updated:
            lines.append(f"updated_utc: {updated}")
        lines.append("---")

    lines.append(f"# {title}")
    meta = []
    if created:
        meta.append(f"- Created (UTC): {created}")
    if updated:
        meta.append(f"- Updated (UTC): {updated}")
    if meta:
        lines.append("\n".join(meta))
    lines.append("\n---\n")

    for m in msgs:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"## {role}")
        if m.get("create_time"):
            lines.append(f"*Time (UTC): {m['create_time']}*")
        lines.append("")
        lines.append(m["text"])
        lines.append("\n")

    return "\n".join(lines).rstrip() + "\n"


def load_conversations(path: str):
    if not os.path.exists(path):
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error: Could not read file: {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "conversations" in data and isinstance(data["conversations"], list):
        return data["conversations"]
    print("Error: Unsupported conversations.json structure. Expected a list or {\"conversations\": [...]}.", file=sys.stderr)
    sys.exit(1)


def filter_conversations(convs, since=None, until=None, title_filter=None):
    result = []
    for conv in convs:
        ts = conv.get("create_time")
        if ts is not None:
            try:
                ts = float(ts)
            except Exception:
                ts = None

        if since is not None and (ts is None or ts < since):
            continue
        if until is not None and (ts is None or ts > until):
            continue

        if title_filter is not None:
            title = conv.get("title") or ""
            if title_filter.lower() not in title.lower():
                continue

        result.append(conv)
    return result


def parse_date_arg(s: str) -> float:
    """Parse YYYY-MM-DD string to UTC unix timestamp (start of day)."""
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        print(f"Error: Invalid date format '{s}'. Use YYYY-MM-DD.", file=sys.stderr)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Convert ChatGPT exported conversations.json to Markdown files")
    ap.add_argument("conversations_json", help="Path to conversations.json from ChatGPT export zip")
    ap.add_argument("-o", "--out", default="chatgpt_md", help="Output directory (default: chatgpt_md)")
    ap.add_argument("--mode", choices=["per_chat", "per_month"], default="per_month",
                    help="per_chat: one md per conversation; per_month: bundle by YYYY-MM (default, recommended for NotebookLM)")
    ap.add_argument("--since", metavar="YYYY-MM-DD", help="Include only conversations created on or after this date")
    ap.add_argument("--until", metavar="YYYY-MM-DD", help="Include only conversations created on or before this date")
    ap.add_argument("--title-filter", metavar="KEYWORD", help="Include only conversations whose title contains this keyword (case-insensitive)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be written without actually writing files")
    args = ap.parse_args()

    since_ts = parse_date_arg(args.since) if args.since else None
    until_ts = parse_date_arg(args.until) if args.until else None

    convs = load_conversations(args.conversations_json)
    total_loaded = len(convs)

    convs = filter_conversations(convs, since=since_ts, until=until_ts, title_filter=args.title_filter)
    total_filtered = len(convs)

    if total_filtered == 0:
        print(f"No conversations matched the filter (loaded: {total_loaded}).")
        return

    if not args.dry_run:
        os.makedirs(args.out, exist_ok=True)

    files_written = 0

    if args.mode == "per_chat":
        total = len(convs)
        for i, conv in enumerate(convs):
            title = safe_filename(conv.get("title") or "Untitled")
            created = ts_to_iso(conv.get("create_time")) or "unknown"
            date_prefix = created[:10].replace("-", "") if created != "unknown" else "unknown"
            cid = conv.get("id") or ""
            fn = safe_filename(f"{date_prefix}_{title}_{cid[:12]}") + ".md"
            path = os.path.join(args.out, fn)

            print(f"\r[{i + 1}/{total}] {fn[:60]:<60}", end="", flush=True)

            if not args.dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(render_conv_to_md(conv, include_frontmatter=True))
            files_written += 1

        print()  # newline after progress
        mode_label = "per-chat markdowns"

    else:  # per_month
        buckets = defaultdict(list)
        for conv in convs:
            created = ts_to_iso(conv.get("create_time"))
            ym = (created[:7] if created else "unknown-month")
            buckets[ym].append(conv)

        bucket_list = sorted(buckets.items())
        total = len(bucket_list)

        for i, (ym, items) in enumerate(bucket_list):
            fn = safe_filename(f"{ym}_chatgpt_bundle") + ".md"
            path = os.path.join(args.out, fn)

            print(f"\r[{i + 1}/{total}] {fn:<60}", end="", flush=True)

            lines = []
            lines.append(f"# ChatGPT Export Bundle: {ym}")
            lines.append("\n---\n")
            for conv in sorted(items, key=conv_create_time_key):
                # No frontmatter in bundle files to avoid repeated --- blocks
                lines.append(render_conv_to_md(conv, include_frontmatter=False))
                lines.append("\n\n")

            if not args.dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines).rstrip() + "\n")
            files_written += 1

        print()  # newline after progress
        mode_label = "per-month bundles"

    # Summary
    dry_label = " (dry-run)" if args.dry_run else ""
    print(f"\nDone{dry_label}.")
    print(f"  Conversations loaded : {total_loaded}")
    if total_filtered != total_loaded:
        print(f"  After filter         : {total_filtered}")
    print(f"  Files {'would write' if args.dry_run else 'written'}    : {files_written} {mode_label}")
    if not args.dry_run:
        print(f"  Output directory     : {args.out}")


if __name__ == "__main__":
    main()
