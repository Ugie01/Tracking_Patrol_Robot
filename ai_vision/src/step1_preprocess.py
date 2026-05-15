# ----------------------------------------
# Step 1: 모델 학습을 위한 데이터셋 준비 (데이터셋 전처리 : 정제, 검증, 패딩)
#  ->  기존 데이터셋의 JSON 파일을 YOLO 형식으로 변환
#  ->  키포인트 수를 11개로 패딩하여 고정   
# ----------------------------------------



import os
import shutil
from utils.data_converter import convert_coco_to_yolo_v1



# 데이터셋 경로 
RAW_DATA_ROOT = "../data/dataset_v1/roboflow"   # 데이터 정제 대상 경로
YOLO_DATA_ROOT = "../data/dataset_v1/yolo"   # 정제한 데이터 저장할 경로 (YOLO 형식)



def main():
    # 1. 기존 폴더가 있다면 초기화 (충돌 방지)
    if os.path.exists(YOLO_DATA_ROOT):
        shutil.rmtree(YOLO_DATA_ROOT)
    
    splits = ['train', 'valid', 'test']
    
    for split in splits:
        json_path = os.path.join(RAW_DATA_ROOT, split, "_annotations.coco.json")
        img_src_dir = os.path.join(RAW_DATA_ROOT, split)
        
        # YOLO 이미지 및 라벨 폴더 경로 설정
        img_dest_dir = os.path.join(YOLO_DATA_ROOT, split, "images")
        lbl_dest_dir = os.path.join(YOLO_DATA_ROOT, split, "labels")
        os.makedirs(img_dest_dir, exist_ok=True)
        os.makedirs(lbl_dest_dir, exist_ok=True)

        # 2. JSON 변환 및 패딩 수행 (11개 키포인트 고정)
        if os.path.exists(json_path):
            convert_coco_to_yolo_v1(json_path, lbl_dest_dir, target_kpt_count=11)
            
            # 3. 이미지 파일 복사
            for file in os.listdir(img_src_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    shutil.copy(os.path.join(img_src_dir, file), os.path.join(img_dest_dir, file))
        else:
            print(f"[Skip] {split} 세트의 JSON 파일을 찾을 수 없습니다.")

    print("\n[Step 1] 모든 데이터의 11개 키포인트 패딩 및 전처리가 완료되었습니다.")



if __name__ == "__main__":
    main()