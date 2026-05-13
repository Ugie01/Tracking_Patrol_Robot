# ----------------------------------------
# Step 2: PT 모델 학습 및 검증 : 전이학습 및 베이스 지표 저장
#  ->  YOLO 형식으로 변환된 데이터셋을 활용하여 PT 모델 학습
#  ->  학습된 모델을 검증 세트로 평가하여 성능 확인   
# ----------------------------------------



import yaml
import os
import sys
import torch
from ultralytics import YOLO
from utils.gpu_check import get_validated_device





def main():

    print("\n" + "="*60)
    print("🚀 [Step 2] 인공지능 모델 전이 학습 프로세스 가동")
    print("="*60)

    # 1. GPU 환경 검증
    print("📡 [1/5] GPU 장치 상태를 점검 중입니다...")
    device = get_validated_device()
    
    if device is None:
        print("🚨 [중단] GPU를 사용할 수 없는 환경입니다. 학습을 강제 종료합니다.")
        sys.exit(1)


    # 2. 설정 파일 로드
    print("📂 [2/5] 설정 파일(train_params.yaml)을 읽어오는 중...")
    try:
        with open('config/train_params.yaml', 'r', encoding='utf-8') as f:
            params = yaml.safe_load(f)
        print(f"✅ 설정 로드 완료: 모델 타입 - {params['model_type']}")
    except Exception as e:
        print(f"❌ 설정 파일 로드 실패: {e}")
        return
    
    
    # 3. 모델 타입 분석을 통한 경로 자동 생성 (yolo11-nano 또는 yolo26-nano)
    m_type = params['model_type'].lower()
    model_alias = "yolo11-nano" if "yolov11" in m_type else "yolo26-nano"
    
    # [work flow 반영] ../models/yoloXX-nano/base_models
    save_project = f"../models/{model_alias}/base_models"
    

    # 3. 모델 로드
    print(f"🏗️ [3/5] {model_alias} 모델 구조 생성 및 가중치 로드 중...")
    try:
        model = YOLO(params['model_type'], task='pose')
        print(f"✅ 모델 준비 완료. 저장 경로: {save_project}/{params['name']}")
    except Exception as e:
        print(f"❌ 모델 로드 오류: {e}")
        return
    
    print(f"\n[Step 2] {model_alias} 전이 학습을 시작합니다.")
    


    # 4. 학습 실행
    print("\n" + "-"*60)
    print(f"🔥 [4/5] 학습 시작 (Epochs: {params['epochs']}, Imgsz: {params['imgsz']})")
    print("⚠️  처음 몇 분간은 엔진 초기화 및 데이터 스캔으로 인해 로그가 멈출 수 있습니다.")
    print("-"*60 + "\n")


    try:
        results = model.train(
            data='config/data_v1.yaml',
            epochs=params['epochs'],
            imgsz=params['imgsz'],
            batch=params['batch'],
            optimizer=params['optimizer'],
            device=device,
            project=save_project,
            name=params['name'],
            exist_ok=True,
            plots=True,
            verbose=True  # 상세 로그 활성화
        )
        print("\n" + "-"*60)
        print("✅ [5/5] 학습이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"\n❌ 학습 도중 오류 발생: {e}")
        return
    
    # model.train(
    #     data='config/data_v1.yaml',
    #     epochs=params['epochs'],
    #     imgsz=params['imgsz'],
    #     batch=params['batch'],
    #     optimizer=params['optimizer'],
    #     device=params['device'],
    #     project=save_project, 
    #     name=params['name'],    # v1
    #     exist_ok=True,
    #     plots=True              # confusion_matrix, curves 등 자동 생성
    # )
    
    
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
