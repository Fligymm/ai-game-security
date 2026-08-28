from ultralytics import YOLO

# 1. 加载 ONNX 模型（也可换为 best.pt）
model = YOLO(r"runs\detect\cs2_detection_v1\weights\best.onnx", task="detect")

# 2. 替换为你的本地视频路径
video_path = r"D:\AI_Security\ai-game-security\test_video.mp4"

# 3. 执行视频推理与画框保存
results = model.predict(
    source=video_path,
    device=0,  # 使用 RTX 4070 SUPER GPU
    conf=0.5,  # 置信度阈值（低于 50% 的框不显示）
    save=True,  # 保存处理后的视频
    project="runs/predict",  # 输出根目录
    name="video_test_results",  # 输出子文件夹
    exist_ok=True,  # 允许覆盖已有文件夹
)

print("视频推理完成！处理后的视频已保存到 runs/predict/video_test_results 目录中。")
