<div align="center">

# Shadowrocket CN Smart

**为中国大陆设计的 Shadowrocket 分流配置**<br>
<sub>A precise, leak-resistant Shadowrocket profile for mainland China</sub>

[![Check](https://github.com/ailuckly/shadowrocket-cn-smart/actions/workflows/check.yml/badge.svg)](https://github.com/ailuckly/shadowrocket-cn-smart/actions/workflows/check.yml)
[![Release](https://img.shields.io/badge/release-v2.0.0-1f6feb?style=flat-square)](https://github.com/ailuckly/shadowrocket-cn-smart/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0-555?style=flat-square)](LICENSE)

[简体中文](#简体中文) · [English](#english)

</div>

---

## 简体中文

国内流量直连，境外流量代理，DNS 全程加密。规则由上游社区数据清洗后自动构建，四个版本共用同一套规则，并经离线回归测试验证分流结果一致。

### 特性

- **精细分流**：中国区 iCloud、App Store 下载、Apple Pay、地图、世纪互联与 Azure 中国、Windows 更新、Steam 下载直连；全球 Apple、Microsoft、Google 与 AI 服务走代理。
- **DNS 防泄露**：默认 DoH 经代理发出，国内域名使用国内 DoH，节点域名单独引导解析；劫持 53 端口，代理流量禁用 QUIC。
- **数据清洗**：自动剔除上游混入国内列表的查 IP 站、海外版应用与 PT 站；规则冲突在构建时报错。
- **两种形态**：离线版单文件内置 3.3 万条规则；在线版内联不到 200 条，大表通过 `DOMAIN-SET` 加载，内存占用更低。
- **模块解耦**：去广告、HttpDNS 拦截与企业 VPN 共存均为独立模块，主配置无需安装证书。

### 版本

| 版本 | 体积 | 说明 | 链接 |
| --- | --- | --- | --- |
| 在线版 · 推荐 | 10 KB | 低内存，规则随仓库更新 | [Online](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/dist/Shadowrocket-CN-Smart-Online.conf) |
| 在线策略组版 | 16 KB | 另含 26 个策略组，可为 AI、流媒体等单独选节点 | [Group-Online](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/dist/Shadowrocket-CN-Smart-Group-Online.conf) |
| 离线版 | 1.15 MB | 规则全部内置，无远程依赖 | [Offline](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/dist/Shadowrocket-CN-Smart-Offline.conf) |
| 离线策略组版 | 1.15 MB | 离线 + 26 个策略组 | [Group-Offline](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/dist/Shadowrocket-CN-Smart-Group-Offline.conf) |

文件名依次为 `Shadowrocket-CN-Smart-Online.conf`、`Shadowrocket-CN-Smart-Group-Online.conf`、`Shadowrocket-CN-Smart-Offline.conf`、`Shadowrocket-CN-Smart-Group-Offline.conf`。策略组版刚导入时，除哔哩哔哩默认直连外，其余分组都跟随首页节点。

### 快速开始

1. 复制上表中的链接，在 Shadowrocket **配置 → `+`** 中粘贴下载，点击该配置选择 **使用配置**。
2. 回到首页选择节点，将 **全局路由** 设为 **配置**（即配置模式，不要选代理或直连）。
3. 在设置中开启 **禁用 STUN**，然后连接。

完整图文步骤见 [导入指南](docs/README.md)。本项目不提供任何节点、订阅或证书。

### 分流顺序

```text
0  本机私有规则（可选 Overlay）
1  局域网与保留地址                       → DIRECT
2  中国区 Apple / 微软 / Steam 下载等例外  → DIRECT
3  AI、Google、GitHub 等核心境外服务       → PROXY 或对应策略组
4  境外域名表（含全球 Apple / 微软）       → PROXY
5  国内域名表与 .cn                        → DIRECT
6  其余域名经代理 DoH 解析后 GEOIP,CN      → DIRECT
7  FINAL                                   → PROXY
```

### 模块

在 **配置 → 模块 → `+`** 中按需添加：

| 模块 | 证书 | 用途 |
| --- | --- | --- |
| [`adblock-dns`](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/modules/adblock-dns.module) | 不需要 | 域名级拦截广告联盟、移动广告 SDK 与追踪域名 |
| [`adblock-mitm`](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/modules/adblock-mitm.module) | 需要本机自签 | 改写 B站、知乎、微博的开屏广告接口，见[说明](docs/modules.md) |
| [`block-httpdns`](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/modules/block-httpdns.module) | 不需要 | 拦截常见 HttpDNS，让 App 回到标准 DNS |
| [`corporate-vpn-template`](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/modules/corporate-vpn-template.module) | 不需要 | macOS 上与企业 VPN 共存的模板，见[指南](docs/corporate-vpn.md) |

### 已知限制

- 未收录的域名由 `GEOIP,CN` 兜底。境外 DoH 按节点位置返回结果，同时有海外 CDN 的国内网站可能走代理，欢迎提 Issue 补充。
- 需要网页认证的公共 Wi-Fi 可能无法弹出认证页，先暂停 Shadowrocket 完成认证即可。
- iOS 同一时间只允许一个 VPN，开启企业 VPN 会断开 Shadowrocket。
- 在线版规则托管于本仓库 `main` 分支；上游每周自动同步并生成 PR，审核合并后在 App 内刷新即可更新。
- Release 中的 `Shadowrocket-CN-Smart.conf` 与离线版内容一致，供 v1.x 旧链接继续更新。

### 开发

需要 Python 3.9+，无第三方依赖。

```sh
python3 scripts/build.py                     # 由 config/ 与 data/ 生成 rules/ 与 dist/
python3 scripts/build.py --check             # 校验生成文件是否最新
python3 -m unittest discover -s tests        # 离线回归测试
python3 scripts/sync_upstream.py             # 同步上游快照（CI 每周一执行）
python3 scripts/build.py --profile host-conf/profile.json   # 生成本机私有配置
```

`host-conf/` 已被 Git 忽略，用于存放公司 VPN、内网域名等私有信息。提交 Issue 或截图时请隐去节点、订阅与内网地址。

---

## English

Domestic traffic goes direct, everything else goes through your proxy, and DNS stays encrypted end to end. Rules are built automatically from cleaned community data; all four editions share one rule base and are verified by offline regression tests to route identically.

### Features

- **Precise routing**: China-region iCloud, App Store downloads, Apple Pay, Maps, 21Vianet / Azure China, Windows Update and Steam downloads go direct; global Apple, Microsoft, Google and AI services go through the proxy.
- **DNS leak protection**: default DoH is sent through the proxy, domestic domains use domestic DoH, and node hostnames have a separate bootstrap resolver; port 53 is hijacked and QUIC is blocked for proxied traffic.
- **Cleaned data**: IP-check sites, overseas app variants and private trackers wrongly listed as Chinese upstream are removed; rule conflicts fail the build.
- **Two forms**: offline editions embed 33k+ rules in one file; online editions inline fewer than 200 rules and load large lists via `DOMAIN-SET` for a smaller memory footprint.
- **Decoupled modules**: ad blocking, HttpDNS blocking and corporate VPN coexistence are separate modules; the main profile needs no certificate.

### Editions

| Edition | Size | Notes |
| --- | --- | --- |
| [Online](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/dist/Shadowrocket-CN-Smart-Online.conf) · recommended | 10 KB | Low memory, rules update with the repository |
| [Group-Online](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/dist/Shadowrocket-CN-Smart-Group-Online.conf) | 16 KB | Adds 26 policy groups for per-service node selection |
| [Offline](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/dist/Shadowrocket-CN-Smart-Offline.conf) | 1.15 MB | All rules embedded, no remote dependencies |
| [Group-Offline](https://raw.githubusercontent.com/ailuckly/shadowrocket-cn-smart/main/dist/Shadowrocket-CN-Smart-Group-Offline.conf) | 1.15 MB | Offline plus 26 policy groups |

### Quick start

1. Copy a link above, paste it in Shadowrocket under **Config → `+`**, then select **Use Config**.
2. Pick a node on the home screen and set **Global Routing** to **Config**.
3. Enable **Disable STUN** in settings, then connect.

This project ships routing rules and modules only. It contains no nodes, subscriptions, keys or certificates.

### Known limitations

- Unlisted domains fall back to `GEOIP,CN`. Because DoH answers reflect the node's location, Chinese sites that also have overseas CDNs may be proxied. Issues are welcome.
- Captive-portal Wi-Fi may not show its login page; pause Shadowrocket, sign in, then reconnect.
- iOS allows only one active VPN, so a corporate VPN will disconnect Shadowrocket.

### Development

Python 3.9+, no third-party dependencies.

```sh
python3 scripts/build.py && python3 scripts/build.py --check
python3 -m unittest discover -s tests
```

---

## 规则来源与许可 · Sources & License

| 来源 Source | 用途 Usage | 许可 License |
| --- | --- | --- |
| [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) | 国内、境外、Apple、Microsoft 域名快照 | GPL-3.0 |
| [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) | 经 MetaCubeX geo-lite 引用 | [GPL-2.0](data/LICENSES/blackmatrix7-GPL-2.0.txt) |
| [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) | 上游域名分类 | [MIT](data/LICENSES/v2fly-MIT.txt) |

项目自身的模板、模块、脚本与文档以 [GPL-3.0](LICENSE) 发布，上游数据保留原始署名与许可。本项目与 Shadowrocket 官方无关。<br>
<sub>Original templates, modules, scripts and docs are released under GPL-3.0; upstream data keeps its original attribution and license. Not affiliated with Shadowrocket.</sub>
