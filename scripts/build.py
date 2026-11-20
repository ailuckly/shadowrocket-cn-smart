#!/usr/bin/env python3
"""Modular builder for Shadowrocket CN Smart (Offline & Git Auto-Update Editions + Personal Overlays)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RULES_DIR = ROOT / "rules"
DIST_DIR = ROOT / "dist"

BOOTSTRAP_PROXY_RULES = [
    "DOMAIN-SUFFIX,github.com,PROXY",
    "DOMAIN-SUFFIX,githubusercontent.com,PROXY",
    "DOMAIN-SUFFIX,githubassets.com,PROXY",
    "DOMAIN-SUFFIX,browserleaks.com,PROXY",
    "DOMAIN-SUFFIX,browserleaks.org,PROXY",
    "DOMAIN-SUFFIX,dnsleaktest.com,PROXY",
    "DOMAIN-SUFFIX,dnsleak.com,PROXY",
    "DOMAIN-SUFFIX,ipleak.net,PROXY",
    "DOMAIN-SUFFIX,whoer.net,PROXY",
]


def domain_rule(value: str, policy: str) -> str:
    """Convert exact domains and mihomo +. suffixes into Shadowrocket rules."""
    if policy not in {"DIRECT", "PROXY"}:
        raise ValueError(f"Unsupported policy: {policy}")
    suffix = value.startswith("+.")
    domain = value[2:] if suffix else value
    labels = domain.split(".")
    if (
        not domain
        or len(domain) > 253
        or domain != domain.lower()
        or any(
            not re.fullmatch(r"[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?", x)
            for x in labels
        )
    ):
        raise ValueError(f"Unsupported upstream domain: {value!r}")
    return f"{'DOMAIN-SUFFIX' if suffix else 'DOMAIN'},{domain},{policy}"


def rule_to_domain_set_entry(rule: str) -> str:
    """Convert DOMAIN / DOMAIN-SUFFIX rule to Shadowrocket DOMAIN-SET line."""
    kind, name, _policy = rule.split(",")
    if kind == "DOMAIN-SUFFIX":
        return f".{name}"
    if kind == "DOMAIN":
        return name
    raise ValueError(f"Not a domain rule: {rule}")


def load_list_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _earliest_cover(name: str, suffixes: dict):
    labels = name.split(".")
    found = None
    for start in range(len(labels)):
        candidate = ".".join(labels[start:])
        current = suffixes.get(candidate)
        if current is not None and (found is None or current[0] < found[0]):
            found = current
    return found


def authoritative_direct_suffixes(lines: list[str]) -> set[str]:
    suffixes = set()
    for line in lines:
        if line.startswith("DOMAIN-SUFFIX,"):
            parts = line.split(",")
            if len(parts) >= 3 and parts[2] == "DIRECT":
                suffixes.add(parts[1])
    return suffixes


def collapse_duplicate_targets(
    lines: list[str],
    authoritative_suffixes=frozenset(),
    allow_cross_policy_drop: bool = False,
) -> list[str]:
    """Drop rules already matched by an earlier exact or suffix rule.

    For standard two-policy builds (allow_cross_policy_drop=False), a narrower rule
    with a different policy under an earlier suffix raises ValueError unless that
    earlier suffix is an explicit direct exception.
    For multi-group builds (allow_cross_policy_drop=True), earlier service-group
    suffixes intentionally claim subdomains before the bulk PROXY/DIRECT tables.
    """
    kept = []
    exacts = {}
    suffixes = {}
    conflicts = []
    seen = 0

    def unreachable(name: str, policy: str, rule: str, kind: str) -> bool:
        if kind == "DOMAIN" and name in exacts:
            return True
        cover = _earliest_cover(name, suffixes)
        if cover is None:
            return False
        _order, suffix, cover_policy = cover
        if (
            suffix == name
            or cover_policy == policy
            or suffix in authoritative_suffixes
            or allow_cross_policy_drop
        ):
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
                kept[:] = [
                    None if item == f"DOMAIN,{name},{policy}" else item for item in kept
                ]
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


def load_upstream_groups(manifest: dict, filters: dict) -> dict[str, list[str]]:
    direct_single = set(filters["direct_single_labels"])
    proxy_cn_keep = set(filters["proxy_cn_keep"])
    direct_excluded = set(filters["direct_excluded_domains"])

    groups = {"PROXY": set(), "DIRECT": set()}
    for source in manifest["files"]:
        name = source["name"]
        if not re.fullmatch(r"[a-z!0-9-]+", name):
            raise ValueError(f"Invalid source name: {name}")
        raw = (DATA_DIR / f"{name}.list").read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(
                f"Checksum mismatch: {name}; review upstream before updating lock"
            )
        values = raw.decode("utf-8").splitlines()
        if not values:
            raise ValueError(f"Empty source: {name}")
        for value in values:
            rule = domain_rule(value, source["policy"])
            label = value[2:] if value.startswith("+.") else value
            if (
                source["policy"] == "DIRECT"
                and value.startswith("+.")
                and "." not in label
                and label not in direct_single
            ):
                continue
            if source["policy"] == "DIRECT" and label in direct_excluded:
                continue
            if (
                name in {"apple", "microsoft"}
                and (label == "cn" or label.endswith(".cn"))
                and label not in proxy_cn_keep
            ):
                continue
            groups[source["policy"]].add(rule)

    cleaned = {}
    for policy, rules in groups.items():
        suffixes = {
            r.split(",")[1] for r in rules if r.startswith("DOMAIN-SUFFIX,")
        }
        deduped = {
            r
            for r in rules
            if not r.startswith("DOMAIN,") or r.split(",")[1] not in suffixes
        }
        cleaned[policy] = sorted(deduped)
    return cleaned


def expand_service_rules(services: list[dict]) -> list[str]:
    lines = ["# 3. 细分服务策略组（离线内置；位于第 2 段中国区直连例外之后）。"]
    for svc in services:
        lines.append(f"# {svc['comment']}")
        policy = svc["policy"]
        for entry in svc["rules"]:
            parts = entry.split(",")
            if parts[0] in {"IP-CIDR", "IP-CIDR6"} and parts[-1] == "no-resolve":
                lines.append(f"{parts[0]},{parts[1]},{policy},no-resolve")
            else:
                lines.append(f"{entry},{policy}")
    lines.append("# GitHub 与出口泄露检测站显式走 PROXY")
    lines.extend(BOOTSTRAP_PROXY_RULES)
    return lines


def _domain_rules(lines: list[str]) -> list[tuple[str, str]]:
    out = []
    for line in lines:
        parts = line.split(",")
        if len(parts) >= 3 and parts[0] in {"DOMAIN", "DOMAIN-SUFFIX"}:
            out.append((parts[0], parts[1]))
    return out


def prune_domain_set(
    rules: list[str], earlier: list[tuple[str, str]]
) -> list[str]:
    """Drop DOMAIN-SET entries that can never match.

    An entry is unreachable when an earlier rule (any policy) already claims it,
    or when a suffix inside the same set covers it (a DOMAIN-SET is one rule, so
    order inside it does not matter).
    """
    earlier_exacts = {n for k, n in earlier if k == "DOMAIN"}
    earlier_suffixes = {n for k, n in earlier if k == "DOMAIN-SUFFIX"}
    own_suffixes = {r.split(",")[1] for r in rules if r.startswith("DOMAIN-SUFFIX,")}

    def ancestors(name: str):
        labels = name.split(".")
        return (".".join(labels[i:]) for i in range(1, len(labels)))

    kept = []
    for rule in rules:
        kind, name, _policy = rule.split(",")
        if kind == "DOMAIN" and name in earlier_exacts:
            continue
        if name in earlier_suffixes or any(a in earlier_suffixes for a in ancestors(name)):
            continue
        if kind == "DOMAIN" and name in own_suffixes:
            continue
        if any(a in own_suffixes for a in ancestors(name)):
            continue
        kept.append(rule)
    return kept


def build_ruleset_files(
    manifest: dict,
    upstream: dict[str, list[str]],
    services: list[dict],
    lan_lines: list[str],
    direct_exc_lines: list[str],
    direct_extra_lines: list[str],
) -> dict[Path, str]:
    """Generate rules/ artifacts used by Git Online (DOMAIN-SET / RULE-SET) configs."""
    version = manifest["version"]
    date = manifest["date"]
    outputs: dict[Path, str] = {}

    # Online order: LAN → direct exceptions → (core/services) → PROXY set → direct extra → DIRECT set.
    before_proxy = _domain_rules(lan_lines + direct_exc_lines)
    proxy_rules = prune_domain_set(upstream["PROXY"], before_proxy)
    before_direct = before_proxy + _domain_rules(proxy_rules + direct_extra_lines)
    direct_rules = prune_domain_set(upstream["DIRECT"], before_direct)
    pruned = {"PROXY": proxy_rules, "DIRECT": direct_rules}

    # DOMAIN-SET files (leading dot = suffix, bare = exact)
    for key, filename, desc in [
        ("PROXY", "proxy-domains.txt", "境外域名 DOMAIN-SET（含清洗后的 Apple/Microsoft 全球域名）"),
        ("DIRECT", "direct-domains.txt", "国内直连域名 DOMAIN-SET（已清洗境外脏数据与海外 PT）"),
    ]:
        entries = sorted({rule_to_domain_set_entry(r) for r in pruned[key]})
        header = [
            f"# Shadowrocket CN Smart v{version} | {date} | {desc}",
            f"# 自动生成，请勿手工修改。共 {len(entries)} 条。",
        ]
        outputs[RULES_DIR / filename] = "\n".join(header + entries) + "\n"

    # Per-service RULE-SET files
    for svc in services:
        slug = svc["slug"]
        header = [
            f"# Shadowrocket CN Smart v{version} | {date} | {svc['policy']}: {svc['comment']}",
            f"# 自动生成，请勿手工修改。共 {len(svc['rules'])} 条。",
        ]
        outputs[RULES_DIR / "services" / f"{slug}.list"] = (
            "\n".join(header + svc["rules"]) + "\n"
        )

    return outputs


def apply_general_overlay(general_text: str, profile: dict | None) -> str:
    if not profile:
        return general_text.rstrip()
    lines = general_text.rstrip().splitlines()
    out = []
    skip_append = profile.get("skip_proxy_append", [])
    tun_append = profile.get("tun_excluded_routes_append", [])
    overrides = profile.get("general_overrides", {})
    seen_keys = set()

    for line in lines:
        if " = " in line and not line.strip().startswith("#"):
            key, val = line.split(" = ", 1)
            seen_keys.add(key)
            if key == "skip-proxy" and skip_append:
                existing = [x.strip() for x in val.split(",") if x.strip()]
                merged = existing + [x for x in skip_append if x not in existing]
                line = f"skip-proxy = {','.join(merged)}"
            elif key == "tun-excluded-routes" and tun_append:
                existing = [x.strip() for x in val.split(",") if x.strip()]
                merged = [x for x in tun_append if x not in existing] + existing
                line = f"tun-excluded-routes = {','.join(merged)}"
            elif key in overrides:
                line = f"{key} = {overrides[key]}"
        out.append(line)

    extra_lines = []
    always_real_ip = profile.get("always_real_ip", [])
    if always_real_ip:
        extra_lines.append("# 企业 VPN / 内网域名强制返回真实 IP，避免 Fake-IP 导致企业隧道不可达。")
        extra_lines.append(f"always-real-ip = {','.join(always_real_ip)}")
    for k, v in overrides.items():
        if k not in seen_keys:
            extra_lines.append(f"{k} = {v}")
    if extra_lines:
        out.append("")
        out.extend(extra_lines)
    return "\n".join(out)


def apply_host_overlay(host_text: str, profile: dict | None) -> str:
    if not profile or not profile.get("hosts"):
        return host_text.rstrip()
    lines = host_text.rstrip().splitlines()
    lines.append("# 本机私有 Host 映射（如企业内网服务）")
    for k, v in profile["hosts"].items():
        lines.append(f"{k} = {v}")
    return "\n".join(lines)


def render_config(
    *,
    manifest: dict,
    general_text: str,
    host_text: str,
    proxy_groups_text: str | None,
    lan_lines: list[str],
    direct_exc_lines: list[str],
    proxy_core_lines: list[str],
    direct_extra_lines: list[str],
    upstream: dict[str, list[str]],
    services: list[dict],
    mode: str,
    with_groups: bool,
    profile: dict | None = None,
) -> str:
    """Render one Shadowrocket .conf variant (offline/online x lite/group x optional overlay)."""
    version = manifest["version"]
    date = manifest["date"]
    repo = manifest["project_repo"]
    branch = manifest["project_branch"]
    raw_base = f"https://raw.githubusercontent.com/{repo}/{branch}/rules"

    edition_label = (
        f"{'策略组' if with_groups else '极简'}"
        f"{'离线单文件版' if mode == 'offline' else ' Git 自动更新版 (DOMAIN-SET)'}"
    )
    if profile:
        edition_label += f" + {profile.get('label', '本机私有 Overlay')}"

    header = [
        f"# Shadowrocket CN Smart v{version} · {edition_label} | {date}",
        "# 导入后选择：全局路由 → 配置。"
        + (
            "各服务策略组默认跟随首页节点（哔哩哔哩默认直连），可随时单点切换。"
            if with_groups
            else "PROXY 使用首页当前节点。"
        ),
        "# 国内服务与局域网直连，境外服务优先代理，未匹配域名经代理 DoH 解析后 CN 直连、其余代理。",
        (
            "# 规则已全量离线内置；不含节点账号或私钥，默认无需安装证书。"
            if mode == "offline"
            else "# 核心防泄露与直连例外已内联，大体积域名表由本仓库 Git 自动更新（DOMAIN-SET 低内存模式）。"
        ),
        f"# GPL-3.0-only | https://github.com/{repo}",
    ]

    general_block = apply_general_overlay(general_text, profile)
    host_block = apply_host_overlay(host_text, profile)
    auth_suffixes = authoritative_direct_suffixes(direct_exc_lines)

    rule_lines: list[str] = []
    if profile and profile.get("top_rules"):
        rule_lines.append("# 0. 本机私有高优先级规则（如企业 VPN 网关、内网域名、远程桌面直连）。")
        rule_lines.extend(profile["top_rules"])
        rule_lines.append("")

    rule_lines.extend(lan_lines)
    rule_lines.append("")
    rule_lines.extend(direct_exc_lines)
    rule_lines.append("")

    if mode == "offline":
        if with_groups:
            rule_lines.extend(expand_service_rules(services))
        else:
            rule_lines.extend(proxy_core_lines)
        rule_lines.append("")
        rule_lines.append(
            "# 4. 境外域名与 Apple/Microsoft 全球服务，优先于国内域名（已过滤中国区直连例外）。"
        )
        rule_lines.extend(upstream["PROXY"])
        rule_lines.append("")
        rule_lines.append("# 5. 国内服务域名。未被更早规则命中的 .cn 在本段直连。")
        rule_lines.extend(direct_extra_lines)
        rule_lines.extend(upstream["DIRECT"])
        rule_lines.append("")
        rule_lines.append(
            "# 6. 其余未命中域名经代理 DoH 解析后按 CN 地理库直连，防止长尾国内服务误走代理且不泄露 DNS。"
        )
        rule_lines.append("GEOIP,CN,DIRECT")
        rule_lines.append("FINAL,PROXY")
        rule_lines = collapse_duplicate_targets(
            rule_lines,
            authoritative_suffixes=auth_suffixes,
            allow_cross_policy_drop=with_groups,
        )
    elif mode == "online":
        if with_groups:
            rule_lines.append(
                "# 3. GitHub 规则源引导（内联防自举死锁）与细分服务策略组（Git 托管 RULE-SET 自动更新）。"
            )
            rule_lines.extend(BOOTSTRAP_PROXY_RULES)
            for svc in services:
                rule_lines.append(
                    f"RULE-SET,{raw_base}/services/{svc['slug']}.list,{svc['policy']}"
                )
        else:
            rule_lines.extend(proxy_core_lines)
        rule_lines.append("")
        rule_lines.append(
            "# 4. 境外域名 DOMAIN-SET（本仓库 Git 自动更新，Shadowrocket 原生哈希/Trie 索引，显著降低 iOS 内存）。"
        )
        rule_lines.append(f"DOMAIN-SET,{raw_base}/proxy-domains.txt,PROXY")
        rule_lines.append("")
        rule_lines.append("# 5. 高频国内补充与国内域名 DOMAIN-SET（本仓库 Git 自动更新）。")
        rule_lines.extend(direct_extra_lines)
        rule_lines.append(f"DOMAIN-SET,{raw_base}/direct-domains.txt,DIRECT")
        rule_lines.append("")
        rule_lines.append(
            "# 6. 其余未命中域名经代理 DoH 解析后按 CN 地理库直连，防止长尾国内服务误走代理且不泄露 DNS。"
        )
        rule_lines.append("GEOIP,CN,DIRECT")
        rule_lines.append("FINAL,PROXY")
        rule_lines = collapse_duplicate_targets(
            rule_lines,
            authoritative_suffixes=auth_suffixes,
            allow_cross_policy_drop=with_groups,
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    parts = ["\n".join(header), general_block]
    if with_groups:
        assert proxy_groups_text is not None
        parts.append(proxy_groups_text.rstrip())
    parts.append("[Rule]\n" + "\n".join(rule_lines).rstrip())
    parts.append(host_block)
    return "\n\n".join(parts) + "\n"


def render_all() -> dict[Path, str]:
    manifest = json.loads((CONFIG_DIR / "sources.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?", version):
        raise ValueError(f"Invalid release version: {version}")

    filters = json.loads((CONFIG_DIR / "filters.json").read_text(encoding="utf-8"))
    services = json.loads(
        (CONFIG_DIR / "rules" / "services.json").read_text(encoding="utf-8")
    )
    general_text = (CONFIG_DIR / "general.ini").read_text(encoding="utf-8")
    host_text = (CONFIG_DIR / "host.ini").read_text(encoding="utf-8")
    proxy_groups_text = (CONFIG_DIR / "proxy-groups.ini").read_text(encoding="utf-8")

    lan_lines = load_list_lines(CONFIG_DIR / "rules" / "01-lan.list")
    direct_exc_lines = load_list_lines(
        CONFIG_DIR / "rules" / "02-direct-exceptions.list"
    )
    proxy_core_lines = load_list_lines(CONFIG_DIR / "rules" / "03-proxy-core.list")
    direct_extra_lines = load_list_lines(CONFIG_DIR / "rules" / "04-direct-extra.list")

    upstream = load_upstream_groups(manifest, filters)

    outputs = build_ruleset_files(
        manifest, upstream, services, lan_lines, direct_exc_lines, direct_extra_lines
    )

    variants = [
        ("Shadowrocket-CN-Smart-Offline.conf", "offline", False),
        ("Shadowrocket-CN-Smart-Group-Offline.conf", "offline", True),
        ("Shadowrocket-CN-Smart-Online.conf", "online", False),
        ("Shadowrocket-CN-Smart-Group-Online.conf", "online", True),
    ]
    for filename, mode, with_groups in variants:
        outputs[DIST_DIR / filename] = render_config(
            manifest=manifest,
            general_text=general_text,
            host_text=host_text,
            proxy_groups_text=proxy_groups_text if with_groups else None,
            lan_lines=lan_lines,
            direct_exc_lines=direct_exc_lines,
            proxy_core_lines=proxy_core_lines,
            direct_extra_lines=direct_extra_lines,
            upstream=upstream,
            services=services,
            mode=mode,
            with_groups=with_groups,
        )
    return outputs


def render_profile(profile_path: Path) -> dict[Path, str]:
    manifest = json.loads((CONFIG_DIR / "sources.json").read_text(encoding="utf-8"))
    filters = json.loads((CONFIG_DIR / "filters.json").read_text(encoding="utf-8"))
    services = json.loads(
        (CONFIG_DIR / "rules" / "services.json").read_text(encoding="utf-8")
    )
    general_text = (CONFIG_DIR / "general.ini").read_text(encoding="utf-8")
    host_text = (CONFIG_DIR / "host.ini").read_text(encoding="utf-8")
    proxy_groups_text = (CONFIG_DIR / "proxy-groups.ini").read_text(encoding="utf-8")

    lan_lines = load_list_lines(CONFIG_DIR / "rules" / "01-lan.list")
    direct_exc_lines = load_list_lines(
        CONFIG_DIR / "rules" / "02-direct-exceptions.list"
    )
    proxy_core_lines = load_list_lines(CONFIG_DIR / "rules" / "03-proxy-core.list")
    direct_extra_lines = load_list_lines(CONFIG_DIR / "rules" / "04-direct-extra.list")
    upstream = load_upstream_groups(manifest, filters)

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    out_dir = (profile_path.parent / profile.get("output_dir", ".")).resolve()
    prefix = profile.get("output_prefix", "Shadowrocket-CN-Smart-Host")
    with_groups = bool(profile.get("with_groups", True))

    outputs: dict[Path, str] = {}
    for mode, suffix in [("offline", "Offline"), ("online", "Online")]:
        outputs[out_dir / f"{prefix}-{suffix}.conf"] = render_config(
            manifest=manifest,
            general_text=general_text,
            host_text=host_text,
            proxy_groups_text=proxy_groups_text if with_groups else None,
            lan_lines=lan_lines,
            direct_exc_lines=direct_exc_lines,
            proxy_core_lines=proxy_core_lines,
            direct_extra_lines=direct_extra_lines,
            upstream=upstream,
            services=services,
            mode=mode,
            with_groups=with_groups,
            profile=profile,
        )
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated rules/ and dist/ files without writing",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        help="Build personal private Overlay configs from a profile JSON (e.g. host-conf/profile.json)",
    )
    args = parser.parse_args()

    if args.profile:
        outputs = render_profile(args.profile)
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
            print(f"Built overlay {path.relative_to(ROOT)}: {len(content.encode('utf-8')):,} bytes")
        return

    outputs = render_all()
    if args.check:
        stale = []
        for path, content in outputs.items():
            if not path.exists() or path.read_bytes() != content.encode("utf-8"):
                stale.append(str(path.relative_to(ROOT)))
        # Ensure no stray generated .conf files in dist/
        expected_dist = {p for p in outputs if p.parent == DIST_DIR}
        actual_dist = set(DIST_DIR.glob("*.conf"))
        for extra in sorted(actual_dist - expected_dist):
            stale.append(f"unexpected:{extra.relative_to(ROOT)}")
        if stale:
            raise SystemExit(
                "Generated artifacts are missing or stale (run python3 scripts/build.py):\n  "
                + "\n  ".join(stale)
            )
        print(f"Checked {len(outputs)} generated files in rules/ and dist/: OK")
    else:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        # Clean up any stale files in dist/ or rules/services/
        expected_paths = set(outputs.keys())
        for folder, pattern in [(DIST_DIR, "*.conf"), (RULES_DIR / "services", "*.list")]:
            for existing in folder.glob(pattern):
                if existing not in expected_paths:
                    existing.unlink()
        for path in sorted(outputs):
            if path.parent == DIST_DIR:
                print(
                    f"Built {path.relative_to(ROOT)}: {len(outputs[path].encode('utf-8')):,} bytes"
                )
        print(f"Built {len(outputs)} total artifacts in rules/ and dist/.")


if __name__ == "__main__":
    main()
