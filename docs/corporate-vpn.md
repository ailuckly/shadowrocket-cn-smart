# 企业 VPN 共存

[项目首页](../README.md) · [导入指南](README.md) · [模块与证书](modules.md)

适用于 macOS 上同时使用 Shadowrocket 与 EasyConnect、AnyConnect、GlobalProtect、FortiClient 等企业 VPN。iOS 同一时间只允许一个 VPN，无法共存。

## 常见原因

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 企业 VPN 连不上 | VPN 网关流量被 Shadowrocket 接管或送往境外节点 | 网关 IP 加入 `tun-excluded-routes` 并直连 |
| 已连接但内网域名打不开 | 域名得到 `198.18.x.x` 虚拟地址，无法进入企业隧道 | 使用 `always-real-ip` 与 `[Host]` 映射 |
| 内网域名解析失败 | 53 端口被劫持，公网 DNS 查不到私有域名 | 将内网后缀指向公司 DNS |

## 方式一：模块（推荐）

下载 [`corporate-vpn-template.module`](../modules/corporate-vpn-template.module)，替换占位值后作为本地模块导入。占位值均为文档专用地址：

```ini
[General]
skip-proxy = %APPEND% intranet.example, *.corp.example
tun-excluded-routes = %APPEND% 203.0.113.10/32
always-real-ip = %APPEND% intranet.example, *.corp.example

[Rule]
IP-CIDR,203.0.113.10/32,DIRECT,no-resolve
DOMAIN,intranet.example,DIRECT
DOMAIN-SUFFIX,corp.example,DIRECT
IP-CIDR,192.168.50.10/32,DIRECT,no-resolve

[Host]
intranet.example = 192.168.50.10
# *.corp.example = server:10.0.0.53
```

| 占位值 | 替换为 |
| --- | --- |
| `203.0.113.10` | 企业 VPN 公网网关 IP |
| `intranet.example` / `corp.example` | 公司内网域名 |
| `192.168.50.10` | 内网服务 IP（或整个网段，如 `10.20.0.0/16`） |
| `10.0.0.53` | 公司内网 DNS（可选） |

请勿把公司真实地址提交到公开仓库。

## 方式二：私有 Overlay

在已被 Git 忽略的 `host-conf/` 中创建 `profile.json`：

```json
{
  "label": "My Corp VPN",
  "output_prefix": "Shadowrocket-CN-Smart-Host",
  "with_groups": true,
  "skip_proxy_append": ["intranet.example"],
  "tun_excluded_routes_append": ["203.0.113.10/32"],
  "always_real_ip": ["intranet.example"],
  "top_rules": [
    "IP-CIDR,203.0.113.10/32,DIRECT,no-resolve",
    "DOMAIN,intranet.example,DIRECT",
    "IP-CIDR,192.168.50.10/32,DIRECT,no-resolve"
  ],
  "hosts": { "intranet.example": "192.168.50.10" }
}
```

```sh
python3 scripts/build.py --profile host-conf/profile.json
```

`host-conf/` 下会生成本机专用的离线版与在线版配置，不会进入仓库。
