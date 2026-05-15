# ----------------------------------------
# Step 4: RPi에 모델 배포 : 최종 배포 및 실시간 추론
#  ->  양자화된 TFLite 모델을 RPi에 배포하여 실시간 추론 수행
#  ->  웹캠 해상도(640x480) 최적화 및 FPS 측정 로직 포함
# ----------------------------------------

import cv2
import time
from ultralytics import YOLO
from utils.metrics_logger import verify_nms_keypoints




def main():
    # 1. 최적의 배포 모델 로드 (INT8 TFLite)
    # Step 3에서 생성된 실제 파일명과 경로를 확인하십시오.
    DEPLOY_MODEL_PATH = "../models/tflite_models/v1/int8/weights/best_int8.tflite"
    
    try:
        model = YOLO(DEPLOY_MODEL_PATH, task='pose')
        print(f"[Info] Deploying model: {DEPLOY_MODEL_PATH}")
    except Exception as e:
        print(f"[Error] Failed to load TFLite model: {e}")
        return

    # 2. 카메라 설정 (라즈베리 파이 웹캠/CSI 카메라)
    cap = cv2.VideoCapture(0)
    
    # OpenCV 설정은 (가로, 세로) 순서입니다.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("\n[Running] Real-time Patrol AI starting... Press 'q' to stop.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # 속도 측정을 위한 시작 시간 기록
        start_time = time.time()

        # 3. 추론 수행 
        # YOLO imgsz 입력은 [Height, Width] 순서이므로 [480, 640]으로 설정합니다.
        results = model.predict(frame, conf=0.5, imgsz=[480, 640], verbose=False)
        
        # 추론 종료 시간 기록 및 FPS 계산
        end_time = time.time()
        fps = 1 / (end_time - start_time)
        
        # 4. 결과 렌더링
        annotated_frame = results[0].plot()
        
        # 화면에 FPS 표시
        cv2.putText(annotated_frame, f"FPS: {fps:.2f}", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # 5. 화면 표시
        cv2.imshow("School Zone Patrol Robot (INT8 Optimized)", annotated_frame)
        
        # 디버깅: 필요한 경우 터미널에 FPS 출력
        # print(f"Current FPS: {fps:.2f}")

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[Step 4 Finished] Deployment script closed.")





if __name__ == "__main__":
    main()






# import cv2
# from ultralytics import YOLO
# from utils.metrics_logger import verify_nms_keypoints



# def main():
#     # 1. 최적의 배포 모델 로드 (INT8 TFLite)
#     DEPLOY_MODEL_PATH = "../models/tflite_models/v1/int8/weights/best_int8.tflite"
    
#     try:
#         model = YOLO(DEPLOY_MODEL_PATH, task='pose')
#         print(f"[Info] Deploying model: {DEPLOY_MODEL_PATH}")
#     except Exception as e:
#         print(f"[Error] Failed to load TFLite model: {e}")
#         return

#     # 2. 카메라 설정 (라즈베리 파이 웹캠/CSI 카메라)
#     cap = cv2.VideoCapture(0)
#     cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
#     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)

#     print("\n[Running] Real-time Patrol AI starting... Press 'q' to stop.")

#     while cap.isOpened():
#         ret, frame = cap.read()
#         if not ret:
#             break

#         # 3. 추론 수행 (NMS 자동 적용)
#         results = model.predict(frame, conf=0.5, imgsz=640, verbose=False)
        
#         # 4. 결과 렌더링
#         # Results[0].plot()은 BBox와 11개 키포인트를 자동으로 그려줌
#         annotated_frame = results[0].plot()
        
#         # 디버깅: 키포인트 유실 여부 실시간 모니터링 (필요 시 주석 해제)
#         # verify_nms_keypoints(results[0])

#         # 5. 화면 표시
#         cv2.imshow("School Zone Patrol Robot (INT8 Optimized)", annotated_frame)
        
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

#     cap.release()
#     cv2.destroyAllWindows()
#     print("[Step 4 Finished] Deployment script closed.")



# if __name__ == "__main__":
#     main()
