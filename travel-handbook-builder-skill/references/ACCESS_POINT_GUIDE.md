# 地点入口编制指南

本文说明 `access_point.add` 与 `access_point.update`。AccessPoint 表示属于一个既有 Place 的明确入口、站台、航站楼等细粒度端点；它不是新的 Place，也不会自动替换任何安排或交通端点。

## 创建独立入口

`place` 必须是当前工作区的 Place handle，`name` 和 `kind` 必须是来源明确的非空字符串。kind 沿用开放字符串，例如 `terminal`、`entrance`；工具不猜方位、编号或类型，也不把同名入口自动合并。

```python
{"method": "access_point.add", "as": "t2", "args": {
    "place": airport,
    "name": "第二航站楼",
    "kind": "terminal",
    "access_notes": "来源说明从到达层进入"
}}
```

location 可省略。两个无坐标的 T2/T3 可以属于同一个机场 Place，仍返回两个稳定且不同的 AccessPoint handle。创建入口不会修改父 Place 的身份、字段或 location，也不会修改已有 Item、Journey、Leg、Call、Route、Reservation、费用或 Task。

`place` 可用同批更早的 Place alias。raw `{"type":"place","id":...}`、Place 之外的 handle、其他工作区或不存在的 handle 都会拒绝；公开方法只接受稳定 handle/批内 alias。

操作可以带既有通用 `origin={basis,statement}`，生成指向新 AccessPoint 的 authoring_statement Claim。方法不会从 name、kind、说明或 location 自动生成核验 Claim。

## 定位可省略或后补

AccessPoint location 完全复用[地址与坐标指南](LOCATION_GUIDE.md)的 Location：具名 `lat`/`lon`、明确非空 `coordinate_system`、明确 `precision`，并可带 notes/source_ref。它不继承父 Place 的坐标，不从小数位推断 precision，也不默认 WGS84。

```python
{"method": "access_point.add", "as": "gate", "args": {
    "place": venue,
    "name": "北入口",
    "kind": "entrance",
    "location": {
        "lat": 22.31,
        "lon": 113.92,
        "coordinate_system": "WGS84",
        "precision": "entrance",
        "notes": "来源明确为入口点"
    }
}}
```

公开 read 在尚未建立 Trip 时也会列出：

```python
contracts = read_workspace(state)["capabilities"]["coordinate_inputs"]
create_location = contracts["access_point.add.location"]
update_location = contracts["access_point.update.set.location"]
```

非空 CRS 字符串按调用方声明保留，工具不验证或转换；`unknown`、`TBD`、`待确认`、`未知` 等占位或缺失 CRS 会拒绝。未知时省略 location，把原始数值、顺序、来源及待核实原因保留在 access_notes/notes，不能填 WGS84 占位。Path 的 WGS84-only 规则不适用于 AccessPoint Location。

Location 的 `source_ref` 与 Place 规则相同：它是领域 Source Ref，不在嵌套位置接受 handle。先用公开来源方法登记并提交，再从 read 取得 Source 记录的 id，按 `{"type":"source","id":...}` 提交；不要自己编 id。source_ref 只保留关联，不表示坐标已由工具核验。

## 受限更新

`access_point.update` 只允许：

- `set.name`：同一入口名称纠错；
- `set.location`：提供完整 Location，整体替换，不合并子字段；
- `set.access_notes`、`set.notes`；
- `clear` location/access_notes/notes；
- `append_note` 追加 notes。

```python
{"method": "access_point.update", "args": {
    "target": gate,
    "set": {"name": "北侧主入口", "location": complete_location},
    "append_note": "补录现场通行说明"
}}

{"method": "access_point.update", "args": {
    "target": gate,
    "clear": ["location"]
}}
```

name 不能 clear。place_ref 和 kind 都不能修改；名称纠错只适用于同一业务入口，工具不根据自然语言判断“北入口”与“南入口”是否同一对象。要记录另一个入口，应新建 AccessPoint。更新保持 AccessPoint id 和 handle，也不改父 Place 或已有引用。

缺 location 字段、未知占位 CRS、越界/非数值/非有限坐标、错误 source_ref 或不完整替换使整批原子失败。修正后应重发整个失败请求；不要把一次 location 失败拆成保留了其他意外修改的局部提交。成功 request_id 原样重放不会重复创建或重复追加说明。

本入口不编辑外链、不建立 Path、不创建车辆，也不把 Service Call 端点精化到新入口。后续班次方法需要显式引用这个 AccessPoint，不能因为入口已存在就声称已有安排使用它。
