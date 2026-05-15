# ----------------------------------------
# JSON → YOLO & 11개 키포인트 패딩 설정 파일
#  -> roboflow에서 JSON 형식으로 라벨링한 데이터를 YOLO 형식으로 변환하는 스크립트
# ----------------------------------------



import json
import os



def pad_keypoints(keypoints, target_num=11):
    """fire/weapon 클래스의 1개 키포인트 데이터를 11개로 확장(패딩)"""
    # 기존 코랩 로직: 부족한 키포인트를 [0.0, 0.0, 0]으로 채움
    current_num = len(keypoints) // 3
    if current_num < target_num:
        # 부족한 만큼 [x, y, v] 세트를 추가
        padding = [0.0, 0.0, 0] * (target_num - current_num)
        keypoints.extend(padding)

    # 정확히 target_num * 3 개수만큼만 슬라이싱하여 반환
    return keypoints[:target_num * 3]




def convert_coco_to_yolo_v1(json_file, output_dir, target_kpt_count=11):
    """
    COCO 라벨 데이터(json) parsing ->  YOLO TXT 생성.
    pad_keypoints 함수를 호출하여 모든 클래스의 키포인트 형식을 11개로 통일함.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. 이미지 정보 및 카테고리 매핑 (코랩 로직 반영)
    image_id_to_info = {img['id']: img for img in data['images']}
    
    # YOLO는 클래스 번호를 0부터 시작하므로 카테고리 ID 조정 필요 시 확인
    # 보통 Roboflow 데이터는 category_id가 1부터 시작하므로 -1 처리를 해줍니다.
    
    # 2. 어노테이션 반복 처리
    for ann in data['annotations']:
        image_id = ann['image_id']
        if image_id not in image_id_to_info:
            continue
            
        img_info = image_id_to_info[image_id]
        img_w = img_info['width']
        img_h = img_info['height']
        file_name = img_info['file_name']
        
        # 클래스 ID (0-indexed)
        category_id = ann['category_id'] - 1 
        
        # BBox 변환 (COCO: [x_min, y_min, width, height] -> YOLO: [center_x, center_y, w, h])
        bbox = ann['bbox']
        x_center = (bbox[0] + bbox[2] / 2.0) / img_w
        y_center = (bbox[1] + bbox[3] / 2.0) / img_h
        w = bbox[2] / img_w
        h = bbox[3] / img_h

        # 키포인트 처리: pad_keypoints 함수 호출 (11개로 강제 패딩)
        raw_keypoints = ann.get('keypoints', [])
        padded_kpts = pad_keypoints(raw_keypoints, target_num=target_kpt_count)
        
        # 키포인트 정규화 (x/img_w, y/img_h, v)
        normalized_kpts = []
        for i in range(0, len(padded_kpts), 3):
            kx = padded_kpts[i] / img_w if padded_kpts[i] != 0 else 0.0
            ky = padded_kpts[i+1] / img_h if padded_kpts[i+1] != 0 else 0.0
            kv = padded_kpts[i+2] # visibility는 정규화 필요 없음
            normalized_kpts.extend([kx, ky, kv])

        # YOLO 텍스트 라인 생성
        # format: class x_c y_c w h k1_x k1_y k1_v ... k11_x k11_y k11_v
        kpt_str = " ".join([f"{val:.6f}" if j % 3 != 2 else str(int(val)) 
                           for j, val in enumerate(normalized_kpts)])
        
        yolo_line = f"{category_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f} {kpt_str}\n"

        # 이미지 파일명과 동일한 이름의 .txt 파일에 기록
        txt_name = os.path.splitext(file_name)[0] + ".txt"
        txt_path = os.path.join(output_dir, txt_name)
        
        with open(txt_path, 'a', encoding='utf-8') as f_out:
            f_out.write(yolo_line)

    print(f"Data conversion completed: {output_dir}")