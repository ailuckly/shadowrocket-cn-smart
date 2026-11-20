# 模块与证书

[项目首页](../README.md) · [导入指南](README.md) · [企业 VPN 共存](corporate-vpn.md)

主配置不包含广告改写与 HTTPS 解密。以下模块在 **配置 → 模块 → `+`** 中按需添加，主配置更新后仍然保留。

| 模块 | 原理 | 证书 | 说明 |
| --- | --- | --- | --- |
| [`adblock-dns`](../modules/adblock-dns.module) | 域名 `REJECT` | 不需要 | 拦截广告联盟、移动广告 SDK 与追踪域名；整域拦截，误杀率低但不为零 |
| [`adblock-mitm`](../modules/adblock-mitm.module) | `URL Rewrite` + MITM | 需要本机自签 | 改写 B站、知乎、微博开屏广告接口 |
| [`block-httpdns`](../modules/block-httpdns.module) | 拦截 HttpDNS | 不需要 | 让 App 回到标准 DNS，从而遵循分流 |

## 关于 `adblock-mitm`

- 只解密 6 个主机：`app.bilibili.com`、`api.zhihu.com`、`sdkapp.uve.weibo.com`、`wbapp.uve.weibo.com`、`cpro.baidustatic.com`、`pos.baidu.com`，不含任何银行或支付域名。
- 其中 B站、知乎、微博是业务 API 主机，开启后这些主机的全部请求（包括登录凭证）都会在本机解密再转发，改写只作用于广告接口。如果介意，只使用 `adblock-dns` 即可。
- 个别 App 启用了证书固定，开启后可能整体无法联网，关闭模块即可恢复。
- 本项目不分发任何证书或私钥，请在自己的设备上生成。

## 生成并信任证书

**iOS / iPadOS**

1. Shadowrocket → 配置 → 当前配置右侧 `ⓘ` → **HTTPS 解密**，打开开关。
2. **证书 → 生成新的 CA 证书 → 安装证书**。
3. 系统设置 → 已下载描述文件 → 安装。
4. 通用 → 关于本机 → 证书信任设置 → 打开该证书的完全信任。

**macOS**

1. 在 Shadowrocket 中按同样路径开启 HTTPS 解密并生成证书。
2. 安装到登录钥匙串，在钥匙串访问中将该证书设为 **始终信任**。

完成后启用模块并重新连接。

## 排查

某个 App 异常时，先逐个关闭模块定位；在请求日志中找到被 `REJECT` 的域名后，欢迎提交 Issue。
