# 地点地址和坐标输入

沿用 [CALLER_GUIDE](CALLER_GUIDE.md) 的批次和 handle 约定。这里说明 Place 与 AccessPoint 共用的 Location 输入；入口方法另见[入口指南](ACCESS_POINT_GUIDE.md)。以下数字、地址均为演示，不能作为旅行事实使用。

## 先读取输入要求

坐标系是写入 location 的必需信息，不是每个 Place 都必须有坐标。先建立地点、只补地址都可以。不要为满足必填项而编造坐标系。

即使尚未创建 Trip，Agent 也能通过公开 read 发现这些要求：

```python
view = read_workspace(state)
contracts = view["capabilities"]["coordinate_inputs"]
location_contract = contracts["place.update.set.location"]
access_point_create_contract = contracts["access_point.add.location"]
access_point_update_contract = contracts["access_point.update.set.location"]
schematic_path_contract = contracts["path.add_schematic"]
recorded_path_contract = contracts["path.record"]
```

前三者列出必填字段、命名 lat/lon 顺序、整体替换规则和未知时的处理；后两项明确示意及记录 Path 都只接受 WGS84，记录 Path 还公开 kind 与 Source 要求。它们都没有默认坐标系、不做转换、不核验声明真伪。AccessPoint 的创建与更新详见[入口指南](ACCESS_POINT_GUIDE.md)，Path 记录与绑定详见[路线指南](MOVEMENT_GUIDE.md)。空工作区可读能力说明，不表示可跳过 trip.define 直接写入。

新提交的 location 缺少、空白或无效类型的 coordinate_system 会得到 `COORDINATE_SYSTEM_REQUIRED`；明确的 `unknown`、`TBD`、`待核实`、`未知` 等占位标签会得到 `COORDINATE_SYSTEM_UNCONFIRMED`。大小写与首尾空白不使占位标签变有效。其他缺失字段返回 `LOCATION_FIELDS_REQUIRED`，附相应 field_guidance；契约也列出 precision 的允许值和具体含义。

错误的 `parameter` 定位到 `set.location.coordinate_system` 或 location，附 `missing_fields`（适用时）、`repair.when_known` / `repair.when_unknown` 和指南路径。例如缺坐标系时，先从原资料或该数据提供方的格式声明取得依据；若仍未知，撤掉本次 location 输入，把原值、顺序、来源及待核实原因留在 notes，再重提修正后的整批请求。不要因坐标失败而丢掉已经明确的地址。

非占位的字符串仍只是调用方声明，不代表工具认识或验证了该坐标系。Place 可以保存明确的非 WGS84 声明；不能把这种坐标原样换标签用于 path.add_schematic 或 path.record。已有工作区不迁移、不回填；只更新地址/备注不重新判定旧定位。

## 地址不依赖坐标

`place.add` 先建立地点，再用回执中的地点 handle 更新。`address` 是非空字符串，不是拆分省市的对象；原文只有地址时可以单独保存地址，不必先查到坐标。

```python
{"method": "place.update", "args": {
    "target": place,
    "set": {"address": "原文提供的完整地址", "timezone": "Asia/Tokyo"}
}}
```

这里的 `place` 是 `receipt["aliases"]["place"]` 或读取对象后组装的 `{"handle": "..."}`。同批前面的 `place.add` 使用 `as="place"` 时，可写 `target={"local":"place"}`。没有地址、时区就省略对应字段；不从旅行默认时区推断地点时区。

## 完整坐标对象

假设原资料明确声明坐标是 WGS84、定位仅为近似点，并给出 `latlng=[35.5, 139.5]`（**纬度在前，经度在后**），可写：

```python
raw_latlng = [35.5, 139.5]
operation = {"method": "place.update", "args": {
    "target": place,
    "set": {"location": {
        "lat": raw_latlng[0],
        "lon": raw_latlng[1],
        "coordinate_system": "WGS84",
        "precision": "approximate",
        "notes": "原文声明 WGS84；此点仅用于近似展示，入口待核实"
    }}
}}
```

本次旧攻略的 `latlng` 顺序是纬度、经度。其他输入必须分别确认；不要按数组字段名猜顺序。本方法只接收 `lat` / `lon` 命名字段，不接受 `latlng`、`lng` 或 GeoJSON 数组。地图路线的 GeoJSON 坐标顺序不能直接套用到这里。

| location 字段 | 输入规则 |
|---|---|
| `lat` | 必填，数字，范围 -90 到 90，包含端点 |
| `lon` | 必填，数字，范围 -180 到 180，包含端点 |
| `coordinate_system` | 必填，非空字符串；按资料声明填写，例如 `WGS84`，工具不转换或核验坐标系 |
| `precision` | 必填，见下表；描述点代表的位置范围，不是小数位数 |
| `notes` | 可选，非空字符串；保留原始定位说明、误差或使用限制 |
| `source_ref` | 可选，已有 Source 的领域引用，详见下节 |

不能填其他字段、数字字符串、布尔值、null、NaN 或 Infinity。四个必填字段必须一起提供；地址可有可无。

| precision | 使用条件 |
|---|---|
| `entrance` | 有依据表明点代表具体入口 |
| `building` | 有依据表明点代表建筑物，未细化到入口 |
| `parcel` | 有依据表明点代表地块或院落范围 |
| `area` | 有依据表明点代表区域级位置 |
| `approximate` | 仅作为近似点使用，不声称建筑或入口精度 |

小数位多、地图 URL 能打开或地点属于某国，都不能证明坐标系或入口精度。资料没说明定位精度但坐标系已明确时，可以保守使用 `approximate`，同时在 notes 明写“原文未说明定位精度，仅按近似点使用”，不能伪装成原文的精度声明。

**坐标系未知时，不要为了通过校验填 WGS84。** 当前接口没有具有明确语义的“待确认坐标”类型。虽然底层 Schema 允许任意非空 coordinate_system 字符串，公开作者入口会拒绝明确的未知占位标签；通过校验仍不代表地图能正确投影。先保留原数值和问题：

```python
{"method": "place.update", "args": {
    "target": place,
    "set": {"address": "原文地址"},
    "append_note": "原文 latlng=[35.5,139.5]，纬度在前；坐标系未说明，尚未录入 location。"
}}
```

如果还需要在导出中保留一条明确的原材料声明，可在同一个操作上加公开的 origin：

```python
{"method":"place.update", "args":{
    "target":place,
    "append_note":"原文 latlng=[35.5,139.5]，纬度在前；坐标系未说明，未采用为 location。"
}, "origin":{
    "basis":"other",
    "statement":"原 JSON $.places[0].latlng=[35.5,139.5]；坐标系待核实。"
}}
```

这会导出关联 Place 的 Claim（字段 authoring_statement）。它仍是原文陈述：没有结构化坐标数组、精确 source_ref 或机器可用的待核实坐标状态，不等于定位已采用。不要仅为了增加 Claim 数重复追加同样说明；先公开 read 检查已保留的内容。原文件 snapshot 可另由 source.register 保管，但快照全文不会进入领域导出。

这属于叙述性保留，不能计作坐标已结构化。如果地点已有可信 location，仅新增未知资料时应保留旧值并说明新资料问题；只有明确撤回旧定位时才 `clear=["location"]`。工具不会联网地理编码、自动换坐标系、推断入口或检测范围内的经纬度颠倒。

## 可选来源引用

`location.source_ref` 是一个嵌套领域引用，当前 `place.update` 不会将它内部的 handle 自动转换。先按 [SOURCE_GUIDE](SOURCE_GUIDE.md) 登记来源并成功提交，拿到 Source handle，再从公开读取结果取得 ID：

```python
source_handle = receipt["aliases"]["source"]
source = next(obj for obj in read_workspace(state)["objects"]
              if obj["handle"] == source_handle["handle"] and obj["type"] == "source")
location = {
    "lat": 35.5, "lon": 139.5,
    "coordinate_system": "WGS84", "precision": "approximate",
    "source_ref": {"type": "source", "id": source["record"]["id"]}
}
operation = {"method": "place.update", "args": {"target": place, "set": {"location": location}}}
```

不要自己编 ID，也不要在这里传 `{"handle":...}` 或 `{"local":...}`。source_ref 指向已登记来源，不等于坐标经外部核验；也不建立 `source.duration` 那样的字段刷新绑定。来源可省略，但不要谎称未知来源已核验。完整原文留在工作区，领域导出保留 Source 和该引用，不包含快照全文。

## 更新与撤回

`set.address` 替换完整地址字符串；`set.location` 替换整个 location 对象，不合并子字段。因此单写 `{"location":{"lat":35.6}}` 会失败，而不是保留旧经度。改坐标时先从 `read_workspace` 读取当前完整对象，保留仍成立的字段，再明确修改；旧来源或精度不再成立时须一起调整，不能机械复制成新点的依据。

省略 address/location 保持旧值；`clear=["address"]` 或 `clear=["location"]` 明确移除该字段。null、空字符串或空对象不是清空方式。清空 location 不会删除地点，也不会修改其安排引用或地址。

非法坐标、缺字段或不存在的 source_ref 返回 `AuthoringError`，整批不提交，包括本批之前合法的修改。具体校验定位可读 `error.as_dict()`。`check.valid=true` 只证明现有结构和引用检查通过，不证明地址、定位精度、坐标系或现场入口正确。
