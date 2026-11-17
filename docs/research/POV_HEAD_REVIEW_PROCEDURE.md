# POV 64 帧 Head 复核流程

日期：2026-11-17  
目的：补足 train/val 的 head 监督，再训练 POV 模型  
范围：**只标 head，不改 body 预标注**

---

## 1. 已准备好的数据

```text
datasets/pov_detection_v1/review_trainval_head/
├── images/                     64 张
├── classes.txt                 enemy_head
└── review_head_checklist.csv   64 行
```

分布：

```text
16 个 session
train 48 帧（12 sessions × 4）
val   16 帧（4 sessions × 4）
```

其中：

```text
56 帧 prelabel 有 head
8 帧 prelabel 无 head
```

复核目录只包含图片，不包含预标注；你直接从画面画 head 框。

---

## 2. Label Studio 项目

### 启动

```powershell
.\.venv\Scripts\python.exe -m pip install label-studio
.\.venv\Scripts\label-studio.exe start
```

打开：

```text
http://localhost:8080
```

### 配置

创建项目：

```text
POV Head QC 64
```

Labeling Setup 粘贴：

```text
configs/labelstudio_pov_head.xml
```

内容：

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true"/>
  <RectangleLabels name="label" toName="image">
    <Label value="enemy_head" background="#00FF00"/>
  </RectangleLabels>
</View>
```

Data Import 上传：

```text
datasets/pov_detection_v1/review_trainval_head/images/
```

只上传 64 张图，不要上传 test 的 80 张。

---

## 3. Head 标注规则

只画 `enemy_head`：

- 头部/头盔整体；
- 不把脖子、肩膀算进去；
- 部分可见时只标可见部分；
- 太小无法确认时不标；
- 一个目标只保留一个 head 框；
- 空帧不画；
- 不标 body、队友、死亡模型、UI、武器。

> 本流程只改 head；body 预标注会在合并时保留。

---

## 4. 逐帧复核

按 checklist 分批：

```text
每批 16 帧
4 批完成
预计 30–60 分钟
```

每张：

1. 看是否有 head；
2. 有 → 画 `enemy_head`；
3. 无 → 保持空；
4. 提交/保存；
5. 下一张。

建议先做 train 48 帧，再做 val 16 帧。

---

## 5. 导出

完成后：

```text
Export -> JSON
```

保存为：

```text
datasets/pov_detection_v1/review_trainval_head/labelstudio_head_export.json
```

必须导出 JSON，不要导出 YOLO。

---

## 6. 转 YOLO

```powershell
.\.venv\Scripts\python.exe tools\labelstudio_to_yolo.py `
  --export datasets\pov_detection_v1\review_trainval_head\labelstudio_head_export.json `
  --images datasets\pov_detection_v1\review_trainval_head\images `
  --output-dir datasets\pov_detection_v1\review_trainval_head\labels_ls `
  --summary datasets\pov_detection_v1\review_trainval_head\head_conversion.json
```

检查：

```text
ok: true
count: 64
missing: []
errors: []
```

---

## 7. 校验 head 标签

```powershell
.\.venv\Scripts\python.exe tools\validate_pov_labels.py `
  --images datasets\pov_detection_v1\review_trainval_head\images `
  --labels datasets\pov_detection_v1\review_trainval_head\labels_ls `
  --output datasets\pov_detection_v1\review_trainval_head\head_labels_qc.json
```

必须：

```text
ok: true
images == labels == 64
```

---

## 8. 合并到 train/val

先 dry-run：

```powershell
.\.venv\Scripts\python.exe tools\merge_pov_head_review.py `
  --review-labels datasets\pov_detection_v1\review_trainval_head\labels_ls
```

确认：

```text
ok: true
reviewed: 64
missing: []
```

再执行：

```powershell
.\.venv\Scripts\python.exe tools\merge_pov_head_review.py `
  --review-labels datasets\pov_detection_v1\review_trainval_head\labels_ls `
  --execute `
  --report datasets\pov_detection_v1\review_trainval_head\merge_report.json
```

合并逻辑：

```text
保留原 train/val 的 body (class 1)
替换/追加你复核的 head (class 0)
```

自动备份原标签到：

```text
labels/train_head_backup/
labels/val_head_backup/
```

---

## 9. 校验合并结果

```powershell
.\.venv\Scripts\python.exe tools\validate_pov_labels.py `
  --images datasets\pov_detection_v1\images\train `
  --labels datasets\pov_detection_v1\labels\train `
  --output datasets\pov_detection_v1\train_after_head_qc.json
```

```powershell
.\.venv\Scripts\python.exe tools\validate_pov_labels.py `
  --images datasets\pov_detection_v1\images\val `
  --labels datasets\pov_detection_v1\labels\val `
  --output datasets\pov_detection_v1\val_after_head_qc.json
```

两个都必须 `ok: true`。

---

## 10. 重训

```powershell
.\.venv\Scripts\python.exe tools\train_pov_detector.py `
  --execute `
  --name pov_ft_v2
```

训练完成后评估：

```powershell
.\.venv\Scripts\python.exe tools\eval_pov_detector.py `
  --models runs\detect\pov_ft_v2\weights\best.pt `
  --imgsz 1280 `
  --output runs\eval\pov_eval_test_v2.json
```

对比：

```text
old
pov_ft_v1-2
pov_ft_v2
```

重点看：

```text
head mAP50
head recall
body mAP50
```

---

## 11. 验收标准

```text
[ ] 64/64 帧已打开并提交
[ ] JSON 导出成功
[ ] labelstudio_to_yolo count=64, ok=true
[ ] head_labels_qc ok=true
[ ] merge dry-run ok=true, missing=[]
[ ] merge --execute 成功
[ ] train/val validate ok=true
[ ] 重训完成
[ ] test 评估完成
```

---

## 12. 当前不做什么

- 不改 test 标签；
- 不改 body 预标注；
- 不覆盖 old deployment default；
- 不把 POV 模型设为默认；
- 不在未重训前宣称 head 提升。