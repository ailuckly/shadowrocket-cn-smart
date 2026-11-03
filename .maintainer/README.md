# 维护与来源

此目录用于项目维护。普通用户只需下载仓库根目录的 `.conf`，不需要运行下列命令或导入模板。

## 构建与检查

Python 3.9+，无第三方运行依赖；以下命令在仓库根目录运行，构建与测试均离线完成：

```sh
python3 .maintainer/build.py
python3 .maintainer/build.py --check
python3 -m unittest discover -s .maintainer -p 'test_*.py' -v
```

- `template.conf`：本项目维护的基础设置、规则顺序与补充域名。
- `data/`：未经修改的上游原始域名快照。
- `sources.json`：版本、日期、上游提交、路径及 SHA-256。
- `build.py` / `test_config.py`：生成器与静态回归测试。
- `LICENSES/`：上游原始许可文本。

测试覆盖生成一致性、唯一下载配置、域名分流样例、规则顺序、重复目标、被更宽后缀盖住的规则、局域网范围、DNS 设置和输入格式校验。静态检查不模拟 Shadowrocket 原生解析器、SNI、GeoIP 数据库或系统网络栈。

更具体的直连名字如果会被更早的境外后缀盖住，生成会失败。这类名字要写进模板第 2 段。同策略且已被后缀覆盖的规则会删掉。发布时除版本文件外，再上传一份同内容的 `Shadowrocket-CN-Smart.conf`，供固定导入链接使用。

## 默认配置参考

策略对照以 Shadowrocket **2.2.92** 随应用提供的 `default.conf` 为基准。参考点包括私有网络旁路、域名/GeoIP/FINAL 分层、专用 AI 域名和 UDP 不支持时拒绝转发。没有将客户端二进制或完整默认配置再分发到本仓库。

本项目的主动差异包括分离 DoH、默认 IPv4、代理流量关闭 QUIC、境外 Apple/Microsoft 域名优先代理、GeoIP 不额外解析未知域名，以及内置的版本化社区域名快照。它们是本项目的策略选择，不代表官方建议或对所有网络都更优。

## 规则数据

直接来源：[MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat)，固定提交 `45a9c7f0489f8b1c7c3ae09192e2a6caa369a265`，快照采集日期 2026-10-24。

| 本地文件 | 上游路径 | 策略 |
| --- | --- | --- |
| `data/geolocation-!cn.list` | `geo/geosite/geolocation-!cn.list` | PROXY |
| `data/apple.list` | `geo/geosite/apple.list` | PROXY |
| `data/microsoft.list` | `geo/geosite/microsoft.list` | PROXY |
| `data/geolocation-cn.list` | `geo/geosite/geolocation-cn.list` | DIRECT |
| `data/cn-lite.list` | `geo-lite/geosite/cn.list` | DIRECT |

每个文件的精确来源 URL 由 `https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/<revision>/<path>` 组成；提交、路径和校验值详见 [sources.json](sources.json)。

转换方式：精确域名转为 `DOMAIN`，`+.` 后缀转为 `DOMAIN-SUFFIX`；境外规则置于国内规则之前。同一策略内，后缀覆盖同名精确域名。跨组去重时，同名后缀若与更早的精确规则策略相同，则保留后缀；策略不同则两条都保留，精确规则在前。单标签直连后缀只保留 `cn` 以及百度、搜狐等国内品牌顶级域，继续丢弃 `+.ms`。不会把其他客户端的原始格式直接作为 Shadowrocket 规则引用。

## 许可与署名

MetaCubeX 上游仓库发布 [GPL-3.0](https://github.com/MetaCubeX/meta-rules-dat/blob/master/LICENSE)，本仓库根目录的 [LICENSE](../LICENSE) 保留其完整标准文本。域名数据的归属与原始许可保留给对应作者，本项目不主张上游列表的原创权。

其上游来源包括：

- [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community)，[MIT 原文](LICENSES/v2fly-MIT.txt)。
- [Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat)。
- [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)，[GPL-2.0 原文](LICENSES/blackmatrix7-GPL-2.0.txt)。MetaCubeX 的 geo-lite 数据注明来自该项目。

完整来源链参见 [MetaCubeX README](https://github.com/MetaCubeX/meta-rules-dat#readme)。上游原始许可不因本项目自身的许可证而被替代。本项目原创模板、生成器、测试及文档使用 GPL-3.0-only；Shadowrocket 是独立的第三方产品。

## 发布约定

1. 修改模板或更新同一上游提交下的快照；审查内容、来源和许可，再更新 SHA-256。
2. 在 `sources.json` 中递增版本与日期，生成新文件，并更新首页下载链接。根目录只保留当前一个用户配置；历史版本由 Git 标签和 Release 保留。
3. 运行静态检查，并在测试设备上完成原生导入与联网验证；如尚未完成，继续标为 beta。
4. 发布独立版本名的附件，不覆盖已发布的标签或文件内容。

规则数据更新不会自动推送到用户设备，用户需下载新版本重新导入。
