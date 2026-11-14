# Pilot 标注流程（Label Studio 1.23）

## 0. 这次要标什么

- 输入：`annotation/images/`，90 张 320×320 JPEG。
- 分布：3 个 scene 各 30 张；60 张有模型选中目标，30 张没有。
- 输出：`annotation/labels/*.txt`，YOLO 格式，文件名与图片同名。
- 类别固定，沿用之前训练集：

| 类别名 | class id | 颜色 |
|---|---:|---|
| `enemy_head` | 0 | 红 |
| `enemy_body` | 1 | 蓝 |

> 这是一次**独立人工标注**。`manifest.json` 里的 `model_detections` 只是参考，不要照抄；否则测出来的是模型和它自己的一致性，不是检测精度。

## 1. 启动 Label Studio

在项目根目录执行：

```powershell
cd D:\AI_Security\ai-game-security
.\.venv\Scripts\label-studio.exe start --port 8080
```

浏览器打开：

```text
http://localhost:8080
```

如果 8080 已被占用，换 8081：

```powershell
.\.venv\Scripts\label-studio.exe start --port 8081
```

> `label-studio.exe --version` 在 1.23 也会启动服务，不要用它来查版本；版本已在项目环境确认是 1.23.0。

## 2. 创建项目

1. 用你之前训练模型时的 Label Studio 账号登录。
2. `Create Project`。
3. 项目名建议：

```text
CS2 Pilot 1920x1080 v0
```

4. 进入 `Labeling Setup`。
5. 选择 `Custom template`，把下面 XML 完整粘贴进去，保存：

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>
  <RectangleLabels name="label" toName="image">
    <Label value="enemy_head" background="#FF3B30"/>
    <Label value="enemy_body" background="#007AFF"/>
  </RectangleLabels>
</View>
```

也可以直接复制同目录的 [`label_config.xml`](label_config.xml)。

> 类别名必须精确为 `enemy_head` / `enemy_body`，不要写成 `head`、`body` 或中文；否则后面转换会报错。

## 3. 导入 90 张图

最简单、最稳的方式是直接上传：

1. 项目页 -> `Import`。
2. 选择 `Upload Files`。
3. 进入：

```text
D:\AI_Security\ai-game-security\runs\pilot_20261114_1920x1080\annotation\images
```

4. 全选 90 张 `.jpg`，上传。
5. 等待 90 个 task 全部出现。

不要一张一张上传；文件名已经唯一，批量上传不会冲突：

```text
static_target__realtime_cs2_agent_20261114_151602__f000597.jpg
slow_strafe__realtime_cs2_agent_20261114_152900__f001234.jpg
fast_strafe__realtime_cs2_agent_20261114_154010__f000765.jpg
```

如果之前已经用 Local Storage 配过 Label Studio，也可以继续用本地存储；但这次 90 张图很小，**Upload Files 更省事**，也避免路径权限问题。

## 4. 标注规则

每张图都要人工检查，按下面顺序：

1. 选择 `Rectangle` 工具。
2. 先选 `enemy_head`（红色），框住每个可见头部；框要贴紧，不要带太多脖子/背景。
3. 再选 `enemy_body`（蓝色），框住每个可见身体；头和身体分开两个框，不要合并。
4. 每个可见目标都要标，**包括模型没有选中的目标**。
5. 不要框准星、HUD、血条、武器、地图元素。
6. 目标被部分遮挡但范围可推断时，按可见范围标；完全不可见/无法推断时不标。
7. 图中没有目标时，直接提交空标注，这是有效负样本。
8. 每张图完成后点 `Submit` / `Update`，不要只保存草稿。

精度建议：

- 320×320 图比较小，打开 `zoom`，用 2×–3× 看边缘。
- 头部框和身体框允许少量重叠，但不要重复框同一个目标。
- 先标 `static_target`，再标 `slow_strafe`，最后 `fast_strafe`；fast 运动模糊更多，放最后更稳。
- 如果一张图目标太多、实在无法判断，先跳过并在项目备注里记文件名，不要猜。

## 5. 进度检查

Label Studio 左侧 task 列表应显示：

```text
90 tasks
Completed: 90 / 90
```

至少确认：

- 没有 `Cancelled` / `Skipped` 的 task；
- 每个 task 都有 `Submit`，不是 `Draft`；
- 60 张“有模型选中”的图，绝大多数应有至少一个框；如果某张实际没有目标，保留空标注，这是模型误报，应该被记录，不要为了迎合模型硬画。

> **不要把空图按 `Skip`。** Label Studio 的 JSON 导出通常不会包含被 Skip 的 task；正确做法是打开空图后直接 `Submit` 一个无框标注。否则转换脚本会报 `N images have no Label Studio task`。

## 6. 导出 JSON

标注完成后：

1. 项目页 -> `Export`。
2. 选择 `JSON`（不要选 CSV，也不要选 YOLO）。
3. 勾选包含所有 task / annotations。
4. 下载后放到：

```text
D:\AI_Security\ai-game-security\runs\pilot_20261114_1920x1080\annotation\labelstudio_export.json
```

JSON 里每个 task 的 `annotations[0].result` 会包含 `rectanglelabels`、`x/y/width/height`（百分比）。

## 7. 转成 YOLO 标签

项目已经提供转换脚本：

```powershell
cd D:\AI_Security\ai-game-security

.\.venv\Scripts\python.exe tools\labelstudio_to_yolo.py `
  --export "runs\pilot_20261114_1920x1080\annotation\labelstudio_export.json" `
  --images-dir "runs\pilot_20261114_1920x1080\annotation\images" `
  --labels-dir "runs\pilot_20261114_1920x1080\annotation\labels"
```

成功时应看到：

```json
{
  "ok": true,
  "images": 90,
  "labeled_tasks": 90,
  "missing": [],
  "boxes": 200,
  "empty_labels": 10,
  "errors": [],
  "warnings": []
}
```

`boxes` 只是示例，实际以你的标注为准；关键看：

- `ok=true`
- `images=90`
- `labeled_tasks=90`
- `missing=[]`
- `errors=[]`

如果报 `no completed annotation`，说明还有 task 没 Submit；如果报 `image not found for task`，检查文件名是否被改。当前 Label Studio 上传后会加 8 位前缀，例如：

```text
75a8c6d2-fast_strafe__...__f000765.jpg
```

转换脚本已支持这种前缀匹配，不需要手动改名。

如果报 `N images have no Label Studio task`，通常是这些图在 Label Studio 里被 `Skip` 或没有 Submit，导出 JSON 时被省略。正确修复是回到项目，对这些空图 `Submit` 一个无框标注；不要用 `--allow-missing` 跳过人工确认。

## 8. 标注后的自检

转换完成后检查：

```powershell
Get-ChildItem "runs\pilot_20261114_1920x1080\annotation\labels" -Filter *.txt | Measure-Object
```

应为 90 个文件。再随机抽 5–10 张，用 Label Studio 或回放工具对照：

- 框是否贴紧；
- head/body 是否标反；
- 是否漏掉未选中的目标；
- 空图是否真的没有目标。

## 9. 交回什么

标注完成后只需要告诉我：

1. `annotation/labelstudio_export.json` 已导出；
2. 转换脚本的完整 JSON 输出（或 `ok=true`）；
3. 你标注时觉得最难的 3–5 张图（可选，便于错误分析）。

之后我会做：

- 标签格式/覆盖检查；
- 按 scene 统计框数、空图、类别分布；
- 用旧 `datasets/cs2_custom` 做 train/val，这 90 帧作为 **new-environment test**，不参与训练；
- 输出 per-scene precision/recall/mAP、空图误报、head/body 结果；
- 再决定是否重训模型。