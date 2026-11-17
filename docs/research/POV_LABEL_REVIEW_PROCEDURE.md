# POV 检测预标注复核流程

日期：2026-11-17  
对象：`datasets/pov_detection_v1`  
目标：把 old 模型 prelabels 修正为可用于 test 评估的人工标签

---

## 1. 复核范围

必须完成：

```text
test: 80 帧（4 sessions × 20 帧）
```

建议完成：

```text
train/val 抽查 64 帧（每 session 4 帧）
```

当前 test 预标注统计：

```text
images 80
boxes 84
head 26
body 58
empty 17
```

复核目录已准备：

```text
datasets/pov_detection_v1/review_test/
├── images/       80 张
├── labels/       80 个 YOLO prelabel
├── classes.txt   enemy_head / enemy_body
└── review_checklist.csv
```

contact sheet：

```text
datasets/pov_detection_v1/review_contact_sheet.jpg
```

---

## 2. 标注规则

### head

- 标注头部/头盔整体；
- 不把脖子、肩膀算进 head；
- 目标只露出部分头时，标可见部分；
- 目标太小、无法确认是头时，不标；
- 不要给 body 框重复标 head。

### body

- 标注躯干和可见四肢；
- 不把纯头部算作 body；
- 目标被遮挡时，只标可见部分；
- 完全不可见、死亡模型、队友、UI 元素不标；
- 一个目标同一类只保留一个框。

### 空帧

- 画面没有可标注目标：labels 文件为空；
- 不要为了“有标签”强行加框。

### 边界

- 框尽量贴合目标外接矩形；
- 不要求像素级精确，但不能明显偏离目标；
- 目标在画面边缘时，保留可见部分；
- 不标注准星、HUD、武器、地图装饰。

---

## 3. 工具

### 推荐：Label Studio

你已经用过 Label Studio，建议直接用这个流程。

#### 3.1 启动

```powershell
.\.venv\Scripts\python.exe -m pip install label-studio
.\.venv\Scripts\label-studio.exe start
```

打开：

```text
http://localhost:8080
```

#### 3.2 创建项目

1. Create Project；
2. 名称：`POV Detection QC`；
3. Labeling Setup 选择 **Object Detection with RectangleLabels**；
4. 或直接粘贴：

```text
configs/labelstudio_pov.xml
```

配置内容：

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true"/>
  <RectangleLabels name="label" toName="image">
    <Label value="enemy_head" background="#00FF00"/>
    <Label value="enemy_body" background="#FFA500"/>
  </RectangleLabels>
</View>
```

5. Data Import 上传：

```text
datasets/pov_detection_v1/review_test/images/
```

80 张 test 图。

6. 不需要导入预标注；按下面的规则手动画框即可。
   预标注只作为参考，不要直接提交未检查的预标注。

#### 3.3 标注

每张图：

- 有 head → 画 `enemy_head`；
- 有身体 → 画 `enemy_body`；
- 空帧 → 不画；
- 删除误框/重复框；
- 保存并提交。

Label Studio 支持键盘快捷键，按你之前的使用习惯即可。

#### 3.4 导出

标注完成后：

```text
Export -> JSON
```

保存为：

```text
datasets/pov_detection_v1/labelstudio_export.json
```

> 不要导出 YOLO；JSON 更容易和图片文件名精确对应。

#### 3.5 转成 YOLO 并校验

```powershell
.\.venv\Scripts\python.exe tools\labelstudio_to_yolo.py `
  --export datasets\pov_detection_v1\labelstudio_export.json `
  --output-dir datasets\pov_detection_v1\review_test\labels_ls `
  --summary datasets\pov_detection_v1\review_test\labelstudio_conversion.json
```

然后校验：

```powershell
.\.venv\Scripts\python.exe tools\validate_pov_labels.py `
  --images datasets\pov_detection_v1\images\test `
  --labels datasets\pov_detection_v1\review_test\labels_ls `
  --output datasets\pov_detection_v1\review_test\labels_ls_qc.json
```

必须 `ok: true`，并且 80 个标签文件。

#### 3.6 替换 test 标签

先备份预标注：

```powershell
Copy-Item `
  datasets\pov_detection_v1\labels\test `
  datasets\pov_detection_v1\labels\test_prelabels_backup `
  -Recurse
```

再复制 Label Studio 结果：

```powershell
Copy-Item `
  datasets\pov_detection_v1\review_test\labels_ls\*.txt `
  datasets\pov_detection_v1\labels\test\ `
  -Force
```

### 备选：LabelImg

当前环境未安装，可在项目虚拟环境安装：

```powershell
.\.venv\Scripts\python.exe -m pip install labelImg
```

启动：

```powershell
.\.venv\Scripts\labelImg.exe `
  datasets\pov_detection_v1\review_test\images `
  datasets\pov_detection_v1\review_test\classes.txt `
  datasets\pov_detection_v1\review_test\labels
```

关键设置：

1. 保存格式切换为 **YOLO**；
2. `classes.txt` 顺序必须是：
   - 0 `enemy_head`
   - 1 `enemy_body`
3. 打开 `review_test/images`；
4. 保存目录设为 `review_test/labels`；
5. 每张修改后 `Ctrl+S`。

常用快捷键：

```text
W        新建框
A / D    上一张 / 下一张
Delete   删除选中框
Ctrl+S   保存
Ctrl+Z   撤销
```

### 备选

- CVAT：上传 `review_test/images`，导出 YOLO 1.1；
- Label Studio：YOLO export；
- 其他支持 YOLO 的标注工具。

无论用什么工具，最终必须得到：

```text
review_test/labels/*.txt
```

每行：

```text
class_id cx cy bw bh
```

---

## 4. 逐帧流程

建议按 session 分批，每批 20 帧，避免疲劳。

### 每张图

1. 看画面中是否有目标；
2. 检查 head 框：
   - 有头但漏框 → 补；
   - head 框套在身体上 → 改；
   - 误报 → 删；
3. 检查 body 框：
   - 有身体但漏框 → 补；
   - head 被标成 body → 改 class；
   - 误报 → 删；
4. 空帧确认没有目标；
5. `Ctrl+S` 保存；
6. 在 `review_checklist.csv` 标记：
   - `reviewed=yes`
   - `head_ok=yes/no`
   - `body_ok=yes/no`
   - `empty_ok=yes/no`
   - `notes` 记录问题。

### 每批结束

抽查 5 张：

- 框是否贴合；
- class 是否混淆；
- 是否有重复框；
- 是否有漏标。

---

## 5. 复核后校验

先备份原 prelabel：

```powershell
Copy-Item `
  datasets\pov_detection_v1\labels\test `
  datasets\pov_detection_v1\labels\test_prelabels_backup `
  -Recurse
```

把复核后的 labels 替换 test：

```powershell
Copy-Item `
  datasets\pov_detection_v1\review_test\labels\*.txt `
  datasets\pov_detection_v1\labels\test\ `
  -Force
```

运行格式校验：

```powershell
.\.venv\Scripts\python.exe tools\validate_pov_labels.py `
  --images datasets\pov_detection_v1\images\test `
  --labels datasets\pov_detection_v1\labels\test `
  --output datasets\pov_detection_v1\reviewed_test_qc.json
```

必须：

```text
ok: true
images == labels == 80
missing_labels: []
missing_images: []
errors: []
```

---

## 6. 验收标准

必须全部满足：

```text
[ ] 80/80 test 帧至少打开并检查
[ ] 每张都执行了保存
[ ] head/body 框无明显错类
[ ] 空帧已确认
[ ] validate_pov_labels ok=true
[ ] reviewed_test_qc.json 已生成
```

建议：

```text
[ ] 抽查 64 张 train/val
[ ] 记录修改数量
[ ] 保留 prelabel 备份
```

---

## 7. 时间估计

```text
80 帧 test：约 1.5–3 小时
64 帧 train/val 抽查：约 1–1.5 小时
```

不要一次做完 80 张；分 4 批，每批 20 张。

---

## 8. 完成后

把以下内容保留在本地：

```text
datasets/pov_detection_v1/labels/test/
datasets/pov_detection_v1/reviewed_test_qc.json
datasets/pov_detection_v1/review_test/review_checklist.csv
```

然后告诉我复核完成。下一步：

1. 训练 POV YOLOv8n；
2. 对比 old/new/POV；
3. 在 test 上报告 mAP50、head recall、per-map；
4. 只有结果成立才写论文。

---

## 9. 注意

- **不要**把 prelabel 直接当人工真值；
- **不要**改 `images/test`；
- **不要**覆盖 `labels/test_prelabels_backup`；
- **不要**在 test 复核完成前报告检测指标；
- 不确定的框标 `notes`，不要猜。