#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
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
        # ChatGPT export timestamps are usually unix seconds (float)
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None

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

def render_conv_to_md(conv: dict) -> str:
    title = conv.get("title") or "Untitled"
    cid = conv.get("id") or ""
    created = ts_to_iso(conv.get("create_time"))
    updated = ts_to_iso(conv.get("update_time"))

    msgs = extract_linear_messages(conv)

    lines = []
    lines.append("---")
    lines.append(f'title: "{title.replace(chr(34), r"\"")}"')
    if cid:
        lines.append(f'chatgpt_conversation_id: "{cid}"')
    if created:
        lines.append(f"created_utc: {created}")
    if updated:
        lines.append(f"updated_utc: {updated}")
    lines.append("---")
    lines.append(f"# {title}")
    meta = []
    if created: meta.append(f"- Created (UTC): {created}")
    if updated: meta.append(f"- Updated (UTC): {updated}")
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
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # exports are typically a list of conversations
    if isinstance(data, list):
        return data
    # sometimes wrapped
    if isinstance(data, dict) and "conversations" in data and isinstance(data["conversations"], list):
        return data["conversations"]
    raise ValueError("Unsupported conversations.json structure")

def main():
    ap = argparse.ArgumentParser(description="Convert ChatGPT exported conversations.json to Markdown files")
    ap.add_argument("conversations_json", help="Path to conversations.json from ChatGPT export zip")
    ap.add_argument("-o", "--out", default="chatgpt_md", help="Output directory")
    ap.add_argument("--mode", choices=["per_chat", "per_month"], default="per_month",
                    help="per_chat: one md per conversation; per_month: bundle by YYYY-MM (recommended for NotebookLM)")
    args = ap.parse_args()

    convs = load_conversations(args.conversations_json)
    os.makedirs(args.out, exist_ok=True)

    if args.mode == "per_chat":
        for conv in convs:
            title = safe_filename(conv.get("title") or "Untitled")
            created = ts_to_iso(conv.get("create_time")) or "unknown"
            date_prefix = created[:10].replace("-", "") if created != "unknown" else "unknown"
            cid = conv.get("id") or ""
            fn = safe_filename(f"{date_prefix}_{title}_{cid[:8]}") + ".md"
            path = os.path.join(args.out, fn)
            with open(path, "w", encoding="utf-8") as f:
                f.write(render_conv_to_md(conv))
        print(f"Done. Wrote per-chat markdowns to: {args.out}")

    else:  # per_month
        buckets = defaultdict(list)
        for conv in convs:
            created = ts_to_iso(conv.get("create_time"))
            ym = (created[:7] if created else "unknown-month")  # YYYY-MM
            buckets[ym].append(conv)

        for ym, items in sorted(buckets.items()):
            lines = []
            lines.append(f"# ChatGPT Export Bundle: {ym}")
            lines.append("\n---\n")
            # sort by create_time
            def key(c):
                t = c.get("create_time")
                try:
                    return float(t) if t is not None else 0.0
                except Exception:
                    return 0.0
            for conv in sorted(items, key=key):
                lines.append(render_conv_to_md(conv))
                lines.append("\n\n")
            fn = safe_filename(f"{ym}_chatgpt_bundle") + ".md"
            path = os.path.join(args.out, fn)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines).rstrip() + "\n")
        print(f"Done. Wrote per-month bundles to: {args.out}")

if __name__ == "__main__":
    main()
