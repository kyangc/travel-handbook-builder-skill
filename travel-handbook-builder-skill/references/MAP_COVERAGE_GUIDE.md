# 按日地图覆盖只读报告

`client read ROOT --report map-coverage`（状态文件：`read STATE --report map-coverage`）检查当前 state 的地图输入与投影覆盖，不改 state、canonical、revision 或旅客正文。Schema 仍为 1.0；没有新增 check 门禁。Python 使用原有 `read_workspace(..., report='map-coverage')`／`book.read(report='map-coverage')`。

可加 `--day DAY_HANDLE` 限定一天；默认 50 行，`--limit` 为 1–100。重复传同一 report、day、limit 和返回的 `pagination.next_cursor`，直到 `has_more=false`。游标绑定工作区、revision 和报告范围；不得把首屏当全报告。其他 read 过滤器和 source-text 不可与报告混用。`summary`／`days` 始终覆盖完整所选范围，`rows` 才分页；`pagination.total` 给完整行数。无 Day 过滤时另含没有任何当日地图关系的库存行；限定一天时不包含全局库存。

报告逐行给当前 handle、Ref、Day 和原因。已选地点、每次 Route Stop（含重复 Place／pass_through）、Recommendation、显式关联 AccessPoint 及路径绑定分别保留。Recommendation 只按明确 Day／当前 Item 关系入图，仍为候选；不会成为固定日程。退役或没有日期关系的对象留在库存行，不能默默当作当前地图输入。

`unique_places` 是不同 Place 数，`place_day_associations` 是不同 Day/Place 对数；同一天重复 Stop 不增加后者。`point_occurrences` 保留各次输入出现次数。图针按前端坐标拥有者去重，多个 AccessPoint 可以使图针数多于地点数。Recommendation 另给不同地点、Day/Place 对数和 Recommendation/Day 记录次数。

`coordinates` 区分 missing、unsupported_crs 和 usable；仅 WGS84 被前端采用。链接／地址不等于坐标。precision 原样解释为已记录入口、建筑、区域代表点或近似且精度未知，不能由小数位推断实际精度。AccessPoint 仅因 parent Place 关联不自动入图；显式端点没有坐标时可回退 Place 图针，但不能作为精确入口或端点连线依据。不推断所有 Place 都需要入口，`entrance_requirement=not_assessed`。

Path 资料与实际显示分别报告。没有 Path 时可能显示两端点示意线；这仍是 `missing_path`，不构成徒步导航。已有 Path 也不证明可通行、实时有效或覆盖全程；多 part 标记 `continuity_not_assessed`。Route 总览 Path 优先时分段线被过滤，报告保留其原因和原绑定；`path_usage=segments` 使用分段线。

本报告只证明**当前 state 按既有前端口径可投影哪些点／线**。managed 输出另标 canonical revision 与 publish_status；stale 时网页可能仍是旧版。实际 Google 底图或自有地点示意的渲染、图瓦／网络、现实入口和路线可行性均为 not_assessed。没有浏览器访问、点位搜索、坐标转换、自动选点、路径生成或候选采纳。

实现取舍：便携 Python 运行时不依赖 Node／浏览器，无法直接执行 TypeScript 投影。报告只镜像稳定的地理关系子集，以跨语言合成契约测试逐日比较当前 `buildHandbook` 的 points／lines；改地图关联或线选择规则时必须同步这些测试，不维护第二套旅客 UI。
