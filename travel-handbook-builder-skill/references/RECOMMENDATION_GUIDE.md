# 推荐地点：收录理由，不自动排入日程

`recommendation.add` 和 `recommendation.update` 沿用 [公共批次协议](README.md)。调用方须已经理解来源中的推荐意图；方法不评价地点，也不生成推荐理由、营业事实或旅行决定。

## 最少调用

```python
{"method": "recommendation.add", "as": "sunset-idea", "args": {
    "place": existing_place,
    "reason": "原文明示：天气合适时可以看湖边日落"
}}
```

place 必须是已收录 Place 的 handle，也可以是本批次前序 `place.add` 的 local 引用；reason 必须是有内容的明确文字。没有来源理由时不写通用“值得一去”补齐输入。

返回的 primary 和 `as` 都是 Recommendation handle。它复用 Place，不复制地点、不创建 Item、不改变 Day 顺序，也不新增待办、票券或费用。已排入安排的地点仍可以有本次旅行的推荐理由；两者保持独立。

## 按已有信息补充

```python
{"method": "recommendation.add", "args": {
    "place": existing_place,
    "reason": "原文明示：适合顺路看湖景",
    "related": [existing_day, existing_arrangement],
    "interests": ["湖景", "散步"],
    "duration_advice": [{
        "experience": "湖岸散步",
        "minutes": [30, 60],
        "conditions": "视天气和体力而定",
        "notes": "原文提供的建议时长"
    }],
    "notes": "营业与预约情况尚未核实"
}, "origin": {"basis": "user_statement", "statement": "旅行笔记中的建议，未作供应方核验"}}
```

- related 只接受 Day 或安排 Item handle，表示关联背景；不表示已安排。不能放 Place、Task 或任意对象。
- interests 为调用方明确给出的非空文字列表；不会从地点角色自动推导。
- duration_advice 为列表，每项必须包含 experience 和 minutes；minutes 是非负分钟单值或 `[最小, 最大]`，不是结束时刻。conditions/notes 可省略。未知时长时省略建议项，在已有说明中保留信息缺口；不得填零代替未知。
- 规范包保存为 `duration: {min_minutes, max_minutes}`。这些是某玩法的游览建议，不改变任何 Item 的 timing 或 Route 的 dwell。
- minutes 暂不支持带 basis/statement 的证据对象，明确拒绝而不静默丢掉依据。可用公共 origin 保存整项推荐的陈述；不会自动生成“已核实”或数值级 adopted Claim。
- 可选资料省略表示未记录。`related: []`、`interests: []` 或 `duration_advice: []` 表示当前列表为空，不证明世界中没有相关资料。

## 更新、清空与身份

```python
{"method": "recommendation.update", "args": {
    "target": recommendation_handle,
    "set": {"reason": "用户补充：主要想看日落", "related": [existing_day]},
    "append_note": "尚未决定是否加入日程"
}}

{"method": "recommendation.update", "args": {
    "target": recommendation_handle,
    "clear": ["duration_advice", "notes"]
}}
```

set 白名单为 reason、related、interests、duration_advice、notes；列表整体替换，不作隐式追加或深合并。省略字段保持。append_note 保留原文后追加，不能与 set/clear notes 混用。

clear 只允许 related、interests、duration_advice、notes，移除对应可选字段。reason、place 与 id 不可清空；update 不允许更换主体地点，避免同一推荐身份悄悄换成另一家店。另一地点需要独立推荐，本片不含删除推荐的方法。

所有更新保留推荐 ID 和 Place 引用。类型错误、缺少引用、非法时长或字段冲突导致整个批次回滚，包括同批先做的其他修改。成功请求同 ID/同载荷重放不重复推荐或追加说明；新请求再次 add 不会按名称或地点去重。

## 验证

通过公共 authoring Interface 运行行为测试：

```sh
python3 -m unittest discover -s tests -p 'test_authoring_recommendations.py'
```

测试范围为公开 apply/read/export、身份及关联保护、明确未知、原子失败和重放；不证明推荐内容真实、来源已完整转换或地点适合实际旅行。
