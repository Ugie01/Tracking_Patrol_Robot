# ----------------------------------------
# Step 3: PT 모델 양자화 및 검증 : 3종 변환 및 독립 전수 검증
#  ->  Step 2에서 학습된 PT 모델을 양자화하여 경량화
#  ->  양자화된 모델을 검증 세트로 평가하여 성능 확인
#  -> 640x480(웹캠 규격) 해상도 고정 변환
#  -> FP32, FP16, INT8 모델별 독립 성능/속도 평가
# ----------------------------------------


import os
import time
import yaml
import json
from ultralytics import YOLO
from utils.model_exporter import export_all_tflite_variants
from utils.metrics_logger import verify_nms_keypoints, save_independent_results



# ----------------------------------------
# Step 3: PT 모델 양자화 및 검증 : 3종 변환 및 독립 전수 검증
#  -> 640x480(웹캠 규격) 해상도 고정 변환 및 속도 측정
#  -> verify_nms_keypoints를 활용한 키포인트 정밀 진단 포함
# ----------------------------------------

import os
import time
import yaml
import json
from ultralytics import YOLO
from utils.model_exporter import export_all_tflite_variants
from utils.metrics_logger import verify_nms_keypoints, save_independent_results



def main():
    # 1. 기본 설정 및 경로
    YAML_PATH = "config/data_v1.yaml"
    PT_MODEL_PATH = "../models/base_models/v1/weights/best.pt"
    TFLITE_BASE_DIR = "../models/tflite_models/v1"
    
    # 라즈베리파이 웹캠 해상도에 맞춘 입력 크기 [Height, Width]
    TARGET_IMGSZ = [480, 640] 
    
    if not os.path.exists(PT_MODEL_PATH):
        print(f"[Error] PT Model not found at {PT_MODEL_PATH}. Run Step 2 first.")
        return

    # 2. 3종 TFLite 변환 (FP32, FP16, INT8)
    print("\n[Step 3-1] Starting Model Export with 640x480 resolution...")
    exported_models = export_all_tflite_variants(PT_MODEL_PATH, YAML_PATH, TFLITE_BASE_DIR)

    # 3. 각 변환 모델에 대한 독립적 전수 검증 및 속도 측정
    for variant_name, model_path in exported_models.items():
        print(f"\n[Step 3-2] Evaluating: {variant_name.upper()}")
        
        model = YOLO(model_path, task='pose')
        save_dir = os.path.join(TFLITE_BASE_DIR, variant_name)
        
        # A. 독립 검증 수행 (mAP, Confusion Matrix 등 생성)
        metrics = model.val(
            data=YAML_PATH,
            imgsz=TARGET_IMGSZ,
            project=save_dir,
            name="validation_report",
            exist_ok=True,
            verbose=False
        )
        
        # B. 추론 속도(Latency) 측정 (10회 평균)
        sample_img_dir = "../data/dataset_v1/yolo/valid/images"
        latencies = []

        # 첫 번째 추론은 워밍업으로 제외하고 10회 측정
        test_images = os.listdir(sample_img_dir)[:11]
        for i, img_name in enumerate(test_images):
            img_path = os.path.join(sample_img_dir, img_name)
            start_time = time.time()
            model.predict(source=img_path, imgsz=TARGET_IMGSZ, conf=0.25, save=False, verbose=False)
            if i > 0: latencies.append(time.time() - start_time)
        
        avg_latency_ms = (sum(latencies) / len(latencies)) * 1000


        # C. NMS 결과 및 키포인트 정밀 분석 (verify_nms_keypoints 활용)
        print(f" -> Analyzing keypoint integrity for {variant_name}...")
        test_results = model.predict(source=sample_img_dir, imgsz=TARGET_IMGSZ, conf=0.25, max_det=5, verbose=False)
        
        kpt_analysis_logs = []
        for r in test_results[:10]: # 샘플 10개에 대해 정밀 진단 수행
            report = verify_nms_keypoints(r) # 이 부분에서 실질적으로 함수 사용
            kpt_analysis_logs.append(report)

        # D. 모든 지표 통합 저장 (results.json)
        json_save_path = os.path.join(save_dir, "results.json")
        save_independent_results(metrics, json_save_path)
        
        with open(json_save_path, 'r+') as f:
            data = json.load(f)
            data['avg_latency_ms'] = round(avg_latency_ms, 2)
            data['kpt_analysis_samples'] = kpt_analysis_logs # 분석 리포트 삽입
            f.seek(0)
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.truncate()

        print(f" -> {variant_name} mAP50: {data.get('mAP_50', 0):.4f}")
        print(f" -> {variant_name} Latency: {avg_latency_ms:.2f} ms")

    print("\n[Step 3 Success] All variants are evaluated with 640x480 resolution and KPT analysis.")



if __name__ == "__main__":
    main()





# def main():
#     # 1. 기본 설정 및 경로
#     YAML_PATH = "config/data_v1.yaml"
#     PT_MODEL_PATH = "../models/base_models/v1/weights/best.pt"
#     TFLITE_BASE_DIR = "../models/tflite_models/v1"


#     # 라즈베리파이 웹캠 해상도에 맞춘 입력 크기 [Height, Width] 순서 (YOLO 규칙)
#     TARGET_IMGSZ = [480, 640] 
    
#     if not os.path.exists(PT_MODEL_PATH):
#         print(f"[Error] PT Model not found at {PT_MODEL_PATH}. Run Step 2 first.")
#         return


#     # 2. 3종 TFLite 변환 (FP32, FP16, INT8)
#     # 내부적으로 model.export(imgsz=[480, 640])가 적용되도록 설계
#     print("\n[Step 3-1] Starting Model Export with 640x480 resolution...")
#     exported_models = export_all_tflite_variants(
#         PT_MODEL_PATH, 
#         YAML_PATH, 
#         TFLITE_BASE_DIR
#     )


#     # 3. 각 변환 모델에 대한 독립적 전수 검증 및 속도 측정
#     for variant_name, model_path in exported_models.items():
#         print(f"\n[Step 3-2] Evaluating: {variant_name.upper()}")
        
#         # TFLite 모델 로드
#         model = YOLO(model_path, task='pose')
        
#         # 결과 저장 폴더 설정
#         save_dir = os.path.join(TFLITE_BASE_DIR, variant_name)
        
#         # A. 독립 검증 수행 (mAP, Confusion Matrix 등 생성)
#         # imgsz를 [480, 640]으로 고정하여 검증
#         metrics = model.val(
#             data=YAML_PATH,
#             imgsz=TARGET_IMGSZ,
#             project=save_dir,
#             name="validation_report",
#             exist_ok=True,
#             verbose=False
#         )
        
#         # B. 추론 속도(Latency) 측정  (10회 평균)
#         # -> 실제 데이터셋 이미지 하나를 사용하여 평균 속도 계산
#         sample_img = "../data/dataset_v1/yolo/valid/images" # 검증셋 경로
#         start_time = time.time()
#         _ = model.predict(source=sample_img, imgsz=TARGET_IMGSZ, conf=0.25, save=False, verbose=False)
#         avg_latency = (time.time() - start_time) / 10.0 # 간단한 평균 측정 (샘플 10개 가정 시)

#         # C. 지표 JSON 저장 (metrics_logger 활용)
#         json_save_path = os.path.join(save_dir, "results.json")
#         save_independent_results(metrics, json_save_path)
        
#         # 추가 속도 데이터 기록
#         with open(json_save_path, 'r+') as f:
#             data = json.load(f)
#             data['avg_latency_ms'] = round(avg_latency * 1000, 2)
#             f.seek(0)
#             json.dump(data, f, indent=4)
#             f.truncate()

#         print(f" -> {variant_name} mAP50: {data.get('mAP_50', 0):.4f}")
#         print(f" -> {variant_name} Latency: {data['avg_latency_ms']} ms")

#     print("\n[Step 3 Success] All variants are exported and evaluated for On-Device deployment.")



# if __name__ == "__main__":
#     main()