# 已选安排待排日期指南

1.0 允许先记录**已经选定、但尚未分配到某一天**的普通安排。它不是候选清单、推荐系统或退役区，也不表示旅行日期未知。Day 与 Trip 仍须有明确日期；安排一旦归日，继续沿用原有 Day 顺序。

## 数据契约

新建 Trip 直接使用稳定数据契约 1.0。待排安排可直接创建，不需要额外版本迁移。

## 创建待排安排

1.0 的普通 `plan.add` 可省略 `day`：

```python
{"method": "plan.add", "as": "museum", "args": {
  "kind": "visit",
  "title": "参观博物馆",
  "place": museum,
  "participants": {"members": [adult, child]}
}}

{"method": "plan.add", "as": "souvenir", "args": {
  "kind": "shopping",
  "title": "购买伴手礼"
}}
```

其余 `plan.add` 规则不变：visit 仍须 Place； shopping 可缺 Place；kind=other 仍须非空 purpose；省略 timing 和 participants 仍分别保存 explicit unknown。省略 day 时不能传 before，因为没有同 Day 锚点。

`journey.compose` 与 `route.compose` 仍要求 day。已有待排 Item 使用 1.0 的 `plan.move(target, day, before?)` 原身份归日；完整顺序、保护和错误语义见[安排编辑指南](ARRANGEMENT_EDIT_GUIDE.md)。调用方不能靠手改 Trip/Day 引用模拟移动。

## 读取、导出与诊断

`read_workspace` 在 1.0 为 `objects[]` 中的每个 Item 返回明确的 `ownership`：

- `{"kind": "day", "day": {"handle": "..."}}`：属于某个 Day；
- `{"kind": "unassigned"}`：已经选定，尚未归日；
- `{"kind": "retired"}`：退役，不属于现行容器。

导出包在 `trip.unassigned_item_refs` 保留待排 Item 引用。每个 current Item 必须且只能出现在一个 Day 或该列表中；重复、双归属、遗漏、悬空引用，以及把 retired Item 放进现行容器，都会使校验失败。

待排 Item 的 check 会返回 `TIME_DAY_UNASSIGNED` warning，不据此猜日期或时区。若 Item 自身已有明确时间边界或约束，仍照常解析和评估；只是需要 Day 日期的归属匹配保持未知。warning 不代表安排是候选，也不代表时间已可行。

`plan.update` 可继续修改待排 Item 已开放的字段。时间、参与者、Task、Coverage、Reservation、费用、付款和 adopted Claim 的既有事实保护在 1.0 继续生效；待排归属不能用来绕过确认或完成历史。

待排状态不扩大 `plan.update` 的字段范围。调用方应遵循[有界字段更新](CALLER_GUIDE.md#有界字段更新)，为待排 Item 提交最小补丁并核对对象级差异。

本入口不实现候选安排、未知 Trip 日期、自动排程或网页。费用方法会按 active Cost 汇总已录费用，不因 Item 待排、移动或 retired 而忽略，见[费用指南](MONEY_GUIDE.md)。
