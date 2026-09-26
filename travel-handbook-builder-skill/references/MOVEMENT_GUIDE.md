# Agent 路线输入指南

与 [共同调用约定](CALLER_GUIDE.md) 配合使用。以下是放入 operations 的动作；day、place_a 等变量都是已创建对象的 handle 或同批前置 local 引用。不需要阅读领域 Schema。此切片只编制已经选定的安排。

补已选日程的相邻交通时，按当前 Day 的 active Item 顺序及已选 Stay 地点核对端点；酒店到首个安排、最后安排回酒店也只在该住宿和衔接确属本次计划时纳入。先读已有 Journey/Route、Leg/Segment 与来源，避免重复建交通 Item。对已采用的方式和路线，可用适用的公开资料补步行/乘车时长、必要换乘和候车范围，并保留估算条件；具体字段分别见下文的 `timing`、`duration_minutes`、Connection step `duration` 等。资料只给出备选而用户尚未选定时，不创建正式 Journey/Route，不替用户选路；未知项简短说明即可。两个活动的起止时刻差不是交通用时，不能当作 Leg 或 Segment duration。

## 从 A 到 B 的多段交通

一次 journey.compose 生成一条正式交通安排及其移动段。未选定班次时，各 independent 段必须明确交通方式和起终地点；工具不根据名称、坐标或换乘说明自动添加步行段。1.0 也支持明确 Service/Call 的 scheduled 段、逐段时间和有类型 Connection，完整调用见[班次与接续指南](TRANSPORT_SERVICE_GUIDE.md)。

```python
{"method": "journey.compose", "as": "transfer", "args": {
    "day": day, "title": "示例接驳",
    "legs": [
        {"key": "walk", "mode": "walking", "from": place_a, "to": place_b},
        {"key": "rail", "mode": "rail", "from": place_b, "to": place_c},
        {"key": "bus", "mode": "bus", "from": place_c, "to": place_d}
    ],
    "connections": [
        {"from": "walk", "to": "rail", "kind": "unknown"},
        {"from": "rail", "to": "bus", "kind": "transfer"}
    ]
}}
```

legs 是有序非空列表，key 在此安排内唯一。independent 段可选 timing、notes、path、mode_label（仅 other 必须提供）；scheduled 段引用 Service 与两个 Calls。connections 必须恰好逐一对应相邻段，单段行程填 []。kind 可用 transfer、through_stop、continuation、unknown，取自明确输入；未知就明确 unknown。不推断联程保障、行李直挂或换乘所需时间。

回执 primary 和 aliases.transfer 是正式安排的引用，可以挂待办。parts.legs 与 parts.connections 按 key 返回每段及每个接续引用。省略顶层 timing 时安排为unknown；分段时间只由每个 Leg/Call 的明确输入决定。显式整体时间见下节；没有自动生成列车班次、总时长、预订或付款。已有段的有界时间补充、班次绑定及 Connection 补全使用 journey.edit；换班和已知班次改期仍不支持，不能重建重复安排代替修订。

## 徒步或其他途经点路线

route.compose 创建一条正式游览安排。地点表示可复用实体，stop 表示**这次经过**。折返同一座桥时必须用两个不同 key 引用同一个 Place。

若已有一个 current 普通 Visit，后来只是把**这同一次到访**细化为多途经点路线，使用下文的 `route.bind_visit` 原位细化，不再 `route.compose` 出第二个 Item。同一 Place 在不同时间确有两次到访时则是两个合法安排；仅凭同名或同 Place 不推断合并。

```python
{"method": "route.compose", "as": "walk", "args": {
    "day": day, "title": "示例折返步行",
    "stops": [
        {"key": "bridge-out", "place": bridge, "purpose": "去程看桥", "dwell_minutes": 10, "encounter_kind": "visit"},
        {"key": "view", "place": viewpoint},
        {"key": "bridge-back", "place": bridge, "purpose": "返程只经过", "dwell_minutes": 20, "encounter_kind": "pass_through"}
    ],
    "segments": [
        {"key": "out", "from": "bridge-out", "to": "view", "mode": "walking", "duration_minutes": [30, 40]},
        {"key": "back", "from": "view", "to": "bridge-back", "mode": "walking", "duration_minutes": 35}
    ]
}}
```

stops 至少两次停留，segments 恰好按顺序连接所有相邻 stop。stop 的 key、place 必填；可选 purpose、dwell_minutes、notes、`encounter_kind`。`encounter_kind` 仅接受 `visit`（本次游览）或 `pass_through`（本次只经过、不作为景点游览），有明确依据才填；省略表示未知，导出时不写默认值。`pass_through` 不表示不停步、无耗时或无需接驳/购买，有 dwell 时照常保留。`route.compose` 按本次顺序生成 Stop 的 `role=start/waypoint/end`；它表示路线位置，不是 Place 的功能类别 `roles`，同一地点可在不同 Stop 分别出现。不能凭相同 Place、role、purpose 或 dwell 猜测本次活动，也不能据此自动合并 Route 外的 Visit。不要把“起点/途经/终点”写成 Place 类别；地点分类仍只按[地点角色合同](CALLER_GUIDE.md#地点类型与资料不足)中的已知功能填写，未知可省略。没有 purpose 时，生成明确占位“本次游览目的未记录”，并在 parts.missing_facts 报告缺失；不猜游览原因。

segment 的 key/from/to/mode 必填；可选 mode_label、duration_minutes、distance_m、path、notes。mode 可用 walking、cycling、driving、taxi、bus、rail、metro、tram、air、ferry、other；other 需 mode_label。不同段可以不同 mode，不传 mixed 给单段。

明确属于道路客运的共享接驳统一使用 `mode: "bus"`，包括接驳车、接驳巴士、摆渡车、班车、shuttle bus 和 shuttle coach。mode 分类与 scheduled/independent 选择分开判断：运营方未知不阻止建立 scheduled Service；`service_number`、`service_date` 和合法 Calls 明确时遵循 scheduled 契约，即使部分 Call 时间显式 unknown。缺少必要班次身份或无法建立合法 Calls 时，才使用 independent bus Leg 保存已知端点和时间。`other + mode_label` 仅用于规范列表没有的交通类别，或原文只说含糊的 “shuttle” 而无法判断它是公路车辆、铁路、船还是其他方式；不要用 `mode_label: "接驳车"` 代替已知的 bus 类别。

分钟值可用非负数字或 [最小, 最大]；省略表示未知，不是零。不自动相加路程、停留时间，也不从这些分钟值生成整条安排的开始/结束时间；已知整体时段可通过timing单独提供。participants 可选，省略为 unknown；如需明确全体，使用 {"kind":"all"}。1.0 也接受[成员指南](PARTY_GUIDE.md)中的members/groups handle形式。两种 compose 都遵守此约定。

回执 primary 是正式路线安排。parts.stops/parts.segments 按输入 key 返回稳定引用。局部引用可以跨请求使用，JSON 保存工作区再读回仍有效。也可在**同批后续操作**直接引用：

```python
{"local": "walk", "part": {"kind": "stop", "key": "bridge-back"}}
{"local": "walk", "part": {"kind": "segment", "key": "back"}}
```

### 已有 Visit 原位细化为 Route

先 `client read` 确认要细化的这次 Visit，取得其 Item handle、原 Place 和现行 revision；以下 `visit` 是这个 Item 的公开 handle，`bridge`、`viewpoint` 是已选 Place 的公开 handle。`source_stop_key` 指向有序 stops 中**精确引用原 Visit Place** 的一次 Stop；旧 Place 的子 AccessPoint 不是相同 Place ref，不能作为这次映射。折返同一 Place 时，由作者根据这次路线选择承接旧到访的那次经过，不按地点名猜。

```python
{"method": "route.bind_visit", "args": {
    "target": visit, "source_stop_key": "bridge-out",
    "reason": "把这次桥边到访细化为折返路线",
    "stops": [
        {"key": "bridge-out", "place": bridge, "purpose": "去程看桥"},
        {"key": "view", "place": viewpoint, "purpose": "经过观景点"},
        {"key": "bridge-back", "place": bridge, "purpose": "返回桥边"}
    ],
    "segments": [
        {"key": "out", "from": "bridge-out", "to": "view", "mode": "walking"},
        {"key": "back", "from": "view", "to": "bridge-back", "mode": "walking"}
    ]
}}
```

`reason` 必填；`route_title` 可选，省略时新 Route 沿用旧 Item.title，显式提供也只命名 Route，不暗改 Item.title。Stop/Segment 输入与 `route.compose` 相同，包括可选 `encounter_kind`，但此入口不接受 `day`、整体 `timing`、`participants` 或 `source_adoption`：原 Item 的身份、Day 序位、title、整体 timing、participants、purpose、notes 保留，kind 改为 route；回执 `primary` 仍是原 Item handle，`parts.route/stops/segments/legs` 是新路线引用，`parts.source_place_ref/source_stop_key/preserved_fields/reason/review_refs` 供读回核对。已有 Task 等指向该 Item 的关联不会因细化而自动改挂、取消或一律阻断；对 review refs 按实际文字与现实承诺复核。已采用的 kind/place_ref/subject_ref Claim 或旧 place_ref 来源字段绑定等真正冲突会以 `ROUTE_BIND_BLOCKED` 和具体 blocker 原子拒绝；`source.field.resolve` 不是通用解绑入口，Place 映射不符也拒绝，不能绕过保护另造重复 Item。使用同一 managed ROOT 的 prepare-request→commit→read/check 核对当前状态，不把 check.valid 当作现实路线或票券适用性的证明。

`review_refs` 是有限的复核候选清单，仅列出直接指向原 Item 的 Guide Note、Issue、Reservation、Cost；保持原目标和状态的 open/done Task 不因此列入，也不会自动重开。`review_refs=[]` 只表示这份清单没有标出候选，不表示没有 Task 或其他关联。此清单不检索自由文本、间接关联或付款依赖；对现实承诺仍需结合 `client read` 中的实际对象核对。

反例：已经有独立 Route Item 和 Visit Item 的旧重复，不可再对 Visit 调用 `route.bind_visit` 来期待自动合并两个对象；本方法只防止**今后**把一次普通 Visit 细化时新建第二个 Item。不要把合法的另一时段再访、Route 外另一次 Visit，或两个同 Place Stop 自动合并。

## 明确整体安排时间，不推算班次或分段时间

两种compose现在都接受可选timing，主返回仍是正式Item的handle。与普通plan.add使用同一输入：

```python
# 放在journey.compose或route.compose的args中
"timing": {
    "kind": "estimated",
    "start": {"local": "2026-10-05T10:30:00", "timezone": "Asia/Tokyo"},
    "end": {"local": "2026-10-05T12:10:00", "timezone": "Asia/Tokyo"}
}
```

estimated表示预计安排；原文明示固定时段才用fixed。1.0 支持end-only、不同确定性的boundaries、相对结束及derived自身简写，详见[时间指南](TIME_PLAN_GUIDE.md)。完全未知用{"kind":"unknown"}或创建时省略。时区分别按原文明示输入，可跨午夜、跨时区，不用旅行默认时区代替另一个地点的时区。这里输入的是整体安排时段：09:00酒店出发、10:00列车发车时，09:00属于整体安排，不能据此填写列车班次。

已有安排用同一plan.update修改：

```python
{"method":"plan.update", "args":{
    "target": transfer_item,
    "set":{"timing":{"kind":"estimated",
        "start":{"local":"2026-10-05T10:45:00","timezone":"Asia/Tokyo"},
        "end":{"local":"2026-10-05T12:25:00","timezone":"Asia/Tokyo"}}}
}}
```

支持current普通活动、route和transport主Item的title/purpose/notes/timing/participants；clear仍仅purpose/notes。把时间恢复未知应set.timing为unknown。timing整对象替换，若只传start，旧end不会隐式保留。

主Item与所有内层对象身份不变。改Item标题不联动Route/Journey主体标题；改参与范围不生成逐段确认事实。plan.update 不改Leg时间、班次、Stop停留、Segment耗时、Day归属、来源基线或已存在声明；这些有自己的有界动作。改到另一天不等于日归属或票券同步修改。原文总时间含拍照等停留时，不按比例分到各段。

本次只保存明确输入，不新增通用排程或现实可行性判断。1.0 会检查有限起止顺序、约束与接续buffer，但不能据valid=true宣称交通可执行。compose顶层 `timing={"kind":"derived"}` 可自动指向本次新建的Journey/Route；已有复杂规范结构的领域Ref兼容输入仍不会被当作普通handle自动改写。

## 只修改某次停留或某一段

```python
{"method": "route.edit", "args": {
    "target": walk_item,
    "edits": [
        {"action": "set_stop", "target": return_stop, "set": {"dwell_minutes": 30}},
        {"action": "set_segment", "target": return_segment, "set": {"duration_minutes": 45}}
    ]
}}
```

set_stop 可 set/clear purpose、dwell_minutes、notes、`encounter_kind`；clear purpose 恢复缺失占位，clear `encounter_kind` 则移除字段、恢复未知。set_segment 可 set/clear duration_minutes、distance_m、path、notes。clear 是字段名列表，与 set 同一字段不能混用，也不能用 null 表示清除。所有修改需属于 target 这条路线，否则整批拒绝。

保留地点、安排、stop、segment 身份和未涉及的信息；相同值返回 no_change。暂不插入/删除/重排，不改地点或交通方式，不处理已确认票券。变更安排需要未来明确的另一类动作，不能偷偷作为资料修正执行。

## 自有车辆与驾驶段

，来源明确为自有车辆时使用 `vehicle.record_owned` 建立一次 VehicleUse 身份。车辆名称、车牌均非必填；只有来源明确时才填写 category、actual_vehicle、drivers、requirements 或 notes。

```python
{"method": "vehicle.record_owned", "as": "blue_car", "args": {
    "category": "电动车", "actual_vehicle": "蓝车"
}}
{"method": "journey.compose", "as": "outbound", "args": {
    "day": day_one, "title": "前往游客中心",
    "legs": [{"key": "drive", "mode": "driving",
              "from": home, "to": visitor_center,
              "vehicle": {"local": "blue_car"}}],
    "connections": []
}}
```

明确驾驶者时，drivers 是同一 Trip 的非空、去重 member handle 列表；未知时省略，不传空数组。requirements 只保存原文明示的非空文字，不追加驾驶资格、能源或容量规则。`source_kind` 固定为 owned；本入口不创建 ServiceUse、Reservation、Cost、停车或充电记录。

另一个已经存在的 independent driving Leg 可后补同一车辆：

```python
{"method": "journey.edit", "args": {
    "target": next_day_journey_item,
    "edits": [{"action": "bind_owned_vehicle",
               "target": next_day_driving_leg,
               "vehicle": blue_car}]
}}
```

Leg 必须属于 target Journey，mode 必须是 driving，movement 必须是 independent，vehicle 必须是 owned。同值重绑为 no_change；从未知后补明确车辆保留 Leg 身份。已有不同 vehicle 时返回 `VEHICLE_REPLACEMENT_REQUIRED`，不能用资料补录冒充执行替换。Leg、Journey 或所属 Item 上已有的 现有 movement 执行事实保护会在写入前以 `PLAN_TIME_CHANGE_BLOCKED` 原子拒绝；不相关 Task 不阻挡。

同一辆车用于多个驾驶段时复用同一 handle。walking、taxi、bus 或 scheduled Leg 不使用此入口。省略的驾驶者、电量、燃油、充电、停车及补能费用继续未知；完整租赁、车辆替换与能源跟踪仍不支持，可从 capabilities.unsupported 读取边界。

## 地图路径

### 示意线

```python
{"method": "path.add_schematic", "as": "line", "args": {
    "coordinate_system": "WGS84", "mode": "walking",
    "parts": [[{"lat": 36.25, "lon": 137.60}, {"lat": 36.251, "lon": 137.602}]],
    "notes": "虚构示意坐标，不能用于导航"
}}
```

本入口只创建 schematic，并要求明确 WGS84。不做坐标系转换或道路寻路。parts 是非空列表，每部分至少两个 {lat,lon} 点；多部分之间保持断开，不插线。lat 范围 -90 至 90，lon -180 至 180。

在 segment 或 leg 的 path 参数引用回执 primary，或同批 {"local":"line"}。path 的 mode 必须与该段一致；other 的 mode_label 也须一致。只有原文/资料给出几何时才录入，不能把示意线冒充真实步道、导航结果或 GPS 轨迹。

几何、原文距离和耗时是独立资料。绑定或替换示意线不会重算距离/时间；如果新的资料同时否定旧估算，调用方必须显式 set/clear 对应字段。不支持原位修改共享 Path；可建立新的示意线，再只更新目标段的 path。没有几何的段保留未知，不补直线或虚构 POI 经纬度。接口不检查几何是否贴合端点或是否真实可走。

校验仅涉及结构、身份、顺序及所述局部规则，仍不证明真实行程可执行或网页已实现地图渲染。

### 明确来源的记录路径

`path.record` 只接受 `observed_track`、`provider_route`、`authored_route`。前两种必须传公开 Source handle；Source 的 kind、notes 与操作 origin 原样保留其材料性质。合成 Source 可以测试承接能力，但不会因此成为现实 GPS 观测或道路核验。`authored_route` 可以没有外部 Source，它仍只是人工绘制，不证明道路存在或可以通行。示意线继续使用 `path.add_schematic`，不能换一个 kind 将示意坐标提升为记录轨迹。

```python
{"method": "source.record", "as": "track_source", "args": {
    "kind": "synthetic_fixture", "title": "完全合成的路径材料",
    "notes": "接口测试材料，不是现实GPS观测或道路核验"
}}
{"method": "path.record", "as": "trail_track", "args": {
    "kind": "observed_track", "coordinate_system": "WGS84",
    "mode": "other", "mode_label": "hiking", "source": {"local": "track_source"},
    "parts": [[
        {"lat": 35.100000, "lon": 138.100000},
        {"lat": 35.105000, "lon": 138.106000},
        {"lat": 35.110000, "lon": 138.112000}
    ]],
    "notes": "仅覆盖南步道口到山脊"
}}
```

`coordinate_system` 必须显式为 WGS84；不转换其他 CRS，也不能只改标签。每个 part 至少两点，多个 part 保持断开，缺段不补线。一个 Path 只有一个 `mode`；`other` 必须给 `mode_label`。普通 walking 与 `other`＋`hiking` 保持不同，混合路线按各自 Segment/Leg 分别绑定。绑定同时比较 mode 与 mode_label，不从几何端点修改 Place/AccessPoint，也不声称这些端点之间可达。

`distance_m` 与 `distance_basis` 必须成对提供，缺少明确距离时两者都省略；实现不会根据顶点计算直线或道路距离。`generated_at` 只在输入材料明确给出时传入，不自动填写当前时间。路径不会推导 Segment duration、Leg timing、Route/Item总时间或费用。点序按输入保存；当前没有 reverse 参数，也不会擅自反转。

Path 新记录不可变。几何修订应创建新 Path，再显式重绑目标使用者，旧 Path 保留。Route 的 inline Segment 沿用 `route.edit`：

```python
{"method": "route.edit", "args": {
    "target": route_item,
    "edits": [{"action": "set_segment", "target": trail_segment,
               "set": {"path": trail_track}}]
}}
```

Journey 用所属 Leg handle 明确绑定或清除：

```python
{"method": "journey.edit", "args": {
    "target": journey_item,
    "edits": [{"action": "set_leg_path", "target": hiking_leg,
               "path": trail_track}]
}}
{"method": "journey.edit", "args": {
    "target": journey_item,
    "edits": [{"action": "clear_leg_path", "target": hiking_leg}]
}}
```

这两个动作保留 Item、Journey、Leg、端点、顺序、Service 和 timing。Leg 必须属于 target Journey；Route 的 Segment 也必须属于 target Route。已采用的 confirmation/observation Claim 若精确保护该 Leg 或 Segment 的 `path_ref`，更换或清除会以 `PLAN_PATH_CHANGE_BLOCKED` 原子拒绝并返回 blocker refs；同值重绑仍是 no_change。没有 `path_ref` Claim 的 done Task 不会仅因补地图线而阻挡。所有动作继续遵守整批原子与 request_id 重放规则，失败不留下新 Path，重放成功请求不重复创建。

## 给某次停留或某段耗时保留“预计”及原句

新建和 route.edit 的 dwell_minutes / duration_minutes 均支持以下丰富输入（需 1.0）：

```python
{"key": "bridge-back", "place": bridge,
 "dwell_minutes": {"minutes": 20, "basis": "estimate", "statement": "返程在河童桥预计停留20分钟"}}

{"action": "set_segment", "target": return_segment, "set": {
    "duration_minutes": {"minutes": 45, "basis": "estimate", "statement": "返程步行修正为预计45分钟"}
}}
```

minutes 同样接受非负数或 [最小, 最大]。丰富输入三个键 minutes、basis、statement 都必填；原句要由调用方提供，不补写成引用。标量和区间的旧写法继续支持，不能仅凭这些数字推断“预计”或“已确认”。

basis 可用 estimate、user_statement、official、observation、confirmation、synthetic_fixture、other，与现有依据类型一致。“预计”用 estimate，statement 保存相应原句。basis 是本条声明的依据类型：official 不意味着精确，confirmation 也不会新建预订、付款或实际执行记录。当前单个 basis 不能同时完整结构化“官网来源”和“预计性质”；可优先用 estimate 保存预计属性、在原句里照实保留来源描述，不宣称已实现来源文件快照或联网核验。

工具自动生成 Claim，指向特定 Route 下某次 Stop 的 dwell 或某个 Segment 的 duration，同时保存标准化的分钟范围、basis、statement、disposition=adopted。不会挂到复用的 Place 或整个 Item 上。操作回执 parts.duration_evidence 返回本次新建声明的 target（局部 handle）、field 和 claim handle；未新建则不必有该列表。同批两个不同途经点即使引用相同 Place，也分别拥有自己的声明。

更新规则：

- 不改该字段，或者只给出与原来相同的数值，保留当前声明；35 与 [35,35] 算相同。
- 改值却没有提供新依据：旧 adopted 变为 superseded，新值的依据性质未记录，不继承原来的 estimate。
- 清空数值：旧 adopted 变为 superseded。以后重设旧数值也不会自动复活旧声明。
- 提供新依据：明确采用新的当前声明，旧声明留作历史。相同数值、basis 和 statement 的重复输入复用现有声明，不制造重复历史。
- superseded 只表示不再作为当前字段的说明，不表示旧来源被证伪。旧值和原句保留。
- 多条 adopted 冲突不会默认取最后一条；输入不合法或后续操作失败时，数值与依据一起回滚。

**读取和网页展示契约：**在导出包 claims 中，用完整 target 匹配：object_ref 是所属 Route；local_ref 的 owner 与它相同，kind/id 对应那一次 stop 或 segment；field 分别为 dwell/duration。只有 disposition=adopted、value 与当前字段一致的唯一声明可用于当前展示。其 basis=estimate 才能据此标“预计”；其他 basis 或没有声明都不能自动标“已确认”。缺失依据时显示“依据性质未记录”，多个当前声明或值不匹配属于不一致，不能按数组顺序选一个。

route.compose / route.edit 的顶层 origin 仍只是整体操作说明。它不替代上述逐字段输入，也不会自动成为所有途经点、区段的耗时依据。本入口仅覆盖本次路线的停留与区段耗时，不是任意 Claim 写入器，也不把历史观测值当作本次实际行驶记录。

坐标契约可由 `read_workspace(state)["capabilities"]["coordinate_inputs"]` 的 `path.add_schematic` 和 `path.record` 发现。缺坐标系、未知占位值或非 WGS84 输入会返回具体字段及 repair 提示，不自动转换，也不能只改标签冒充转换。未知时暂不创建 Path，保留路线安排与原始资料即可。
