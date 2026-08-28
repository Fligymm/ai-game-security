from ultralytics import YOLO

# 1. 直接加载之前已导出的 best.onnx 模型
model = YOLO(r"runs\detect\cs2_detection_v1\weights\best.onnx", task="detect")

# 2. 在 GPU (device=0) 上进行推理测试
results = model(r"datasets\cs2_custom\val\images", device=0, conf=0.5)

# 3. 打印第一张图片的推理延迟
print("ONNX 模型 GPU 推理成功！")
print("单帧处理耗时:", results[0].speed)
