# ----------------------------------------
# PT 모델(pre-trained model)을 3종(FP32, FP16, INT8)으로 변환하고, 각각 지정된 폴더로 자동 분류
#  -> 모델 변환과 파일 이동을 한 번에 처리하여 효율성 극대화
# ----------------------------------------


from ultralytics import YOLO
import os
import shutil




def export_all_tflite_variants(pt_model_path, data_yaml, output_base_dir):
    """
    PT 모델을 3가지 TFLite 버전(FP32, FP16, INT8)으로 변환하고
    각 모델별 독립 폴더로 가중치 파일을 배분함.
    """
    # 1. 베이스 모델 로드
    model = YOLO(pt_model_path, task='pose')
    
    # 출력 경로 설정 (tflite_models/v1/)
    variants = {
        "float32": {"half": False, "int8": False},
        "float16": {"half": True, "int8": False},
        "int8":    {"half": False, "int8": True}
    }

    exported_paths = {}

    for name, params in variants.items():
        print(f"\n[Export] Starting {name} conversion...")
        
        # 모델 변환 실행
        # int8 변환 시에는 반드시 data_yaml(대표 이미지셋 정보)이 필요함
        export_path = model.export(
            format='tflite', 
            half=params['half'], 
            int8=params['int8'], 
            data=data_yaml
        )
        
        # 생성된 파일의 목적지 폴더 (예: ../models/tflite_models/v1/int8/weights/)
        target_dir = os.path.join(output_base_dir, name, "weights")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        # 변환된 파일 이동 로직
        # model.export()는 보통 원본 .pt와 같은 위치에 생성됨
        new_path = os.path.join(target_dir, os.path.basename(export_path))
        
        # 기존 파일이 있다면 삭제 후 이동
        if os.path.exists(new_path):
            os.remove(new_path)
            
        shutil.move(export_path, new_path)
        exported_paths[name] = new_path
        
        print(f"[Success] {name} model saved at: {new_path}")

    return exported_paths




# 디버깅을 위한 독립 실행 구문
if __name__ == "__main__":
    # 코랩 파일의 변수명 예시 유지
    PT_PATH = "../models/base_models/v1/weights/best.pt"
    YAML_PATH = "../src/config/data_v1.yaml"
    OUT_BASE = "../models/tflite_models/v1"
    
    if os.path.exists(PT_PATH):
        export_all_tflite_variants(PT_PATH, YAML_PATH, OUT_BASE)
    else:
        print(f"[Error] Base model not found at {PT_PATH}")