#!/usr/bin/env python3
"""Fetch latest upstream MetaCubeX/meta-rules-dat snapshots and update config/sources.json.

Intended for scheduled GitHub Actions (.github/workflows/sync-upstream.yml) or manual updates.
Does NOT run automatically during offline tests.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "config" / "sources.json"
DATA_DIR = ROOT / "data"


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "shadowrocket-cn-smart-upstream-sync/2.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def resolve_latest_commit(repo_url: str, branch: str) -> str:
    owner_repo = repo_url.rstrip("/").split("github.com/", 1)[1]
    api_url = f"https://api.github.com/repos/{owner_repo}/commits/{branch}"
    payload = json.loads(fetch_bytes(api_url).decode("utf-8"))
    sha = payload["sha"]
    if len(sha) != 40:
        raise ValueError(f"Unexpected commit SHA: {sha!r}")
    return sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--revision",
        help="Pin to a specific upstream commit SHA instead of querying GitHub API",
    )
    args = parser.parse_args()

    manifest = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    repo_url = manifest["repository"]
    owner_repo = repo_url.rstrip("/").split("github.com/", 1)[1]
    branch = manifest.get("upstream_branch", "meta")
    revision = args.revision or resolve_latest_commit(repo_url, branch)

    changed = revision != manifest["revision"]
    for item in manifest["files"]:
        raw_url = (
            f"https://raw.githubusercontent.com/{owner_repo}/{revision}/{item['path']}"
        )
        content = fetch_bytes(raw_url)
        if not content.strip():
            raise ValueError(f"Empty upstream file: {raw_url}")
        digest = hashlib.sha256(content).hexdigest()
        target = DATA_DIR / f"{item['name']}.list"
        if digest != item["sha256"] or not target.exists() or target.read_bytes() != content:
            changed = True
            target.write_bytes(content)
            item["sha256"] = digest
        print(f"Synced {item['name']}.list ({len(content):,} bytes, sha256={digest[:12]}...)")

    if changed:
        manifest["revision"] = revision
        manifest["date"] = date.today().isoformat()
        SOURCES_PATH.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Updated config/sources.json to revision {revision[:12]} ({manifest['date']}).")
    else:
        print(f"Upstream already up-to-date at {revision[:12]}.")


if __name__ == "__main__":
    main()
