# ----------------------------------------
# NMS 결과 분석 및 FDS 지표 생성
#  -> yolo 모델 자체에서 정의한 NMS 연산 결과를 분석하여 FDS 지표를 생성하는 모듈
# ----------------------------------------


import numpy as np
import json
import os



def verify_nms_keypoints(r):
    """
    NMS 후 결과물 r에서 키포인트 유실 여부를 정밀 진단하고 디버깅 로그를 출력함.
    YOLO11 등에서 키포인트가 안 나오는 현상을 추적하기 위한 핵심 함수.
    """
    analysis_report = {
        "object_count": len(r.boxes),
        "keypoints_detected": False,
        "details": []
    }

    if r.keypoints is not None:
        # r.keypoints.xyn 변수명 유지 (정규화 좌표 [N, 11, 2])
        kpts_xyn = r.keypoints.xyn.cpu().numpy()
        # 신뢰도 [N, 11]
        kpts_conf = r.keypoints.conf.cpu().numpy() if r.keypoints.conf is not None else None
        
        analysis_report["keypoints_detected"] = True
        print(f"\n[NMS Debug] Objects: {len(r.boxes)}, KPT Shape: {kpts_xyn.shape}")

        for i in range(len(kpts_xyn)):
            kpt = kpts_xyn[i]
            # 좌표가 (0,0)이 아닌 유효 키포인트 개수 파악 (valid_kpts로 통일)
            valid_kpts = int(np.count_nonzero(kpt.sum(axis=1) > 0)) # valid_kpts로 정의
            avg_conf = float(np.mean(kpts_conf[i])) if kpts_conf is not None else 0.0
            
            obj_info = {
                "id": i,
                "class": int(r.boxes.cls[i]),
                "valid_keypoints": valid_kpts,
                "avg_confidence": avg_conf
            }
            analysis_report["details"].append(obj_info)
            print(f"  - Object {i} (Class {obj_info['class']}): {valid_kpts}/11 Keypoints, Conf: {avg_conf:.4f}")
            
        return analysis_report
    else:
        print("\n[NMS Warning] Keypoints are None for this frame.")
        return analysis_report



def calculate_fds_metrics(results):
    """
    Fire Detection Sensitivity(FDS) 계산 로직.
    """
    total_fire_instances = 0
    detected_fire_instances = 0
    
    for r in results:
        classes = r.boxes.cls.cpu().numpy()
        total_fire_instances += np.sum(classes == 0) # 클래스 0: 화재
        # 탐지 로직 고도화 시 추가
        
    fds_score = (detected_fire_instances / total_fire_instances) if total_fire_instances > 0 else 0.0
    return {"fds_score": fds_score}



def save_independent_results(results_obj, save_path):
    """
    mAP, FDS 등 각 모델별 독립 성능 지표를 JSON으로 저장.
    """
    # Ultralytics의 결과 객체에서 지표 추출
    metrics_dict = results_obj.results_dict
    
    metrics_summary = {
        "model_name": os.path.basename(os.path.dirname(save_path)),
        "mAP_50": float(metrics_dict.get('metrics/mAP50(B)', 0.0)),
        "mAP_50_95": float(metrics_dict.get('metrics/mAP50-95(B)', 0.0)),
        "fitness": float(results_obj.fitness) if hasattr(results_obj, 'fitness') else 0.0
    }
    
    save_dir = os.path.dirname(save_path)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)
        
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(metrics_summary, f, indent=4, ensure_ascii=False)
        
    print(f"[Success] Independent metrics saved at: {save_path}")

