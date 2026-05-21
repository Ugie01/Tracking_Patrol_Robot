import cv2
import yaml
import os
from ultralytics import YOLO

# ===========================================================================
# 1. 메타데이터 강제 생성 (TFLite 모델의 차원 에러 방지)
# ===========================================================================
model_name = "best_float16.tflite"
yaml_name = model_name.replace(".tflite", ".yaml")

# 모델이 실제로 내뱉는 39차원(Box 4 + Class 2 + Kpt 33)에 맞춘 정확한 스펙
metadata = {
    "task": "pose",
    "nc": 3,
    "names": {0: "Fire", 1: "Person", 2: "Weapon"},
    "kpt_shape": [11, 3]
}

# 실행 디렉토리에 YAML 파일을 강제로 덮어쓰기하여 생성
with open(yaml_name, "w", encoding="utf-8") as f:
    yaml.dump(metadata, f)
print(f"[시스템] {yaml_name} 메타데이터 파일 강제 생성 완료.")

# ===========================================================================
# 2. 모델 로드
# ===========================================================================
# YAML 파일이 만들어졌으므로, 라이브러리가 알아서 Pose 모델로 인식합니다.
model = YOLO(model_name, task="pose")

print("[시스템] YOLO 모델 로드 완료.")

# ===========================================================================
# 3. 비전 추론 루프
# ===========================================================================
cap = cv2.VideoCapture(0)
print("카메라 구동 시작. 종료하려면 'q' 키를 누르세요.")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("[에러] 카메라에서 프레임을 읽어올 수 없습니다.")
        break

    # 모델 추론 (에러 방지를 위해 해상도 640 고정)
    results = model.predict(frame, imgsz=640, conf=0.25, verbose=False)

    # 결과 시각화
    annotated_frame = results[0].plot()

    # 화면 출력
    cv2.imshow("TFLite Minimal Inference", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 자원 반납
cap.release()
cv2.destroyAllWindows()