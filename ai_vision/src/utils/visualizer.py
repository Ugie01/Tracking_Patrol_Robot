# ----------------------------------------
# 모델 시각화 도구
#  -> NMS 결과를 프레임에 렌더링하여 모델 성능을 직관적으로 비교할 수 있도록 지원
#  -> 4개 모델의 결과를 2x2 격자로 합쳐서 저장하는 기능 포함 (보고서용)
# * 모델별 mAP, FPS, Size 등을 막대 그래프로 시각화하는 기능 포함 (보고서용)
# * 4종 모델(PT, FP32, FP16, INT8)의 추론 결과를 한 장의 이미지나 하나의 영상으로 결합
# ----------------------------------------


import cv2
import numpy as np
import os
import matplotlib.pyplot as plt



def draw_keypoints_on_frame(frame, r, color=(0, 255, 0)):
    """
    단일 프레임에 NMS 결과(r)의 BBox와 11개 키포인트를 렌더링함.
    """
    if r.keypoints is not None:
        # 정규화되지 않은 픽셀 좌표 [N, 11, 2]
        kpts = r.keypoints.xy.cpu().numpy()
        conf = r.keypoints.conf.cpu().numpy() if r.keypoints.conf is not None else None
        
        for i, obj_kpts in enumerate(kpts):
            # BBox 그리기
            x1, y1, x2, y2 = map(int, r.boxes.xyxy[i].cpu().numpy())
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # 11개 키포인트 및 연결선 그리기 (패딩된 0,0 좌표는 제외)
            for j, (kx, ky) in enumerate(obj_kpts):
                if kx > 0 and ky > 0:
                    cv2.circle(frame, (int(kx), int(ky)), 5, (0, 0, 255), -1)
                    cv2.putText(frame, str(j), (int(kx), int(ky)-5), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    return frame



def create_comparison_grid(frames, labels, output_path):
    """
    4개 모델의 결과 프레임을 2x2 격자로 합쳐서 저장 (성능 비교용)
    frames: [frame_pt, frame_f32, frame_f16, frame_int8]
    """
    if len(frames) != 4:
        return
    
    # 각 프레임 상단에 모델 이름 기입
    for frame, label in zip(frames, labels):
        cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

    # 2x2 격자 생성
    top_row = np.hstack((frames[0], frames[1]))
    bottom_row = np.hstack((frames[2], frames[3]))
    grid = np.vstack((top_row, bottom_row))
    
    cv2.imwrite(output_path, grid)
    print(f"[Success] Comparison grid saved: {output_path}")



def plot_model_comparison_chart(metrics_list, labels, save_path):
    """
    모델별 mAP, FPS, Size 등을 막대 그래프로 시각화 (보고서용)
    """
    x = np.arange(len(labels))
    maps = [m['mAP_50'] for m in metrics_list]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(x, maps, color=['blue', 'green', 'orange', 'red'])
    plt.xlabel('Model Variants')
    plt.ylabel('mAP@50')
    plt.title('Performance Comparison: PT vs TFLite Variants')
    plt.xticks(x, labels)
    
    # 막대 위에 수치 표시
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.01, round(yval, 3), ha='center')
    
    plt.savefig(save_path)
    plt.close()
    print(f"[Success] Comparison chart saved: {save_path}")