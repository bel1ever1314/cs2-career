# CS2 Career 1.5 扩展包

扩展包是纯数据目录，不运行第三方 Python。把 `_templates` 里的某个模板复制到
`extensions` 根目录，去掉目录名前的下划线，修改 `pack.json` 和 JSON 内容，重启游戏即可。

```text
extensions/my-pack/
  pack.json
  stories/*.json   # 剧情包
  skins/*.json     # 皮肤与箱子包
  events/*.json    # 赛事包
  teams/*.json     # 战队包（稳定预留接口）
  eras/*.json      # 年代包（稳定预留接口）
```

`pack.json` 的 `schema_version` 当前固定为 `1`。`id` 必须全局唯一，只能使用小写
字母、数字、点、`-`、`_`。`load_order` 越小越早载入。将 `enabled` 改为 `false`
即可停用。一个包可以在 `types` 同时声明多种内容。

五种类型均已接入运行时。赛事日期可写 `YYYY-MM-DD` 或 `MM-DD`；后者使用生涯年份。
`teams` 可追加或按 ID 替换五人战队；`eras` 可增加年代元数据、排名和阵容。赛事、战队
与年代不会改写进行中的世界，只在新生涯生效。

损坏、缺目录或版本不支持的包会显示为 `rejected`，其内容不加载，其他包和存档仍可
使用。赛事与年代变化只影响新生涯。建议给所有 ID 加作者前缀，避免与其他作者冲突。
