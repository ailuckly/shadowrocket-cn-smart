<div align="center">

# 🚀 Shadowrocket CN Smart

**国内直连 · 境外代理 · 一个文件，轻松导入**

[![检查](https://github.com/ailuckly/shadowrocket-cn-smart/actions/workflows/check.yml/badge.svg)](https://github.com/ailuckly/shadowrocket-cn-smart/actions/workflows/check.yml)
[![版本](https://img.shields.io/badge/version-1.0.0--beta.2-orange?style=flat-square)](https://github.com/ailuckly/shadowrocket-cn-smart/releases/tag/v1.0.0-beta.2)
![模式](https://img.shields.io/badge/Shadowrocket-配置模式-2684FF?style=flat-square)
[![许可证](https://img.shields.io/badge/license-GPL--3.0-blue?style=flat-square)](LICENSE)

### [⬇ 下载配置文件](https://github.com/ailuckly/shadowrocket-cn-smart/releases/download/v1.0.0-beta.2/Shadowrocket-CN-Smart-v1.0.0-beta.2.conf)

[查看配置](Shadowrocket-CN-Smart-v1.0.0-beta.2.conf) · [版本记录](https://github.com/ailuckly/shadowrocket-cn-smart/releases) · [反馈问题](https://github.com/ailuckly/shadowrocket-cn-smart/issues)

</div>

面向中国大陆日常使用的 **Shadowrocket 分流配置**。规则已内置，下载一个 `.conf` 即可导入，无需运行脚本、安装证书或另外下载规则集。

> **生效条件：在 Shadowrocket 中启用本文件，并将「首页 → 全局路由」设为「配置」。** 本文描述的分流策略用于**配置模式**，不是全局代理模式。
>
> 本项目不提供节点。请先在首页添加并选中自己的可用节点；Shadowsocks 等节点仍由 Shadowrocket 首页管理，本文件不包含服务器账号或密码。

## ✨ 三步开始

1. **下载**：点击上方按钮，保存 `.conf` 文件。
2. **导入**：在 Shadowrocket 的「配置」页导入并启用该文件。
3. **连接**：首页选择可用节点，将全局路由设为 **配置**，开启连接。

更新时下载新版本并重新导入即可。普通用户只需要根目录中的一个 `.conf`，无需下载整个仓库。

## 🧭 它会怎样分流？

| 流量 | 策略 |
| --- | --- |
| 已收录的国内网站、支付、社交、视频及国内 AI 服务 | 🟢 直连 |
| 局域网设备与本地域名 | 🟢 直连 |
| 已收录的境外 AI、Google、开发平台和境外服务 | 🔵 使用首页节点 |
| Apple、Microsoft 的已收录服务域名 | 🔵 使用首页节点，少数联网检测域名除外 |
| 未命中更早规则的已有 CN 目标 IP | 🟢 按客户端 GeoIP 数据库直连 |
| 其余未匹配流量 | 🔵 使用首页节点 |

规则按顺序匹配：**本地网络 → 必要基础服务 → 境外域名 → 国内域名 → CN IP → 代理兜底**。不自动更换节点或出口地区；修改首页节点即可统一切换代理出口。

## 🛠 默认配置有哪些优点？本项目补充了什么？

Shadowrocket 默认配置提供常用域名分流、局域网旁路和兜底策略。本项目沿用这些基础，按国内直连、境外服务代理的目标补充规则。

| 默认配置的基础能力 | 本项目的保留或补充 |
| --- | --- |
| 常用域名规则、CN GeoIP 与最终代理兜底 | 保留分层结构，扩充国内/境外域名覆盖；GeoIP 使用 `no-resolve`，不为匹配它额外解析未知域名 |
| 局域网旁路与私有 IP 直连 | 保留本地通信能力，补充本地域名和地址范围 |
| Apple Intelligence、Copilot 等专用代理规则 | 扩充境外 AI、登录及开发服务，统一跟随首页节点 |
| 节点不支持 UDP 时拒绝转发 | 保留，不设置代理 UDP 自动直连回退 |
| 系统 DNS 与 IPv6 支持，方便适配系统环境 | 本项目改为分离的代理/直连 DoH，默认面向具备 IPv4 连接的网络 |

以上对照以 **Shadowrocket 2.2.92 随应用提供的 `default.conf`** 为基准，其他版本可能不同。本项目不是官方配置：它将已收录的 Apple、Microsoft 服务优先代理，会比偏向这些服务直连的配置消耗更多节点流量。

### 本项目额外提供

- **单文件离线规则**：约 1.2 MB，导入后不依赖远程规则下载；更新随新版本发布。
- **分离 DNS**：默认/备用 DoH 经首页节点，国内直连与节点引导使用国内 DoH，本地域名交给系统处理。
- **可复现版本**：固定规则来源、校验快照并检查生成结果；每次发布使用独立文件名。
- **轻量使用方式**：没有复杂策略组、重写脚本或 HTTPS 解密设置，只做分流。

## 🤝 规则来源与致谢

| 来源 | 本项目使用的内容 |
| --- | --- |
| [Shadowrocket](https://apps.apple.com/us/app/shadowrocket/id932747118) | 参考随应用提供的默认配置结构与基础策略 |
| [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) | 当前直接采用的国内、境外、Apple 和 Microsoft 域名快照 |
| [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) | 经 MetaCubeX 的 geo-lite 集合引用的国内基础规则来源 |
| [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community)、[Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) | 上游域名分类与数据生态 |

域名数据由上游社区维护；本项目负责策略编排、必要域名补充、格式转换、去重与验证。详细来源、许可与构建方法统一放在 [维护目录](.maintainer/README.md)，不影响直接下载使用。

## 📌 使用范围

当前为 **beta 测试版**，已提供静态检查，尚未完成不同设备、客户端版本及运营商的全面实测。默认面向具备 IPv4 连接的网络；IPv6-only 网络需要另行适配。

域名规则和 GeoIP 不能完全识别每个应用的所有连接，共享 CDN 或应用自带 DNS 可能影响分流。配置不等于匿名或系统级断网保护，也不保证服务的地区可用性。请使用有权使用的节点并遵守适用要求。

反馈时提供配置版本、目标域名及预期策略即可，**请勿公开节点密码、订阅链接或完整访问日志**。

---

<div align="center">

如果这个配置对你有帮助，欢迎点亮 ⭐，也欢迎提交规则修正。

本项目原创部分使用 [GPL-3.0](LICENSE)；第三方数据保留其来源与许可。与 Shadowrocket 官方无隶属关系。

</div>
