

import cv2
import time
import numpy as np
from ultralytics import YOLO

# [경로 설정]
M1_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/model_full_integer_quant.tflite"
M2_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/yolo11n-pose_full_integer_quant.tflite"

roi_model = YOLO(M1_PATH, task='detect')
pose_model = YOLO(M2_PATH, task='pose')

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

prev_time = 0

print("--- [최적화] 실시간 탐지 및 11포인트 추적 시스템 가동 ---")

try:
    while True:
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time + 1e-6)
        prev_time = curr_time

        ret, frame = cap.read()
        if not ret: break
        
        results1 = roi_model.predict(frame, imgsz=320, conf=0.5, verbose=False)
        
        for r in results1:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = roi_model.names[cls_id]
                conf = float(box.conf[0])
                
                if label == 'person':
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    # 원본 박스 크기
                    # orig_w, orig_h = x2 - x1, y2 - y1

                    w, h = x2 - x1, y2 - y1
                    
                    # [핵심] 정사각형 패딩 로직
                    side = max(w, h) * 1.2
                    cx, cy = x1 + w // 2, y1 + h // 2

                    # # [개선] 인체 비율(세로:가로 = 2:1) 로직 적용
                    # # 사람을 세로로 길게 잘라내어 타이트하게 집중
                    # target_ratio = 0.5 
                    # new_h = orig_h * 1.1 # 10% 여유
                    # new_w = new_h * target_ratio
                    
                    x1_c = int(max(0, cx - side // 2))
                    y1_c = int(max(0, cy - side // 2))
                    x2_c = int(min(320, cx + side // 2))
                    y2_c = int(min(240, cy + side // 2))
                    
                    roi_img = frame[y1_c:y2_c, x1_c:x2_c]
                    
                    if roi_img.size > 0:
                        # [중요] 모델 2가 학습된 해상도(예: 160)에 맞춰 강제 리사이즈
                        # 모델 2가 160으로 학습되었다면 여기서 160으로 고정해서 넣어야 합니다.
                        roi_resized = cv2.resize(roi_img, (160, 160)) 
                        
                        results2 = pose_model.predict(roi_resized, imgsz=160, conf=0.3, verbose=False)
                        
                        if len(results2) > 0 and results2[0].keypoints.xy is not None:
                            kpts = results2[0].keypoints.xy[0].cpu().numpy()
                            
                            # 모델 입력이 160이었으므로, 출력된 키포인트 좌표를 원본 ROI 크기로 복원
                            # [x_원본] = [x_160] * (ROI_width / 160)
                            scale_w = (x2_c - x1_c) / 160
                            scale_h = (y2_c - y1_c) / 160
                            
                            for kpt in kpts:
                                if kpt[0] > 0: # visibility 체크
                                    px = int(kpt[0] * scale_w + x1_c)
                                    py = int(kpt[1] * scale_h + y1_c)
                                    cv2.circle(frame, (px, py), 4, (0, 255, 255), -1)

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
                    cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

        cv2.putText(frame, f"FPS: {int(fps)}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.imshow('RPi_Detection', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

finally:
    cap.release()
    cv2.destroyAllWindows()







# import cv2
# import time
# import numpy as np
# from ultralytics import YOLO

# # [경로 설정]
# M1_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/model_full_integer_quant.tflite"
# M2_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/yolo11n-pose_full_integer_quant.tflite"

# roi_model = YOLO(M1_PATH, task='detect')
# pose_model = YOLO(M2_PATH, task='pose')

# cap = cv2.VideoCapture(0)
# cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
# cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
# cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# # FPS 계산을 위한 변수 초기화
# prev_time = 0

# print("--- [최적화] 실시간 탐지 및 11포인트 추적 시스템 가동 ---")

# try:
#     while True:
#         # FPS 계산
#         curr_time = time.time()
#         fps = 1 / (curr_time - prev_time + 1e-6)
#         prev_time = curr_time

#         ret, frame = cap.read()
#         if not ret: break
        
#         results1 = roi_model.predict(frame, imgsz=320, conf=0.5, verbose=False)
        
#         for r in results1:
#             for box in r.boxes:
#                 cls_id = int(box.cls[0])
#                 label = roi_model.names[cls_id]
#                 conf = float(box.conf[0]) # 신뢰도 가져오기
                
#                 if label == 'person':
#                     x1, y1, x2, y2 = map(int, box.xyxy[0])
#                     w, h = x2 - x1, y2 - y1
                    
#                     # [개선 1] 정사각형 패딩 로직
#                     side = max(w, h) * 1.2
#                     cx, cy = x1 + w // 2, y1 + h // 2
                    
#                     x1_c = int(max(0, cx - side // 2))
#                     y1_c = int(max(0, cy - side // 2))
#                     x2_c = int(min(320, cx + side // 2))
#                     y2_c = int(min(240, cy + side // 2))
                    
#                     roi_img = frame[y1_c:y2_c, x1_c:x2_c]
                    
#                     if roi_img.size > 0:
#                         results2 = pose_model.predict(roi_img, imgsz=160, conf=0.3, verbose=False)
                        
#                         if len(results2) > 0 and results2[0].keypoints.xy is not None and len(results2[0].keypoints.xy) > 0:
#                             kpts = results2[0].keypoints.xy[0].cpu().numpy()
#                             def get_p(i): return kpts[i] if i < len(kpts) and kpts[i][0] > 0 else None
                            
#                             p0 = get_p(0)
#                             p5, p6 = get_p(5), get_p(6)
#                             p7, p8 = get_p(7), get_p(8)
#                             p9, p10 = get_p(9), get_p(10)
#                             p11, p12 = get_p(11), get_p(12)
#                             p15, p16 = get_p(15), get_p(16)
                            
#                             # [개선 2] 11개 포인트 리스트 정의
#                             pts = [
#                                 p0, (p5+p6)/2 if (p5 is not None and p6 is not None) else None,
#                                 p5, p6, p7, p8, p9, p10,
#                                 (p11+p12)/2 if (p11 is not None and p12 is not None) else None,
#                                 p15, p16
#                             ]
                            
#                             for pt in pts:
#                                 if pt is not None:
#                                     cv2.circle(frame, (int(pt[0] + x1_c), int(pt[1] + y1_c)), 4, (0, 255, 255), -1)

#                     # [출력] 사람 박스 및 라벨(클래스명 + 신뢰도) 표시
#                     cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
#                     cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

#         # [출력] 화면 좌측 상단에 FPS 출력
#         cv2.putText(frame, f"FPS: {int(fps)}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
#         cv2.imshow('RPi_Detection', frame)
#         if cv2.waitKey(1) & 0xFF == ord('q'): break

# finally:
#     cap.release()
#     cv2.destroyAllWindows()






# import cv2
# import numpy as np
# from ultralytics import YOLO

# # [경로 설정]
# M1_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/model_full_integer_quant.tflite"
# M2_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/yolo11n-pose_full_integer_quant.tflite"

# roi_model = YOLO(M1_PATH, task='detect')
# pose_model = YOLO(M2_PATH, task='pose')

# cap = cv2.VideoCapture(0)
# cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
# cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
# cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# print("--- [최적화] 실시간 탐지 및 11포인트 추적 시스템 가동 ---")

# try:
#     while True:
#         ret, frame = cap.read()
#         if not ret: break
        
#         results1 = roi_model.predict(frame, imgsz=320, conf=0.5, verbose=False)
        
#         for r in results1:
#             for box in r.boxes:
#                 # 라벨 확인
#                 cls_id = int(box.cls[0])
#                 label = roi_model.names[cls_id]
                
#                 if label == 'person':
#                     x1, y1, x2, y2 = map(int, box.xyxy[0])
#                     w, h = x2 - x1, y2 - y1
                    
#                     # [개선 1] 정사각형 패딩 로직으로 인체 비율 보존
#                     side = max(w, h) * 1.2  # 20% 여유를 주어 신체 잘림 방지
#                     cx, cy = x1 + w // 2, y1 + h // 2
                    
#                     x1_c = int(max(0, cx - side // 2))
#                     y1_c = int(max(0, cy - side // 2))
#                     x2_c = int(min(320, cx + side // 2))
#                     y2_c = int(min(240, cy + side // 2))
                    
#                     roi_img = frame[y1_c:y2_c, x1_c:x2_c]
                    
#                     if roi_img.size > 0:
#                         results2 = pose_model.predict(roi_img, imgsz=160, conf=0.3, verbose=False)
                        
#                         if len(results2) > 0 and results2[0].keypoints.xy is not None and len(results2[0].keypoints.xy) > 0:
#                             kpts = results2[0].keypoints.xy[0].cpu().numpy()
#                             def get_p(i): return kpts[i] if i < len(kpts) and kpts[i][0] > 0 else None
                            
#                             # 11개 포인트 계산용 인덱스 매핑
#                             p0 = get_p(0)   # 코
#                             p5, p6 = get_p(5), get_p(6)     # 양어깨
#                             p7, p8 = get_p(7), get_p(8)     # 양팔꿈치
#                             p9, p10 = get_p(9), get_p(10)   # 양손
#                             p11, p12 = get_p(11), get_p(12) # 양 골반
#                             p15, p16 = get_p(15), get_p(16) # 양 발
                            
#                             # [개선 2] 11개 포인트 리스트 정의
#                             pts = [
#                                 p0,                                         # 코
#                                 (p5+p6)/2 if (p5 is not None and p6 is not None) else None, # 가슴 중앙
#                                 p5, p6,                                     # 양어깨
#                                 p7, p8,                                     # 양팔꿈치
#                                 p9, p10,                                    # 양손
#                                 (p11+p12)/2 if (p11 is not None and p12 is not None) else None, # 골반 중앙
#                                 p15, p16                                    # 양 발
#                             ]
                            
#                             for pt in pts:
#                                 if pt is not None:
#                                     # 원본 좌표로 환산하여 그리기
#                                     cv2.circle(frame, (int(pt[0] + x1_c), int(pt[1] + y1_c)), 4, (0, 255, 255), -1)

#                     # 사람 박스 표시
#                     cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)

#         cv2.imshow('RPi_Detection', frame)
#         if cv2.waitKey(1) & 0xFF == ord('q'): break

# finally:
#     cap.release()
#     cv2.destroyAllWindows()









# ------------------------------
# 탐지가 되긴 하는데,,, 상반신만 탐지되는 등 이상함.. 
# -> 모델1에서 탐지되서 바운딩 박스를 그려서 그걸 크롭으로 따서 모델2에게 줄 때, 그대로 주면 안됨... 사람 비율에 맞춰서 조정 필요
# ------------------------------

# import cv2
# import time
# import psutil
# import os
# import numpy as np
# from ultralytics import YOLO

# # [경로 설정]
# M1_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/model_full_integer_quant.tflite"
# M2_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/yolo11n-pose_full_integer_quant.tflite"

# roi_model = YOLO(M1_PATH, task='detect')
# pose_model = YOLO(M2_PATH, task='pose')

# cap = cv2.VideoCapture(0)
# # [딜레이 해결 핵심] 버퍼 사이즈를 1로 줄이고 해상도를 낮게 유지
# cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
# cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
# cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# print("--- [최적화] 실시간 탐지 시스템 가동 ---")

# prev_time = 0

# try:
#     while True:
#         # FPS 계산
#         curr_time = time.time()
#         fps = 1 / (curr_time - prev_time + 1e-6)
#         prev_time = curr_time

#         # [딜레이 해결 핵심] 프레임 버퍼를 비우기 위해 루프마다 최신 1장만 읽음
#         ret, frame = cap.read()
#         if not ret: break
        
#         # [탐지 향상] conf를 0.5로 낮추어 놓침 방지
#         results1 = roi_model.predict(frame, imgsz=320, conf=0.5, verbose=False)
        
#         for r in results1:
#             for box in r.boxes:
#                 x1, y1, x2, y2 = map(int, box.xyxy[0])
#                 conf = float(box.conf[0])
#                 cls_id = int(box.cls[0])
#                 label = roi_model.names[cls_id]
                
#                 # [라벨링] fds와 신뢰도 출력
#                 label_text = f"{label} fds {conf:.2f}"
#                 cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
#                 cv2.putText(frame, label_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                
#                 # 포즈 추론은 'person'인 경우만 별도 처리
#                 if label == 'person':
#                     roi_img = frame[max(0, y1):min(240, y2), max(0, x1):min(320, x2)]
#                     if roi_img.size > 0:
#                         results2 = pose_model.predict(roi_img, imgsz=160, conf=0.3, verbose=False)
                        
#                         if len(results2) > 0 and results2[0].keypoints.xy is not None and len(results2[0].keypoints.xy) > 0:
#                             kpts = results2[0].keypoints.xy[0].cpu().numpy()
#                             def get_p(i): return kpts[i] if i < len(kpts) and kpts[i][0] > 0 else None
                            
#                             p0, p5, p6 = get_p(0), get_p(5), get_p(6)
#                             p7, p8, p9, p10 = get_p(7), get_p(8), get_p(9), get_p(10)
#                             p11, p12, p15, p16 = get_p(11), get_p(12), get_p(15), get_p(16)
                            
#                             pts = [
#                                 p0, (p5+p6)/2 if p5 is not None and p6 is not None else None,
#                                 p5, p6, p7, p8, p9, p10,
#                                 (p11+p12)/2 if p11 is not None and p12 is not None else None,
#                                 p15, p16
#                             ]
#                             for pt in pts:
#                                 if pt is not None:
#                                     cv2.circle(frame, (int(pt[0]+x1), int(pt[1]+y1)), 4, (0, 255, 255), -1)

#         # FPS 출력
#         cv2.putText(frame, f"FPS: {fps:.1f}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

#         # 딜레이를 유발하는 imshow 전송 데이터를 최소화 (원본 320x240 출력)
#         cv2.imshow('RPi_Detection', frame)
#         if cv2.waitKey(1) & 0xFF == ord('q'): break

# finally:
#     cap.release()
#     cv2.destroyAllWindows()









# # ------------------------------
# # 3개의 클래스가 골고루 탐지됨 (물론, 정확도는 떨어짐..)
# # ------------------------------
# import cv2
# import time
# import psutil
# import os
# import numpy as np
# from ultralytics import YOLO

# # [경로 설정]
# M1_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/model_full_integer_quant.tflite"
# M2_PATH = "/home/willtek/work/1st_pj_Tracking/models/yolo11-nano_ROI/yolo11n-pose_full_integer_quant.tflite"

# roi_model = YOLO(M1_PATH, task='detect')
# pose_model = YOLO(M2_PATH, task='pose')

# cap = cv2.VideoCapture(0)
# # [딜레이 해결 핵심] 버퍼 사이즈를 1로 줄이고 해상도를 낮게 유지
# cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
# cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
# cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# print("--- [최적화] 실시간 탐지 시스템 가동 ---")

# try:
#     while True:
#         # [딜레이 해결 핵심] 프레임 버퍼를 비우기 위해 루프마다 최신 1장만 읽음
#         ret, frame = cap.read()
#         if not ret: break
        
#         # [탐지 향상] conf를 0.5로 낮추어 놓침 방지
#         results1 = roi_model.predict(frame, imgsz=320, conf=0.5, verbose=False)
        
#         for r in results1:
#             for box in r.boxes:
#                 x1, y1, x2, y2 = map(int, box.xyxy[0])
#                 conf = float(box.conf[0])
#                 cls_id = int(box.cls[0])
#                 label = roi_model.names[cls_id]
                
#                 # 라벨링 (fire, person, weapon 모두 출력)
#                 label_text = f"{label} fds {conf:.2f}"
#                 cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
#                 cv2.putText(frame, label_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                
#                 # 포즈 추론은 'person'인 경우만 별도 처리
#                 if label == 'person':
#                     roi_img = frame[max(0, y1):min(240, y2), max(0, x1):min(320, x2)]
#                     if roi_img.size > 0:
#                         results2 = pose_model.predict(roi_img, imgsz=160, conf=0.3, verbose=False)
                        
#                         if len(results2) > 0 and results2[0].keypoints.xy is not None and results2[0].keypoints.xy.shape[0] > 0:
#                             kpts = results2[0].keypoints.xy[0].cpu().numpy()
#                             def get_p(i): return kpts[i] if i < len(kpts) and kpts[i][0] > 0 else None
                            
#                             p0, p5, p6 = get_p(0), get_p(5), get_p(6)
#                             p7, p8, p9, p10 = get_p(7), get_p(8), get_p(9), get_p(10)
#                             p11, p12, p15, p16 = get_p(11), get_p(12), get_p(15), get_p(16)
                            
#                             # 11개 포인트 매핑
#                             pts = [
#                                 p0, (p5+p6)/2 if p5 is not None and p6 is not None else None,
#                                 p5, p6, p7, p8, p9, p10,
#                                 (p11+p12)/2 if p11 is not None and p12 is not None else None,
#                                 p15, p16
#                             ]
#                             for pt in pts:
#                                 if pt is not None:
#                                     cv2.circle(frame, (int(pt[0]+x1), int(pt[1]+y1)), 4, (0, 255, 255), -1)

#         # 딜레이를 유발하는 imshow 전송 데이터를 최소화
#         small_frame = cv2.resize(frame, (320, 240))
#         cv2.imshow('RPi_Detection', small_frame)
#         if cv2.waitKey(1) & 0xFF == ord('q'): break

# finally:
#     cap.release()
#     cv2.destroyAllWindows()