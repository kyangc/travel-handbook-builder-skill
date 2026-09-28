# 本日主要天气地点

每个 Day 可明确选择一个已有 Place 或真实 AccessPoint，使用当前 workspace handle：

- 新增：`day.add` 的 `weather_location={"handle":"…"}`。
- 修改：`day.update` 的 `set.weather_location={"handle":"…"}`。
- 清除：`day.update` 的 `clear=["weather_location"]`。

选择导出为可选 `Day.weather_location_ref`，仅接受同包 `place/access_point`；裸 Ref、null、其他对象类型不能作为作者入口。清除只影响天气关系。不要从住宿、第一景点、地图中心、交通终点或浏览器位置自动选择；没有用户明确选择时省略。天气地点无需成为 Item 或推荐。不要为天气坐标虚构 AccessPoint；直接选入口时仅使用入口自己的坐标。

地点可暂缺坐标，仍是合法初稿。浏览器仅查询明确 WGS84 坐标与 Day 日期/时区；已知地点时区不同会提示确认，不更改日程。在线天气来自浏览器直接请求 Open-Meteo，不是 canonical 事实；不得把预报值、供应商/更新时间写入攻略、Source/Claim 或作者 state。

只有用户手动保存离线攻略才保存天气快照，绑定攻略版本、Day 身份和实际查询输入。远期、过去、缺资料或供应商失败不阻止完整攻略离线保存；反馈必须区分天气完整/部分/未保存。未选择天气的旧 `1.0` 包保持有效；带字段包需支持天气的发行版本（`0.3.7` 起），旧严格验证器可能拒绝新字段。

Open-Meteo 免费 API 的非商业使用及 CC BY 4.0 署名适用；供应商接收请求坐标与 IP。页面来源入口保留署名；公共包随前端带相同适配器，不需要 Key、后台代理或定时任务。
