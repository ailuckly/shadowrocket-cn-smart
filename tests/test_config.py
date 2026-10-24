"""Static policy regressions, not an emulator or native Shadowrocket validation."""
import importlib.util
import ipaddress
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", ROOT / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path, cls.content = build.render()
        cls.sections = {}
        current = None
        for line in cls.content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("["):
                if line in cls.sections:
                    raise AssertionError(f"Repeated section: {line}")
                current = line
                cls.sections[current] = []
            else:
                cls.sections[current].append(line)
        cls.rules = [line.split(",") for line in cls.sections["[Rule]"]]
        cls.general = dict(line.split(" = ", 1) for line in cls.sections["[General]"])

    def route_domain(self, domain):
        # Model only first-match domain rules; never infer DNS, SNI or GeoIP results.
        for rule in self.rules:
            kind = rule[0]
            if kind == "FINAL":
                return rule[1]
            if kind == "DOMAIN" and domain == rule[1]:
                return rule[2]
            if kind == "DOMAIN-SUFFIX" and (domain == rule[1] or domain.endswith("." + rule[1])):
                return rule[2]
        self.fail(f"No final policy for {domain}")

    def test_generated_file_is_reproducible(self):
        self.assertEqual(self.path.read_bytes(), self.content.encode("utf-8"))
        self.assertIn(self.path.name, (ROOT / "README.md").read_text())

    def test_no_unsupported_sections_or_remote_dependencies(self):
        self.assertEqual(set(self.sections), {"[General]", "[Rule]", "[Host]"})
        self.assertEqual(self.rules[-1], ["FINAL", "PROXY"])
        self.assertEqual(sum(rule[0] == "FINAL" for rule in self.rules), 1)
        allowed = {"DOMAIN", "DOMAIN-SUFFIX", "IP-CIDR", "IP-CIDR6", "GEOIP", "FINAL"}
        for rule in self.rules:
            self.assertIn(rule[0], allowed)
            self.assertIn(rule[-1] if rule[0] == "FINAL" else rule[2], {"DIRECT", "PROXY"})
            if rule[0] in {"IP-CIDR", "IP-CIDR6", "GEOIP"}:
                self.assertEqual(rule[-1], "no-resolve")
        self.assertNotRegex(self.content, r"(?i)(password|privatekey|private-key|token)\s*=")
        self.assertNotIn("stun-response-ip", self.general)
        self.assertNotIn("[Proxy Group]", self.sections)
        domain_targets = [r[1] for r in self.rules if r[0] in {"DOMAIN", "DOMAIN-SUFFIX"}]
        self.assertEqual(len(domain_targets), len(set(domain_targets)))
        for rule in self.rules:
            if rule[0] == "DOMAIN-SUFFIX" and rule[2] == "DIRECT":
                self.assertTrue("." in rule[1] or rule[1] in {"local", "lan"})

    def test_overseas_services(self):
        domains = """
        chatgpt.com auth.openai.com api.openai.com cdn.oaistatic.com files.oaiusercontent.com
        claude.ai claude.com api.anthropic.com gemini.google.com accounts.google.com
        aistudio.google.com ai.google.dev generativelanguage.googleapis.com www.google.cn
        www.gstatic.com lh3.googleusercontent.com grok.com api.x.ai www.perplexity.ai
        poe.com cursor.com api2.cursor.sh api.githubcopilot.com copilot.microsoft.com
        login.microsoftonline.com login.live.com www.bing.com github.com
        raw.githubusercontent.com github.githubassets.com registry.npmjs.org pypi.org
        docker.com www.youtube.com rr1.googlevideo.com api.telegram.org t.me
        www.netflix.com www.disneyplus.com open.spotify.com www.tiktok.com
        x.com www.instagram.com www.facebook.com www.reddit.com www.wikipedia.org
        www.apple.com appleid.apple.com www.icloud.com configuration.apple.com
        apple-relay.apple.com windowsupdate.com www.microsoft.com
        www.adobe.com zoom.us www.amazon.com api.stripe.com www.paypal.com
        dns.google cloudflare-dns.com browserleaks.com dnsleaktest.com ipleak.net
        """.split()
        for domain in domains:
            with self.subTest(domain=domain):
                self.assertEqual(self.route_domain(domain), "PROXY")

    def test_domestic_services(self):
        domains = """
        www.baidu.com www.taobao.com login.taobao.com www.alipay.com img.alicdn.com
        www.jd.com img.360buyimg.com www.qq.com wx.qq.com www.weixin.qq.com
        www.bilibili.com api.bilibili.com www.douyin.com www.zhihu.com
        www.xiaohongshu.com www.meituan.com www.12306.cn www.ctrip.com
        www.icbc.com.cn www.ccb.com www.cmbchina.com www.abchina.com
        www.gov.cn www.chinamobile.com www.10010.com www.163.com music.163.com
        www.amap.com www.mi.com www.huawei.com www.aliyun.com www.gitee.com
        chat.deepseek.com www.doubao.com www.kimi.com kimi.moonshot.cn
        dns.alidns.com doh.pub captive.apple.com www.msftconnecttest.com
        """.split()
        for domain in domains:
            with self.subTest(domain=domain):
                self.assertEqual(self.route_domain(domain), "DIRECT")

    def test_unknown_and_suffix_boundaries(self):
        for domain in ["unlisted.example", "ssh.unlisted.example", "unlisted.example.cn",
                       "baidu.com.example", "notqq.com", "qq.com.example", "unlisted.ms"]:
            with self.subTest(domain=domain):
                self.assertEqual(self.route_domain(domain), "PROXY")

    def test_lan_and_ip_rules(self):
        for domain in ["localhost", "printer.local", "router.lan", "nas.home.arpa"]:
            self.assertEqual(self.route_domain(domain), "DIRECT")
        networks = [(ipaddress.ip_network(r[1]), r[2]) for r in self.rules
                    if r[0] in {"IP-CIDR", "IP-CIDR6"}]
        excluded = [ipaddress.ip_network(s) for s in self.general["tun-excluded-routes"].split(",")]
        for value in ["192.168.1.1", "192.168.255.254", "10.0.0.1", "172.16.0.1",
                      "172.31.255.254", "127.0.0.1", "169.254.1.2", "::1", "fd00::1", "fe80::1"]:
            ip = ipaddress.ip_address(value)
            self.assertEqual(next(policy for net, policy in networks if ip in net), "DIRECT")
            self.assertTrue(any(ip in net for net in excluded))
        for value in ["198.18.0.1", "100.64.0.1", "8.8.8.8", "203.0.113.1", "172.32.0.1"]:
            ip = ipaddress.ip_address(value)
            self.assertFalse(any(ip in net for net in excluded), value)
        self.assertEqual(self.rules[-2], ["GEOIP", "CN", "DIRECT", "no-resolve"])

    def test_dns_and_no_udp_direct_fallback(self):
        for key in ["dns-server", "fallback-dns-server"]:
            for endpoint in self.general[key].split(","):
                self.assertTrue(endpoint.startswith("https://"))
                self.assertTrue(endpoint.endswith("#proxy"))
        for key in ["direct-dns-server", "proxy-dns-server"]:
            self.assertTrue(all(url.startswith("https://") for url in self.general[key].split(",")))
        self.assertEqual(self.general["dns-direct-fallback-proxy"], "false")
        self.assertEqual(self.general["dns-direct-system"], "false")
        self.assertEqual(self.general["udp-policy-not-supported-behaviour"], "REJECT")
        self.assertEqual(self.general["bypass-system"], "false")

    def test_source_conversion_rejects_unknown_formats(self):
        self.assertEqual(build.domain_rule("+.example.com", "DIRECT"), "DOMAIN-SUFFIX,example.com,DIRECT")
        self.assertEqual(build.domain_rule("example.com", "PROXY"), "DOMAIN,example.com,PROXY")
        for invalid in ["", "*.example.com", "+.a..com", "https://example.com", "example.com,REJECT",
                        "example.com\nFINAL,DIRECT", "-example.com", "A.example.com", "a" * 64 + ".com"]:
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                build.domain_rule(invalid, "DIRECT")
        with self.assertRaises(ValueError):
            build.domain_rule("example.com", "REJECT")


if __name__ == "__main__":
    unittest.main()
