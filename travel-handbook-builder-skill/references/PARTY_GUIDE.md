# 成员、分组与参与范围

本指南说明 1.0 已实现的旅行成员、不可变分组、计划参与范围和 Task 人群快照。工具只保存来源明确给出的身份区分、人数、年龄数字和原词类别；不会生成人名、生日、成人票/儿童票资格或价格规则。

新建 Trip 直接使用稳定数据契约 1.0；成员、分组和参与范围方法均可直接调用。

## 人数、名单状态和成员

只知道总人数时只写人数，不生成匿名成员：

```python
{"method":"party.describe","args":{"count":3,"members_status":"incomplete"}}
```

`count` 是正整数。`members_status` 只取 `complete` / `incomplete`；名单不会因已录人数碰巧等于 count 自动变 complete。complete 名单至少一人，成员数必须等于 count；任何名单的已录成员数不能超过 count。`clear` 只接受 `count`、`members_status`，不能删除成员。

来源已区分人物但没有姓名时，可忠实使用“同行者 A”这类显示 label：

```python
{"method":"party.member.add","as":"a","args":{
  "label":"同行者 A","declared_category":"成人"
},"origin":{"basis":"user_statement","statement":"来源把同行者 A 称为成人"}}
{"method":"party.member.add","as":"c","args":{
  "label":"同行者 C","age":{"years":11}
}}
```

`age.years` 是非负整数；只有来源明确年龄基准日时才加 `as_of:"YYYY-MM-DD"`。不知道基准日就省略，不用旅行首日或系统日期代填。`declared_category` 保存来源原词，不从 years 推断，也不用于自动票价资格。

成员更新保持同一身份：

```python
{"method":"party.member.update","args":{
  "target":a,
  "set":{"label":"同行者甲","age":{"years":38,"as_of":"2027-04-10"}}
}}
```

label 可纠正。age/declared_category 只能补缺失或提交同值；已有 `{years:38}` 可补相同 years 的 as_of。更改已知 years/category/as_of，或在完整 `set.age` 中遗漏已有 as_of，返回 `MEMBER_FACT_REPLACEMENT_REQUIRED`。当前不删除、合并成员或清除年龄。

## 不可变分组与稳定 handle

```python
{"method":"party.group.add","as":"pair","args":{
  "members":[{"local":"a"},{"local":"c"}],"label":"参观组"
}}
```

members 是非空 member handle 列表，重复 handle 按首次出现去重。组的成员集合创建后不原位修改；新的组合建立新 Group，再显式修改计划。member/group 回执都是稳定工作区 handle，同批可用 alias，后续从 read 复用。底层领域 ID 不作为公开写参数。

operation.origin 会按通用协议建立调用方明确声明的 Claim；GuideNote.related 也可直接使用 member/group handle。它们不会从 label 推断身份事实。

## 计划与住宿的友好参与者输入

`plan.add`、`plan.update.set.participants`、`journey.compose`、`route.compose`、`stay.plan`、`stay.change_plan.set.participants` 以及 Unit 的 occupants 接受：

```python
{"members":[a,c]}
{"groups":[pair]}
{"kind":"count","count":2}
{"kind":"unknown"}
{"kind":"all"}
```

members/groups 会写成领域 `member_ids` / `group_ids`，不能和其他变体混用。已有规范 member_ids/group_ids 输入仍兼容，但公开调用优先使用 handle。省略计划 participants 仍主动写 explicit unknown；它不会变成 all。Unit 省略 occupants 同样是分配未知，不继承 Stay 全体。

已受 confirmed Reservation、当前有效 Coverage、confirmed Cost、settled Payment、done Task 或 adopted confirmation/observation Claim 保护的已知参与人群不能直接替换，返回 `PLAN_PARTICIPANTS_CHANGE_BLOCKED`。Item 的 Journey/Route 及其 Leg/Stop/Segment 沿主 Item 人群保护；不经 Place、Path 或 Service 传播。Unit 的变更会检查直接目标 Unit 或父 Stay 的 Reservation、Cost、Payment 和 done Task；Coverage 必须精确以该 Unit 为 scope target 才保护房间分配。仅以父 Stay 为 scope target 的早餐等 Coverage 不下传成 Unit occupants 确认。父 Stay participants Claim 也不冒充 Unit occupants Claim。

编码不同但可证明人群相同不拒绝，例如完整 AB 名单下从 all 改为 members=[A,B]。explicit unknown 补成来源明确的人群也允许；回执的 `parts.participant_review_refs` 列出仍需核对的相关执行记录，记录本身不被修改。

## Coverage 和 Task 保存快照

Coverage 不能保存动态 group/all。1.0 的 `coverage.record` 与完整替换入口接受 friendly members/groups/all：members 直接固化，group 展开其当前成员，all 仅在名单明确 complete 时展开；领域 scope 最终只写 member_ids。省略仍是 unknown，count 保持 count。以后补成员不会修改旧 Coverage，也不证明新增成员已有权益。

Task 可写 assignees 和 beneficiaries：

```python
{"method":"task.add","args":{
  "title":"核实证件","action":"verify","targets":[trip],
  "assignees":{"groups":[pair]},
  "beneficiaries":{"kind":"all"}
}}
```

Task 的 groups/all 在写入时展开为 member_ids；all 要求非空 complete 名单。assignees 不接受 count 冒充负责人；beneficiaries 可保留明确 count 或 unknown。省略不推断人群，task.complete 也不会从 assignees 自动填写 completed_by。

1.0 done Task 的 assignees/beneficiaries 与其他定义字段一样须先 `task.reopen` 才能 amend。reopen 的 task_snapshot 深拷贝当时的人群；修改当前 Task 不改历史。

## 名册变更保护

旧包中可能存在动态 all。若人数、完整性或成员身份集合变化会改变当前 done Task、completion_history 或受保护计划的历史人群，整批返回 `PARTY_HISTORY_SCOPE_BLOCKED` 或 `PLAN_PARTICIPANTS_CHANGE_BLOCKED`。label、age、declared_category 的补充不改变成员身份。

如果旧完整名单 AB 的受保护计划确实仍只适用于 AB，可在同一原子批次先把该计划改成显式 members=[A,B]，再把名单扩为 ABC；工具比较整批前后实际人群，允许等价冻结。另一条历史 Task 自身的 all 不会因此解锁。Trip 目标 done Task 如果没有 assignees/beneficiaries/completed_by，不等于全体，不阻止补成员。不相关 Coverage 也不会锁住整个名单。

本入口不提供成人票资格、生日推算、身份证件、删除/合并成员、组内原位增删或任意人群历史系统。
