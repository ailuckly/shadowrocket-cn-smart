#!/usr/bin/env python3
"""Build an offline, versioned Shadowrocket config from checked-in snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parent
# Mainland and domestic brand TLDs from the checked-in snapshots.
# +.ms is intentionally absent: a single label is not evidence of a direct route.
DIRECT_SINGLE_LABELS = {"cn", "baidu", "yun", "xihuan", "shouji", "anquan", "sohu"}


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


def _earliest_cover(name, suffixes):
    """Return the earliest suffix already seen that matches name, if any."""
    labels = name.split(".")
    found = None
    for start in range(len(labels)):
        candidate = ".".join(labels[start:])
        current = suffixes.get(candidate)
        if current is not None and (found is None or current[0] < found[0]):
            found = current
    return found


def template_overrides(template_text):
    """Direct-exception suffixes before section 3 may hide later upstream rules."""
    suffixes = set()
    for line in template_text.splitlines():
        if line.startswith("# 3."):
            break
        if line.startswith("DOMAIN-SUFFIX,"):
            suffixes.add(line.split(",")[1])
    return suffixes


def collapse_duplicate_targets(lines, authoritative_suffixes=frozenset()):
    """Drop rules that an earlier suffix already matches.

    A same-policy rule under an earlier suffix is redundant. A different
    policy is a conflict, unless that earlier suffix or exact name is one of
    the template's direct exceptions. A later suffix with another policy still
    follows an earlier exact name, so only the apex keeps the exact policy.
    """
    kept = []
    exacts = {}
    suffixes = {}
    conflicts = []
    seen = 0

    def unreachable(name, policy, rule, kind):
        # A later exact host is already decided. A later suffix can still
        # match other hosts under that name, so an exact rule does not hide it.
        if kind == "DOMAIN" and name in exacts:
            return True
        cover = _earliest_cover(name, suffixes)
        if cover is None:
            return False
        _order, suffix, cover_policy = cover
        # The same suffix was already emitted. A broader suffix with the same
        # policy is redundant. An explicit direct exception may hide a later rule.
        if suffix == name or cover_policy == policy or suffix in authoritative_suffixes:
            return True
        conflicts.append(f"{rule} covered by DOMAIN-SUFFIX,{suffix},{cover_policy}")
        return True

    for line in lines:
        if not line.startswith(("DOMAIN,", "DOMAIN-SUFFIX,")):
            kept.append(line)
            continue
        kind, name, policy = line.split(",")
        if kind == "DOMAIN-SUFFIX":
            if unreachable(name, policy, line, kind):
                continue
            if exacts.get(name) == policy:
                kept[:] = [None if item == f"DOMAIN,{name},{policy}" else item for item in kept]
                del exacts[name]
            seen += 1
            suffixes[name] = (seen, name, policy)
            kept.append(line)
            continue
        if unreachable(name, policy, line, kind):
            continue
        exacts[name] = policy
        kept.append(line)
    if conflicts:
        raise ValueError("Unreachable domain rules:\n" + "\n".join(conflicts))
    return [line for line in kept if line is not None]


def render():
    manifest = json.loads((SOURCE / "sources.json").read_text())
    version = manifest["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?", version):
        raise ValueError("Invalid release version")
    groups = {"PROXY": set(), "DIRECT": set()}
    for source in manifest["files"]:
        name = source["name"]
        if not re.fullmatch(r"[a-z!0-9-]+", name):
            raise ValueError("Invalid source name")
        raw = (SOURCE / "data" / f"{name}.list").read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Checksum mismatch: {name}; review upstream before updating lock")
        values = raw.decode("utf-8").splitlines()
        if not values:
            raise ValueError(f"Empty source: {name}")
        for value in values:
            rule = domain_rule(value, source["policy"])
            label = value[2:] if value.startswith("+.") else value
            if (source["policy"] == "DIRECT" and value.startswith("+.")
                    and "." not in label and label not in DIRECT_SINGLE_LABELS):
                continue
            groups[source["policy"]].add(rule)
    template = (SOURCE / "template.conf").read_text(encoding="utf-8")
    overrides = template_overrides(template)
    text = template.replace("{{VERSION}}", version).replace("{{DATE}}", manifest["date"])
    for policy, rules in groups.items():
        suffixes = {r.split(",")[1] for r in rules if r.startswith("DOMAIN-SUFFIX,")}
        rules = {r for r in rules if not r.startswith("DOMAIN,") or r.split(",")[1] not in suffixes}
        marker = f"# {{{{{policy}_RULES}}}}"
        if text.count(marker) != 1:
            raise ValueError(f"Expected exactly one {marker}")
        text = text.replace(marker, "\n".join(sorted(rules)))
    if "{{" in text:
        raise ValueError("Unexpanded template marker")
    lines = collapse_duplicate_targets(text.splitlines(), overrides)
    return ROOT / f"Shadowrocket-CN-Smart-v{version}.conf", "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check without writing")
    args = parser.parse_args()
    path, content = render()
    if args.check:
        if not path.exists() or path.read_bytes() != content.encode("utf-8"):
            raise SystemExit("Generated config is missing or stale; run python3 .maintainer/build.py")
    else:
        path.write_bytes(content.encode("utf-8"))
        for old in ROOT.glob("Shadowrocket-CN-Smart-*.conf"):
            if old != path:
                old.unlink()
    print(f"{'Checked' if args.check else 'Built'} {path.name}: {len(content.encode('utf-8')):,} bytes")


if __name__ == "__main__":
    main()
