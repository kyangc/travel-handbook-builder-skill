# 营业资料与既定用餐安排的影响检查

使用既有 [CALLER_GUIDE](CALLER_GUIDE.md) 中的 place.hours.update 更新资料，plan.add / plan.update 明确记录用餐安排。本轮没有增加写方法，也没有将 source.duration 刷新扩大为营业规则刷新。

## 明确用餐起止时间

```python
{"method":"plan.add", "as":"meal", "args":{
    "day":day, "kind":"meal", "title":"已选午餐", "place":shop,
    "timing":{"kind":"fixed",
              "start":{"local":"2026-10-05T12:30:00","timezone":"Asia/Tokyo"},
              "end":{"local":"2026-10-05T13:30:00","timezone":"Asia/Tokyo"}}
}}
```

fixed只用于原文明确排定的时间，不是为了让检查通过而把预计时间改成固定时间。estimated、unknown、window、derived、缺少起点或终点均返回unknown。本轮不从预计游玩时长推算结束时间。

## 读取检查

```python
report = check(state)
assessments = report["availability_assessments"]
artifact = export_package(state, revision=read_workspace(state)["revision"])
assert artifact["validation"]["availability_assessments"] == assessments
```

对每个当前kind=meal的安排产生一条记录；其他活动及退役安排不在本轮范围内。item_ref/place_ref是领域引用，可用read_workspace对象record.id查对应handle，不要直接把领域引用当作写方法的handle。

仅选地点唯一的scope=venue（整体营业）规则，不从标题“午餐”猜scope=lunch，不用商场营业代替内部餐厅。若需要核实是否供应午餐、是否过了点单截止或是否已订座，仍须另外核实。limits明确这层边界。

| status | 含义 |
|---|---|
| covered | 已记录整体营业区间覆盖整个起止区间；不是用餐可行保证 |
| conflict | 至少一段时间明确与记录的营业规则不相容，或与绝对休业区间重叠 |
| unknown | 资料不足或遇到本轮不支持的规则；不能当作已通过或闭店 |

计算使用半开区间 `[start,end)`，以UTC比较绝对时刻。13–14的安排可被11–14营业覆盖；14点开始的安排不能。分段营业中间缺口不会被连起来；相邻营业区间允许共同覆盖。

covered/conflict与已进入区间计算的unknown返回interval（UTC起止）、schedule_id和相关rule_ids；冲突附uncovered_intervals。绝对休业冲突改附closure_indices，索引指向该schedule的closures。它们是当前诊断定位，不是永久来源锚点。资料不足且已知覆盖不足时附unverified_intervals，这只是尚未证实营业的区间，不能据此宣称关闭。

冲突同时出现在report.warnings，code为MEAL_OUTSIDE_VENUE_HOURS。成功apply回执也返回这些警告；未知结果请读取check中的availability_assessments。诊断每次按当前最终状态重算，旧请求重放仍返回原回执，当前结果以check为准。没有“警告消失所以全旅行通过”的含义。

## 原文没有提供的星期不能填closed

周一营业14–18、周日没写时，周一12:30–13:30可能受周日跨夜营业影响，本轮返回unknown/opening_start_day_unspecified，并列出unverified_intervals。只有明确记录周日不开始营业（closed）或已知其跨夜时段不能覆盖午餐，才足以据周一资料判定conflict。不要为了生成冲突而编造星期规则。

周日22点至周一02点营业，周一weekly closed，周一01–01:30仍是covered；weekly closed只表示当天不开始新的营业。明确周一整天休业用closed_dates，它形成绝对关闭区间，诊断为conflict/absolute_closure_overlap。

未知前日可能延续到次日，因此工具保守保留其潜在覆盖范围；已知营业已完整覆盖安排时，不因别的未知日而撤回covered。

## 保存事实与处理安排分开

营业资料更新成功，即使产生conflict也不阻止保存。Item、办理待办及其他地点不会自动修改；工具也不自动新建待办。调用Agent根据诊断与已有授权决定是否调整安排、核实资料或保留风险，并通过现有方法另行明确操作。

此冲突不是IMPORT_CONFLICT。前者表示不同对象的已记录内容不相容；后者表示新原文试图覆盖人工修改过的字段。

## 当前计算范围

支持唯一venue、每周规则、跨夜、绝对closures、明确固定起止、跨时区比较。只读，不推进revision，不把诊断写成业务事实。

以下返回unknown：无地点、无venue、多份venue、日期例外、季节有效期、非空cutoffs、同星期多条规则、显式offset、非唯一或不存在的本地时刻、日期超出计算范围。旧完整输入中若存在当前时区库无法解析的时区，也返回unknown/timezone_not_supported，不因诊断崩溃而中断操作。区间涉及的营业起始日（含前一日）跨度超过7天也暂不计算。DST检测依赖运行环境时区库；没有联网验证营业事实。

check.valid仅表示结构与现有有限语义有效；conflict仍是warning，unknown仍需检查。导出允许保留这些情况，网页应读取诊断含义，不能把领域包通过Schema当成已安排妥当。
