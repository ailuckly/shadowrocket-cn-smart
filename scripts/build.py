#!/usr/bin/env python3
"""Build an offline, versioned Shadowrocket config from checked-in snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def domain_rule(value, policy):
    """Convert only exact domains and mihomo +. suffixes, never guess a format."""
    if policy not in {"DIRECT", "PROXY"}:
        raise ValueError(f"Unsupported policy: {policy}")
    suffix = value.startswith("+.")
    domain = value[2:] if suffix else value
    labels = domain.split(".")
    if (not domain or len(domain) > 253 or domain != domain.lower()
            or any(not re.fullmatch(r"[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?", x)
                   for x in labels)):
        raise ValueError(f"Unsupported upstream domain: {value!r}")
    return f"{'DOMAIN-SUFFIX' if suffix else 'DOMAIN'},{domain},{policy}"


def render():
    manifest = json.loads((ROOT / "sources.json").read_text())
    version = manifest["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?", version):
        raise ValueError("Invalid release version")
    groups = {"PROXY": set(), "DIRECT": set()}
    for source in manifest["files"]:
        name = source["name"]
        if not re.fullmatch(r"[a-z!0-9-]+", name):
            raise ValueError("Invalid source name")
        raw = (ROOT / "data" / f"{name}.list").read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Checksum mismatch: {name}; review upstream before updating lock")
        values = raw.decode("utf-8").splitlines()
        if not values:
            raise ValueError(f"Empty source: {name}")
        for value in values:
            rule = domain_rule(value, source["policy"])
            # A country/brand TLD alone is not evidence that every site should bypass the proxy.
            if source["policy"] == "DIRECT" and value.startswith("+.") and "." not in value[2:]:
                continue
            groups[source["policy"]].add(rule)
    text = (ROOT / "config.template.conf").read_text(encoding="utf-8")
    text = text.replace("{{VERSION}}", version).replace("{{DATE}}", manifest["date"])
    for policy, rules in groups.items():
        suffixes = {r.split(",")[1] for r in rules if r.startswith("DOMAIN-SUFFIX,")}
        rules = {r for r in rules if not r.startswith("DOMAIN,") or r.split(",")[1] not in suffixes}
        marker = f"# {{{{{policy}_RULES}}}}"
        if text.count(marker) != 1:
            raise ValueError(f"Expected exactly one {marker}")
        text = text.replace(marker, "\n".join(sorted(rules)))
    if "{{" in text:
        raise ValueError("Unexpanded template marker")
    # Keep the earlier decision for duplicate names instead of relying on importer deduplication.
    seen = set()
    lines = []
    for line in text.splitlines():
        if line.startswith(("DOMAIN,", "DOMAIN-SUFFIX,")):
            name = line.split(",")[1]
            if name in seen:
                continue
            seen.add(name)
        lines.append(line)
    return ROOT / f"Shadowrocket-CN-Smart-v{version}.conf", "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check without writing")
    args = parser.parse_args()
    path, content = render()
    if args.check:
        if not path.exists() or path.read_bytes() != content.encode("utf-8"):
            raise SystemExit("Generated config is missing or stale; run python3 scripts/build.py")
    else:
        path.write_bytes(content.encode("utf-8"))
    print(f"{'Checked' if args.check else 'Built'} {path.name}: {len(content.encode('utf-8')):,} bytes")


if __name__ == "__main__":
    main()
