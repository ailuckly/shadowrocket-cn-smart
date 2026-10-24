# Third-party rule data

`data/*.list` are unmodified plain-text domain snapshots downloaded from [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat), commit `45a9c7f0489f8b1c7c3ae09192e2a6caa369a265` (the `meta` branch snapshot inspected on 2026-10-24).

The upstream repository publishes a [GPL-3.0 license](https://github.com/MetaCubeX/meta-rules-dat/blob/master/LICENSE). A verbatim copy is provided in this repository's `LICENSE`. Attribution and any rights in upstream data remain with their respective authors; this project does not claim to have created those domain lists.

| Local snapshot | Upstream path | Applied policy |
| --- | --- | --- |
| `data/geolocation-!cn.list` | `geo/geosite/geolocation-!cn.list` | PROXY |
| `data/apple.list` | `geo/geosite/apple.list` | PROXY |
| `data/microsoft.list` | `geo/geosite/microsoft.list` | PROXY |
| `data/geolocation-cn.list` | `geo/geosite/geolocation-cn.list` | DIRECT |
| `data/cn-lite.list` | `geo-lite/geosite/cn.list` | DIRECT |

The exact repository revision, source paths and SHA-256 digests are recorded in `sources.json`. Each source URL is `https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/<revision>/<path>`.

Upstream credits include [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) ([MIT license](https://github.com/v2fly/domain-list-community/blob/master/LICENSE)), [Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) and [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) ([GPL-2.0 license](https://github.com/blackmatrix7/ios_rule_script/blob/master/LICENSE)). In particular, MetaCubeX documents its geo-lite domain data as sourced from ios_rule_script. Consult the [upstream README](https://github.com/MetaCubeX/meta-rules-dat#readme) for its full source chain. Upstream original license notices are not replaced by the license for this project's own work.

Original upstream license texts are also included in `LICENSES/v2fly-MIT.txt` and `LICENSES/blackmatrix7-GPL-2.0.txt`.

Local transformations: map exact domains to `DOMAIN`, map `+.` suffixes to `DOMAIN-SUFFIX`, sort and deduplicate within each policy, omit DIRECT top-level suffixes, then place proxy domain rules before direct domain rules. A same-policy suffix supersedes a redundant exact entry in a source group; duplicate domain targets across template/groups keep the earlier decision. The original snapshots are retained intact. No node credentials, user traffic records, CA certificates or account data are included.

The configuration template, generator, regression tests and documentation are original work for this project, distributed under GPL-3.0-only. Shadowrocket is a third-party product; its app and proprietary implementation are not distributed here.
