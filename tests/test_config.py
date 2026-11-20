"""Comprehensive offline regression tests for Shadowrocket CN Smart v2.0."""
from __future__ import annotations

import importlib.util
import ipaddress
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", ROOT / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def parse_conf(text: str):
    sections: dict[str, list[str]] = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            if line in sections:
                raise AssertionError(f"Repeated section: {line}")
            current = line
            sections[current] = []
        else:
            sections[current].append(line)
    return sections


def expand_rules_locally(rule_lines: list[str], repo: str, branch: str):
    """Expand inline rules + local DOMAIN-SET / RULE-SET files into a flat matcher list."""
    raw_prefix = f"https://raw.githubusercontent.com/{repo}/{branch}/"
    expanded = []
    for line in rule_lines:
        parts = line.split(",")
        kind = parts[0]
        if kind == "DOMAIN-SET":
            url, policy = parts[1], parts[2]
            if not url.startswith(raw_prefix):
                raise AssertionError(f"Unexpected remote DOMAIN-SET URL: {url}")
            local_path = ROOT / url.removeprefix(raw_prefix)
            if not local_path.exists():
                raise AssertionError(f"Missing local DOMAIN-SET file: {local_path}")
            for entry in local_path.read_text(encoding="utf-8").splitlines():
                s = entry.strip()
                if not s or s.startswith("#"):
                    continue
                if s.startswith("."):
                    expanded.append(["DOMAIN-SUFFIX", s[1:], policy])
                else:
                    expanded.append(["DOMAIN", s, policy])
        elif kind == "RULE-SET":
            url, policy = parts[1], parts[2]
            if not url.startswith(raw_prefix):
                raise AssertionError(f"Unexpected remote RULE-SET URL: {url}")
            local_path = ROOT / url.removeprefix(raw_prefix)
            if not local_path.exists():
                raise AssertionError(f"Missing local RULE-SET file: {local_path}")
            for entry in local_path.read_text(encoding="utf-8").splitlines():
                s = entry.strip()
                if not s or s.startswith("#"):
                    continue
                ep = s.split(",")
                if ep[0] in {"IP-CIDR", "IP-CIDR6"} and ep[-1] == "no-resolve":
                    expanded.append([ep[0], ep[1], policy, "no-resolve"])
                else:
                    expanded.append([ep[0], ep[1], policy])
        else:
            expanded.append(parts)
    return expanded


def route_domain(expanded_rules: list[list[str]], domain: str) -> str:
    for rule in expanded_rules:
        kind = rule[0]
        if kind == "FINAL":
            return rule[1]
        if kind == "DOMAIN" and domain == rule[1]:
            return rule[2]
        if kind == "DOMAIN-SUFFIX" and (
            domain == rule[1] or domain.endswith("." + rule[1])
        ):
            return rule[2]
    raise AssertionError(f"No final policy for {domain}")


def route_ip(expanded_rules: list[list[str]], ip_str: str) -> str:
    ip = ipaddress.ip_address(ip_str)
    for rule in expanded_rules:
        kind = rule[0]
        if kind == "FINAL":
            return rule[1]
        if kind in {"IP-CIDR", "IP-CIDR6"} and ip in ipaddress.ip_network(rule[1]):
            return rule[2]
    return "UNMATCHED"


class ConfigV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
        cls.repo = cls.manifest["project_repo"]
        cls.branch = cls.manifest["project_branch"]
        cls.outputs = build.render_all()

        cls.configs = {}
        cls.sections = {}
        cls.expanded = {}
        for name in [
            "Shadowrocket-CN-Smart-Offline.conf",
            "Shadowrocket-CN-Smart-Group-Offline.conf",
            "Shadowrocket-CN-Smart-Online.conf",
            "Shadowrocket-CN-Smart-Group-Online.conf",
        ]:
            text = cls.outputs[ROOT / "dist" / name]
            cls.configs[name] = text
            secs = parse_conf(text)
            cls.sections[name] = secs
            cls.expanded[name] = expand_rules_locally(
                secs["[Rule]"], cls.repo, cls.branch
            )

    def test_all_generated_artifacts_are_reproducible(self):
        for path, content in self.outputs.items():
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists(), f"Missing {path}")
                self.assertEqual(path.read_bytes(), content.encode("utf-8"))
        # No stray root .conf files
        self.assertEqual(list(ROOT.glob("*.conf")), [])

    def test_docs_and_no_private_paths(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("全局路由", readme)
        self.assertIn("配置模式", readme)
        self.assertIn("Shadowrocket-CN-Smart-Offline.conf", readme)
        self.assertIn("Shadowrocket-CN-Smart-Online.conf", readme)
        self.assertIn("Shadowrocket-CN-Smart-Group-Offline.conf", readme)
        self.assertIn("Shadowrocket-CN-Smart-Group-Online.conf", readme)
        for doc in [
            "README.md",
            "README.en.md",
            "docs/README.md",
            "docs/modules.md",
            "docs/corporate-vpn.md",
            "docs/index.html",
        ]:
            text = (ROOT / doc).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?:/Users/|/home/)[^\s/]+/", doc)

    def test_offline_has_no_remote_dependencies_and_online_bootstraps_github(self):
        for name in [
            "Shadowrocket-CN-Smart-Offline.conf",
            "Shadowrocket-CN-Smart-Group-Offline.conf",
        ]:
            rules = self.sections[name]["[Rule]"]
            for line in rules:
                self.assertFalse(line.startswith(("RULE-SET,", "DOMAIN-SET,")), line)

        for name in [
            "Shadowrocket-CN-Smart-Online.conf",
            "Shadowrocket-CN-Smart-Group-Online.conf",
        ]:
            rules = self.sections[name]["[Rule]"]
            gh_idx = next(
                i for i, l in enumerate(rules) if l == "DOMAIN-SUFFIX,githubusercontent.com,PROXY"
            )
            first_remote = next(
                i for i, l in enumerate(rules) if l.startswith(("RULE-SET,", "DOMAIN-SET,"))
            )
            self.assertLess(
                gh_idx,
                first_remote,
                f"{name}: githubusercontent.com must appear before remote rulesets",
            )
            # Online configs stay compact for low iOS memory footprint
            self.assertLess(len(rules), 200, name)

    def test_security_and_structure_across_all_editions(self):
        for name, text in self.configs.items():
            with self.subTest(config=name):
                self.assertNotRegex(
                    text,
                    r"(?i)(password|privatekey|private-key|token|ca-p12|ca-passphrase)\s*=",
                )
                secs = self.sections[name]
                expected_secs = {"[General]", "[Rule]", "[Host]"}
                if "Group" in name:
                    expected_secs.add("[Proxy Group]")
                self.assertEqual(set(secs), expected_secs)

                general = dict(line.split(" = ", 1) for line in secs["[General]"])
                self.assertEqual(general["bypass-system"], "false")
                self.assertEqual(general["dns-direct-system"], "false")
                self.assertEqual(general["dns-direct-fallback-proxy"], "false")
                self.assertEqual(general["dns-fallback-system"], "false")
                self.assertEqual(general["hijack-dns"], ":53")
                self.assertEqual(general["udp-policy-not-supported-behaviour"], "REJECT")
                self.assertEqual(general["block-quic"], "all-proxy")
                self.assertEqual(general["proxy-dns-server"], "223.5.5.5,119.29.29.29")
                for key in ["dns-server", "fallback-dns-server"]:
                    for ep in general[key].split(","):
                        self.assertTrue(ep.startswith("https://"), ep)
                        self.assertIn("#proxy", ep)
                        self.assertIn("no-h3", ep)
                skip = general["skip-proxy"].split(",")
                self.assertIn("100.64.0.0/10", skip)
                self.assertIn("captive.apple.com", skip)

                expanded = self.expanded[name]
                self.assertEqual(expanded[-2], ["GEOIP", "CN", "DIRECT"])
                self.assertEqual(expanded[-1], ["FINAL", "PROXY"])
                for r in expanded:
                    if r[0] in {"IP-CIDR", "IP-CIDR6"}:
                        self.assertEqual(r[-1], "no-resolve", r)

    def test_proxy_group_integrity(self):
        for name in [
            "Shadowrocket-CN-Smart-Group-Offline.conf",
            "Shadowrocket-CN-Smart-Group-Online.conf",
        ]:
            secs = self.sections[name]
            groups = {l.split(" = ", 1)[0] for l in secs["[Proxy Group]"]}
            valid = groups | {"DIRECT", "PROXY", "REJECT"}
            for line in secs["[Proxy Group]"]:
                gname, rhs = line.split(" = ", 1)
                parts = rhs.split(",")
                if parts[0] == "select":
                    for item in parts[1:]:
                        if item.startswith("policy-select-name="):
                            self.assertIn(item.split("=", 1)[1], valid, gname)
                        else:
                            self.assertIn(item, valid, gname)
            for r in self.expanded[name]:
                pol = r[1] if r[0] == "FINAL" else r[2]
                self.assertIn(pol, valid, r)

    def test_lite_offline_and_online_routing_equivalence(self):
        samples = """
        chatgpt.com api.openai.com claude.ai gemini.google.com aistudio.google.com
        www.google.com www.google.cn gstatic.cn googleapis.cn github.com
        raw.githubusercontent.com www.youtube.com api.telegram.org www.netflix.com
        www.apple.com www.icloud.com mesu.apple.com www.microsoft.com www.bing.com.cn
        browserleaks.com dnsleaktest.com whatismyip.com bilibili.tv biliintl.com
        byteintl.net example.in.th m-team.cc empornium.me hdbits.org worldbank.org
        imf.org weather.com tawk.to api.crisp.chat origin-a.akamaihd.ne
        www.baidu.com www.taobao.com www.alipay.com www.jd.com weixin.qq.com
        www.bilibili.com www.douyin.com www.zhihu.com www.xiaohongshu.com
        www.dewu.com www.poizon.com www.volcengine.com www.larkoffice.com
        www.stepfun.com www.xpeng.com www.xiaomiev.com www.hypergryph.com
        www.kurogame.com www.steamchina.com dl.steam.clngaa.com
        courier.push.apple.com time.apple.com ocsp.apple.com
        www.icloud.com.cn p100.icloud-content.com.cn www.apple.com.cn
        iosapps.itunes.apple.com osxapps.itunes.apple.com
        amp-api-edge-lb-cn.itunes-apple.com.akadns.net
        is-ssl.mzstatic.com-cn-lb.itunes-apple.com.akadns.net
        appldnld.apple.com updates-http.cdn-apple.com mesu-china.apple.com.akadns.net
        cn-smp-paymentservices.apple.com cdn-cn.apple-mapkit.com gs-loc-cn.apple.com
        gsp4-cn.ls.apple.com gspe19-cn-ssl.ls.apple.com
        portal.azure.cn app.chinacloudapp.cn demo.chinacloudsites.cn registry.azurecr.cn
        login.b2clogin.cn login.msauth.cn files.o365files.cn app.powerbi.cn
        download.microsoft.com update.microsoft.com images-cn.ssl-images-amazon.com
        dns.alidns.com doh.pub sm2.doh.pub dot.pub captive.apple.com
        unlisted.example.cn unlisted.example aka.ms
        """.split()

        off = self.expanded["Shadowrocket-CN-Smart-Offline.conf"]
        on = self.expanded["Shadowrocket-CN-Smart-Online.conf"]
        goff = self.expanded["Shadowrocket-CN-Smart-Group-Offline.conf"]
        gon = self.expanded["Shadowrocket-CN-Smart-Group-Online.conf"]

        for d in samples:
            with self.subTest(domain=d):
                self.assertEqual(route_domain(off, d), route_domain(on, d))
                self.assertEqual(route_domain(goff, d), route_domain(gon, d))

    def test_lite_routing_accuracy(self):
        off = self.expanded["Shadowrocket-CN-Smart-Offline.conf"]
        must_proxy = """
        chatgpt.com claude.ai gemini.google.com www.google.com www.google.cn
        gstatic.cn googleapis.cn github.com www.youtube.com www.netflix.com
        www.apple.com www.icloud.com mesu.apple.com www.microsoft.com www.bing.com.cn
        whatismyip.com bilibili.tv biliintl.com byteintl.net example.in.th
        m-team.cc empornium.me hdbits.org worldbank.org imf.org weather.com
        tawk.to api.crisp.chat origin-a.akamaihd.ne unlisted.example aka.ms
        """.split()
        must_direct = """
        www.baidu.com www.taobao.com www.alipay.com weixin.qq.com www.bilibili.com
        www.dewu.com www.volcengine.com www.larkoffice.com www.xpeng.com www.xiaomiev.com
        www.hypergryph.com www.kurogame.com www.steamchina.com dl.steam.clngaa.com
        courier.push.apple.com www.icloud.com.cn p100.icloud-content.com.cn
        download.windowsupdate.com au.download.windowsupdate.com officecdn.microsoft.com
        lancache.steamcontent.com
        iosapps.itunes.apple.com osxapps.itunes.apple.com cn-smp-paymentservices.apple.com
        cdn-cn.apple-mapkit.com gs-loc-cn.apple.com mesu-china.apple.com.akadns.net
        portal.azure.cn app.chinacloudapp.cn registry.azurecr.cn login.msauth.cn
        download.microsoft.com update.microsoft.com images-cn.ssl-images-amazon.com
        dns.alidns.com doh.pub sm2.doh.pub dot.pub captive.apple.com unlisted.example.cn
        """.split()
        for d in must_proxy:
            with self.subTest(proxy=d):
                self.assertEqual(route_domain(off, d), "PROXY")
        for d in must_direct:
            with self.subTest(direct=d):
                self.assertEqual(route_domain(off, d), "DIRECT")

    def test_group_routing_accuracy(self):
        goff = self.expanded["Shadowrocket-CN-Smart-Group-Offline.conf"]
        expected = {
            "gemini.google.com": "Gemini",
            "aistudio.google.com": "Gemini",
            "generativelanguage.googleapis.com": "Gemini",
            "chatgpt.com": "AI",
            "claude.ai": "AI",
            "grok.com": "AI",
            "copilot.microsoft.com": "AI",
            "apple-relay.apple.com": "AI",
            "www.youtube.com": "YouTube",
            "rr1.googlevideo.com": "YouTube",
            "www.netflix.com": "Netflix",
            "www.disneyplus.com": "Disney+",
            "www.max.com": "Max",
            "www.tiktok.com": "TikTok",
            "open.spotify.com": "Spotify",
            "api.telegram.org": "Telegram",
            "x.com": "Twitter",
            "www.instagram.com": "Facebook",
            "www.paypal.com": "PayPal",
            "www.amazon.com": "Amazon",
            "store.steampowered.com": "游戏平台",
            "lancache.steamcontent.com": "DIRECT",
            "download.windowsupdate.com": "DIRECT",
            "www.google.com": "谷歌服务",
            "gstatic.cn": "谷歌服务",
            "www.microsoft.com": "微软服务",
            "www.bing.com.cn": "微软服务",
            "www.apple.com": "苹果服务",
            "www.icloud.com": "苹果服务",
            "www.bilibili.com": "哔哩哔哩",
            "bilibili.tv": "PROXY",
            "biliintl.com": "PROXY",
            "whatismyip.com": "PROXY",
            "github.com": "PROXY",
            "iosapps.itunes.apple.com": "DIRECT",
            "p100.icloud-content.com.cn": "DIRECT",
            "cn-smp-paymentservices.apple.com": "DIRECT",
            "portal.azure.cn": "DIRECT",
            "www.steamchina.com": "DIRECT",
            "www.dewu.com": "DIRECT",
        }
        for d, want in expected.items():
            with self.subTest(domain=d):
                self.assertEqual(route_domain(goff, d), want)
        self.assertEqual(route_ip(goff, "149.154.167.50"), "Telegram")
        self.assertEqual(route_ip(goff, "100.64.0.1"), "DIRECT")

    def test_region_group_regex_avoids_false_matches(self):
        groups = {}
        for line in (ROOT / "config" / "proxy-groups.ini").read_text(encoding="utf-8").splitlines():
            if "policy-regex-filter=" in line:
                name, rhs = line.split(" = ", 1)
                groups[name] = re.compile(rhs.split("policy-regex-filter=", 1)[1])
        cases = {
            "美国节点": (["🇺🇸 US 01", "US01", "USA-LA", "美国 02"], ["RUS 01", "AUS-Sydney", "Plus 03", "俄罗斯"]),
            "香港节点": (["HK01", "香港 IPLC"], ["HKG-Bus", "THK 1"]),
            "新加坡节点": (["SG 01", "新加坡"], ["MSG-02"]),
            "日本节点": (["JP-Tokyo", "日本 01"], ["XJPY"]),
            "台湾节点": (["TW 01", "TWN-2"], ["ATW 1"]),
            "韩国节点": (["KR 01", "KOR-Seoul"], ["SKR"]),
            "Gemini可用": (
                ["US 01", "JP-Tokyo", "SG-IEPL", "Taiwan 01", "KR 01", "🇺🇸 美国 02"],
                ["HK 01", "香港 01", "Hong Kong", "hongkong 2", "US 剩余流量 10G", "RUS 01"],
            ),
        }
        for group, (good, bad) in cases.items():
            for n in good:
                with self.subTest(group=group, node=n):
                    self.assertTrue(groups[group].search(n))
            for n in bad:
                with self.subTest(group=group, node=n):
                    self.assertFalse(groups[group].search(n))

    def test_modules_syntax_and_safety(self):
        modules_dir = ROOT / "modules"
        expected_modules = {
            "adblock-dns.module",
            "adblock-mitm.module",
            "block-httpdns.module",
            "corporate-vpn-template.module",
        }
        found = {p.name for p in modules_dir.glob("*.module")}
        self.assertEqual(found, expected_modules)

        for mod in sorted(modules_dir.glob("*.module")):
            text = mod.read_text(encoding="utf-8")
            with self.subTest(module=mod.name):
                self.assertIn("#!name=", text)
                self.assertIn("#!desc=", text)
                self.assertNotRegex(
                    text, r"(?i)(password|privatekey|private-key|ca-p12|ca-passphrase)\s*="
                )
                if mod.name == "corporate-vpn-template.module":
                    doc_nets = [
                        ipaddress.ip_network("192.0.2.0/24"),
                        ipaddress.ip_network("198.51.100.0/24"),
                        ipaddress.ip_network("203.0.113.0/24"),
                        ipaddress.ip_network("10.0.0.0/8"),
                        ipaddress.ip_network("172.16.0.0/12"),
                        ipaddress.ip_network("192.168.0.0/16"),
                    ]
                    for m in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text):
                        addr = ipaddress.ip_address(m)
                        self.assertTrue(
                            any(addr in n for n in doc_nets),
                            f"Non-documentation IP {m} in template module",
                        )
                if mod.name == "adblock-dns.module":
                    for keep in ["jiguang.cn", "branch.io"]:
                        self.assertNotIn(f",{keep},", text)
                secs = parse_conf(text)
                if "[MITM]" in secs:
                    for line in secs["[MITM]"]:
                        if line.startswith("hostname"):
                            self.assertIn("%APPEND%", line)
                            hosts = [
                                h.strip()
                                for h in line.split("%APPEND%", 1)[1].split(",")
                                if h.strip()
                            ]
                            self.assertNotIn("*", hosts)
                            for h in hosts:
                                self.assertNotRegex(
                                    h, r"(bank|alipay|tenpay|unionpay|icbc|ccb|abchina|boc)"
                                )

    def test_profile_overlay_rendering(self):
        sample_profile = {
            "label": "Test Overlay",
            "output_dir": ".",
            "output_prefix": "Test-Host",
            "with_groups": True,
            "skip_proxy_append": ["intranet.example"],
            "tun_excluded_routes_append": ["203.0.113.10/32"],
            "always_real_ip": ["intranet.example"],
            "general_overrides": {"icmp-auto-reply": "true"},
            "top_rules": [
                "IP-CIDR,203.0.113.10/32,DIRECT,no-resolve",
                "DOMAIN,intranet.example,DIRECT",
            ],
            "hosts": {"intranet.example": "192.168.50.10"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            pfile = Path(tmp) / "profile.json"
            pfile.write_text(json.dumps(sample_profile), encoding="utf-8")
            rendered = build.render_profile(pfile)
            self.assertEqual(len(rendered), 2)
            for out_path, content in rendered.items():
                secs = parse_conf(content)
                general = dict(l.split(" = ", 1) for l in secs["[General]"])
                self.assertIn("203.0.113.10/32", general["tun-excluded-routes"])
                self.assertIn("intranet.example", general["skip-proxy"])
                self.assertEqual(general["always-real-ip"], "intranet.example")
                self.assertEqual(general["icmp-auto-reply"], "true")
                expanded = expand_rules_locally(secs["[Rule]"], self.repo, self.branch)
                self.assertEqual(route_domain(expanded, "intranet.example"), "DIRECT")
                self.assertEqual(route_ip(expanded, "203.0.113.10"), "DIRECT")
                hosts = dict(l.split(" = ", 1) for l in secs["[Host]"])
                self.assertEqual(hosts["intranet.example"], "192.168.50.10")


if __name__ == "__main__":
    unittest.main()
