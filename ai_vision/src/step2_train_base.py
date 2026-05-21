# ----------------------------------------
# Step 2: PT 모델 학습 및 검증 : 전이학습 및 베이스 지표 저장
#  ->  YOLO 형식으로 변환된 데이터셋을 활용하여 PT 모델 학습
#  ->  학습된 모델을 검증 세트로 평가하여 성능 확인   
# ----------------------------------------



import yaml
import os
import sys
import torch
from pathlib import Path
from ultralytics import YOLO
from utils.gpu_check import get_validated_device





def main():

    print("\n" + "="*60)
    print("🚀 [Step 2] 인공지능 모델 전이 학습 프로세스 가동")
    print("="*60)


    # 1. 경로 기준점 설정 (파일 위치 기반 절대 경로 추출)
    # 현재 파일(step2_train_base.py)의 부모 폴더(src)의 부모 폴더(ai_vision)
    BASE_DIR = Path(__file__).resolve().parent.parent
    print(f"🏠 프로젝트 루트 경로: {BASE_DIR}")



    # 2. GPU 환경 검증
    print("📡 [1/5] GPU 장치 상태를 점검 중입니다...")
    device = get_validated_device()
    
    if device is None:
        print("🚨 [중단] GPU를 사용할 수 없는 환경입니다. 학습을 강제 종료합니다.")
        sys.exit(1)



    # 3. 설정 파일 로드
    config_path = BASE_DIR / 'src' / 'config' / 'train_params.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            params = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 설정 파일 로드 실패: {e}")
        return
    

    
    # 4. 모델 타입에 따른 동적 경로 생성 로직 (워크플로우 반영)
    # -> yolo11-nano 또는 yolo26-nano
    m_type = params['model_type'].lower()

    # 모델명 기반 alias 결정
    if "yolov11" in m_type:
        model_alias = "yolo11-nano"
    elif "yolo26" in m_type:
        model_alias = "yolo26-nano"
    else:
        model_alias = "custom-model"
    

    # [최종 저장 절대 경로] ai_vision/models/yolo26-nano/base_models
    save_project = BASE_DIR / "models" / model_alias / "base_models"
    
    # 윈도우 경로 호환성을 위해 문자열로 변환
    save_project_str = str(save_project)
    
    print(f"📂 [저장 경로 확정]: {save_project_str}/{params['name']}")
    


    # 5. 모델 로드
    print(f"🏗️ [3/5] {model_alias} 모델 구조 생성 및 가중치 로드 중...")
    try:
        model = YOLO(params['model_type'], task='pose')
        print(f"✅ 모델 준비 완료. 저장 경로: {save_project}/{params['name']}")
    except Exception as e:
        print(f"❌ 모델 로드 오류: {e}")
        return
    
    print(f"\n[Step 2] {model_alias} 전이 학습을 시작합니다.")
    


    # 6. 최적화 학습 실행
    print("\n" + "-"*60)
    print(f"🔥 학습 시작: {params['model_type']} ({params['name']})")
    print(f"🖼️ 해상도 설정: {params['imgsz']} (H, W)")
    print("⚠️  처음 몇 분간은 엔진 초기화 및 데이터 스캔으로 인해 로그가 멈출 수 있습니다.")
    print("-"*60 + "\n")


    try:
        results = model.train(
            data=str(BASE_DIR / 'src' / 'config' / 'data_v1.yaml'),
            epochs=params['epochs'],
            imgsz=params['imgsz'],   # yaml의 [480, 640] 반영
            batch=params['batch'],
            optimizer=params['optimizer'],
            device=device,
            project=save_project_str,    # 절대 경로 전달
            name=params['name'],      # 하위 버전 경로 (v1)
            exist_ok=True,           # 동일 폴더 존재 시 유지/덮어쓰기
            plots=True,              # 지표 시각화 파일 생성
            verbose=True,             # 상세 로그 출력


            # --- 셧다운 방지 및 효율 최적화 설정 ---
            # cache=True,              # RAM 캐싱으로 속도 가속
            cache=False,             # RAM 폭주 방지 (셧다운의 주범 차단)
            rect=True,               # 직사각형 학습으로 연산 부하 감소
            # workers=8,               # CPU 병렬 준비 프로세스 최적화 (데이터 로딩 병렬화)
            workers=4,                # workers : CPU가 데이터를 읽어와서 전처리하는 '병렬' 프로세스의 개수
            amp=False,               # GTX 1660 수치 안정성 확보            
        )
        print("\n" + "-"*60)
        print("✅ [학습 성공] 베이스 PT 모델 생성이 완료되었습니다!")
    except Exception as e:
        print(f"\n❌ 학습 도중 오류 발생: {e}")
        return
    
    
    
    print(f"\n✨ 모든 결과물은 {save_project}/{params['name']} 폴더에서 확인 가능합니다.")
    print("="*60 + "\n")





if __name__ == "__main__":
    main()





# # -------------------------------
# gpu 설정 전 : cuda에서 기본적으로 cpu 연산 -> 시스템 부하로 PC 정지 위험
# # -------------------------------
# 
# def main():
#     # 1. 설정 로드
#     with open('config/train_params.yaml', 'r', encoding='utf-8') as f:
#         params = yaml.safe_load(f)
    
#     # 2. 모델 로드 (YOLO11n-pose 또는 YOLO26n-pose)
#     model = YOLO(params['model_type'], task='pose')
    
#     # 3. 학습 수행
#     # project와 name 설정을 통해 설계한 폴더 구조에 맞게 저장
#     results = model.train(
#         data='config/data_v1.yaml',
#         epochs=params['epochs'],
#         imgsz=params['imgsz'],
#         batch=params['batch'],
#         optimizer=params['optimizer'],
#         device=params['device'],
#         project=params['project'],  # ../models/base_models
#         name=params['name'],        # v1
#         exist_ok=True
#     )
    
#     print(f"\n[Step 2 Success] Base PT model trained and saved at: {params['project']}/{params['name']}")



# if __name__ == "__main__":
#     main()
