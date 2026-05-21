import cv2             
import time            
import threading       
import math            
import struct          
import serial          
import numpy as np     
from ultralytics import YOLO 
import yaml

import tensorflow as tf

# TFLite 모델 텐서 구조 분석 스크립트
interpreter = tf.lite.Interpreter(model_path="best_float16.tflite")
interpreter.allocate_tensors()
output_details = interpreter.get_output_details()

print("실제 아웃풋 텐서 셰이프:", output_details[0]['shape'])
# ===========================================================================
# [커스텀 라벨 인덱스] - 학습된 모델의 0, 1, 2 클래스 정의 (필요시 순서 변경)
# ===========================================================================
PERSON_CLS = 1  # 사람
FIRE_CLS = 0    # 화염
WEAPON_CLS = 2  # 무기

# ===========================================================================
# [하이퍼파라미터 설정] - 시스템 제어 및 임계치 상수 정의
# ===========================================================================
FALL_LATERAL_RATIO = 1.3        
FALL_AXIAL_RATIO = 0.55         
FALL_CHEST_LOW_THRESH = 0.50    

PUNCH_REACH_RATIO = 0.50         
WEAPON_PROXIMITY_THRESH = 70.0   
WEAPON_DIST_SQ_THRESH = WEAPON_PROXIMITY_THRESH ** 2  

DRIVE_REVERSE_THRESH = 0.90      
DRIVE_STOP_THRESH = 0.75         

PRIORITY = {"FALLEN": 3, "ABNORMAL": 2, "FIRE": 1, "NORMAL": 0} 

MODEL_PATH = "best_float16.tflite"   
FRAME_W, FRAME_H = 640, 480      
CENTER_X = FRAME_W / 2           
H_FOV = 40.1                     
focal_length = CENTER_X / math.tan(math.radians(H_FOV / 2.0)) 

TRACKING_TIMEOUT = 10.0         
REID_SIMILARITY_THRESH = 0.50   
KP_CONF_THRESH = 0.6            
MAX_LOST_FRAMES_BUFFER = 30     

global_output_frame = None      
frame_lock = threading.Lock()   

# ===========================================================================
# [키포인트 인덱스] - 11포인트 모델 출력 순서 매핑
# ===========================================================================
KP_FACE = 0
KP_CHEST = 1
KP_HIP = 2
KP_R_FOOT = 3
KP_L_FOOT = 4
KP_R_SHOULDER = 5
KP_L_SHOULDER = 6
KP_R_ELBOW = 7
KP_L_ELBOW = 8
KP_R_WRIST = 9
KP_L_WRIST = 10

# ===========================================================================
# [알고리즘 함수군] - 휴리스틱 행동 분석 및 특징 추출
# ===========================================================================
def get_color_hist(frame, bx, by, bw, bh):
    core_w, core_h = bw * 0.5, bh * 0.5 
    x1, y1 = max(0, int(bx - core_w/2)), max(0, int(by - core_h/2))
    x2, y2 = min(FRAME_W, int(bx + core_w/2)), min(FRAME_H, int(by + core_h/2))
    
    crop = frame[y1:y2, x1:x2] 
    if crop.size == 0: return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV) 
    hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX) 
    return hist

def analyze_behavior(kpts, bw, bh, weapon_centers):
    def is_valid(idx): 
        if len(kpts) <= idx: return False
        return kpts[idx][2] > KP_CONF_THRESH
        
    aspect_ratio = bw / bh if bh > 0 else 0 

    if aspect_ratio > 0.8 and is_valid(KP_CHEST) and is_valid(KP_HIP):
        chest_y_frame = kpts[KP_CHEST][1] / FRAME_H 
        t_x = abs(kpts[KP_CHEST][0] - kpts[KP_HIP][0]) 
        t_y = abs(kpts[KP_CHEST][1] - kpts[KP_HIP][1]) 

        if t_x > (t_y * FALL_LATERAL_RATIO): return "FALLEN"
        
        if is_valid(KP_R_SHOULDER) and is_valid(KP_L_SHOULDER):
            shoulder_w = abs(kpts[KP_R_SHOULDER][0] - kpts[KP_L_SHOULDER][0])
            if shoulder_w > 0 and t_y < (shoulder_w * FALL_AXIAL_RATIO) and chest_y_frame > FALL_CHEST_LOW_THRESH:
                return "FALLEN"

    weapon_held = False
    for w_idx in [KP_R_WRIST, KP_L_WRIST]:
        if is_valid(w_idx):
            wx, wy = kpts[w_idx][0], kpts[w_idx][1]
            for wbx, wby in weapon_centers:
                if (wx - wbx)**2 + (wy - wby)**2 < WEAPON_DIST_SQ_THRESH and wy < kpts[KP_HIP][1]:
                    weapon_held = True; break

    punch_detected = False
    if is_valid(KP_CHEST) and bw > 0:
        for w_idx in [KP_R_WRIST, KP_L_WRIST]:
            if is_valid(w_idx):
                if abs(kpts[w_idx][0] - kpts[KP_CHEST][0]) > (bw * PUNCH_REACH_RATIO) and kpts[w_idx][1] < kpts[KP_CHEST][1]:
                    punch_detected = True; break

    kick_detected = False
    if is_valid(KP_HIP) and bh > 0:
        for f_idx in [KP_R_FOOT, KP_L_FOOT]:
            if is_valid(f_idx):
                if kpts[f_idx][1] < kpts[KP_HIP][1] + (bh * 0.1):
                    kick_detected = True; break

    if weapon_held or punch_detected or kick_detected: return "ABNORMAL"
    return "NORMAL"

# ===========================================================================
# [하드웨어 모듈] I/O 비동기 분리용 스레드 클래스
# ===========================================================================
class CameraStream:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src, cv2.CAP_V4L2) 
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)    
        self.cap.set(cv2.CAP_PROP_EXPOSURE, -5)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)       
        self.stopped = False
        self.ret, self.frame = self.cap.read()         
        self.lock = threading.Lock()                   
        threading.Thread(target=self.update, daemon=True).start() 

    def update(self):
        while not self.stopped:
            ret, frame = self.cap.read()
            if ret:
                with self.lock: self.frame = frame 
            time.sleep(0.005) 
            
    def read(self):
        with self.lock: return self.frame.copy() if self.frame is not None else None
        
    def stop(self):
        self.stopped = True; self.cap.release()

class SerialCommunicator:
    def __init__(self, port='/dev/ttyAMA0', baudrate=115200):
        self.current_yaw, self.current_temp = 0.0, 0.0 
        self.stopped = False
        self.temp_trigger_event, self.yaw_trigger_event = threading.Event(), threading.Event()
        self.lock = threading.Lock()
        self.target_yaw, self.stop_signal = 0.0, 0     
        try:
            self.ser = serial.Serial(port, baudrate, timeout=0.05) 
        except: self.ser = None 
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        if not self.ser: return
        last_poll_time = time.time()
        while not self.stopped:
            if self.temp_trigger_event.is_set():
                self.ser.write(bytes([0xAA, 0x0A, 0x55])) 
                self.temp_trigger_event.clear(); self.receive_response('T')
                
            if self.yaw_trigger_event.is_set():
                self.ser.write(bytes([0xAA, 0x0B, 0x55]))
                self.yaw_trigger_event.clear(); self.receive_response('Y')
                
            if time.time() - last_poll_time >= 0.05:
                with self.lock: payload = f"t{self.target_yaw:.2f},{self.stop_signal}\n"
                self.ser.write(payload.encode('utf-8'))
                last_poll_time = time.time()
            time.sleep(0.01)

    def receive_response(self, data_type):
        if not self.ser: return
        packet = self.ser.read(4)
        if len(packet) < 4: return
        try:
            val = struct.unpack('<f', packet)[0] 
            with self.lock:
                if data_type == 'T': self.current_temp = val
                elif data_type == 'Y': self.current_yaw = val
        except: pass

    def request_temp(self): self.temp_trigger_event.set()
    def request_yaw(self): self.yaw_trigger_event.set()
    def get_temp(self):
        with self.lock: return self.current_temp
    def get_yaw(self):
        with self.lock: return self.current_yaw
    def set_target_data(self, yaw_val, stop_val):
        with self.lock: self.target_yaw, self.stop_signal = yaw_val, stop_val
    def stop(self):
        self.stopped = True
        if self.ser: self.ser.close()

# ===========================================================================
# [모듈] 메인 AI 추론 엔진
# ===========================================================================
class InferenceEngine:
    def __init__(self, camera, serial_comm):
        self.camera = camera
        self.serial = serial_comm
        
        # 깔끔하게 모델만 로드 (task='pose'만 유지)
        self.model = YOLO(MODEL_PATH, task='pose')
        
        self.stopped = False
        
        self.locked_id = None            
        self.locked_type = None          
        self.locked_hist = None          
        self.last_seen_time = 0.0        
        self.lost_frame_count = 0        
        self.last_known_target = None    
        self.last_valid_yaw = 0.0
        self.last_valid_state = 0
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        global global_output_frame
        while not self.stopped:
            frame = self.camera.read() 
            self.serial.request_yaw()  
            curr_yaw = self.serial.get_yaw()
            if frame is None: continue

            try:
                print("시작")
                # 3. [수정됨] track 함수에 data='custom_metadata.yaml' 파라미터 추가
                results = self.model.track(frame, tracker="bytetrack.yaml", persist=True, verbose=False, classes=[0, 1, 2], imgsz=640, conf=0.25)
                print("끝")
                weapon_centers = [] 
                candidates = []     
                current_time = time.time()

                if results and results[0].boxes:
                    for i, box_obj in enumerate(results[0].boxes):
                        cls = int(box_obj.cls[0])
                        box_xywh = box_obj.xywh[0].cpu().numpy() 
                        bx, by, bw, bh = box_xywh
                        
                        # 무기 검출
                        if cls == WEAPON_CLS: 
                            weapon_centers.append((bx, by))
                            continue
                        
                        # 화염 검출
                        if cls == FIRE_CLS: 
                            candidates.append({"id": None, "type": "FIRE", "prio": PRIORITY["FIRE"], "box": box_xywh, "center": (bx, by), "height_ratio": bh/FRAME_H, "status": "FIRE", "hist": None})
                            continue

                        # 사람 검출 (ID 부여 확인)
                        track_id = int(box_obj.id[0]) if box_obj.id is not None else -1
                        if track_id == -1 or cls != PERSON_CLS: continue

                        current_status = "NORMAL"
                        if results[0].keypoints is not None and len(results[0].keypoints.data) > i:
                            tflite_kpts = results[0].keypoints.data[i].cpu().numpy()
                            current_status = analyze_behavior(tflite_kpts, bw, bh, weapon_centers) 

                        candidates.append({
                            "id": track_id, "type": current_status, "prio": PRIORITY[current_status],
                            "box": box_xywh, "center": (bx, by), "height_ratio": bh/FRAME_H,
                            "status": current_status, "hist": get_color_hist(frame, bx, by, bw, bh) 
                        })

                best_target = None

                if self.locked_id is not None:
                    matched = [c for c in candidates if c["id"] == self.locked_id]
                    
                    if not matched and candidates:
                        highest_sim = 0
                        reid_candidate = None
                        for c in candidates:
                            if c["hist"] is not None and self.locked_hist is not None:
                                sim = cv2.compareHist(self.locked_hist, c["hist"], cv2.HISTCMP_CORREL)
                                if sim > highest_sim:
                                    highest_sim = sim; reid_candidate = c
                        
                        if highest_sim > REID_SIMILARITY_THRESH and reid_candidate is not None:
                            matched = [reid_candidate]
                            self.locked_id = reid_candidate["id"] 

                    if matched:
                        best_target = matched[0]
                        best_target["status"] = self.locked_type 
                        self.locked_hist = best_target["hist"]   
                        self.last_seen_time = current_time
                        self.lost_frame_count = 0                
                        self.last_known_target = best_target     
                    
                    else:
                        self.lost_frame_count += 1 
                        
                        if self.lost_frame_count < MAX_LOST_FRAMES_BUFFER and self.last_known_target is not None:
                            best_target = self.last_known_target
                            self.last_seen_time = current_time   
                        
                        elif current_time - self.last_seen_time >= TRACKING_TIMEOUT:
                            self.locked_id, self.locked_type, self.locked_hist = None, None, None
                            self.last_known_target = None

                if self.locked_id is None and candidates:
                    valid_candidates = [c for c in candidates if c["prio"] > 0] 
                    if valid_candidates:
                        best_target = max(valid_candidates, key=lambda c: c["prio"])
                        self.locked_id = best_target["id"]
                        self.locked_type = best_target["type"]
                        self.locked_hist = best_target["hist"]
                        self.last_seen_time = current_time
                        self.lost_frame_count = 0
                        self.last_known_target = best_target

                if best_target is not None:
                    tx, ty = best_target["center"]
                    vis_error = math.degrees(math.atan((tx - CENTER_X) / focal_length))
                    if abs(vis_error) < 2.0: vis_error = 0.0 

                    target_yaw = curr_yaw + vis_error
                    if target_yaw > 180: target_yaw -= 360
                    elif target_yaw < -180: target_yaw += 360

                    ratio = best_target["height_ratio"]
                    drive_state = 2 if ratio >= DRIVE_REVERSE_THRESH else 1 if ratio >= DRIVE_STOP_THRESH else 0
                    
                    color = (0, 255, 255) if self.lost_frame_count > 0 else (0, 0, 255)
                    state_msg = f"HOLD({self.lost_frame_count})" if self.lost_frame_count > 0 else f"LOCKED ID:{self.locked_id}"
                    
                    self.last_valid_yaw, self.last_valid_state = target_yaw, drive_state
                    self.serial.set_target_data(target_yaw, drive_state) 

                    bx, by, bw, bh = best_target["box"]
                    cv2.rectangle(frame, (int(bx-bw/2), int(by-bh/2)), (int(bx+bw/2), int(by+bh/2)), color, 3)
                    cv2.putText(frame, f"{state_msg} [{self.locked_type}]", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                else:
                    state_text = f"SEARCHING (Timeout: {TRACKING_TIMEOUT - (current_time - self.last_seen_time):.1f}s)" if self.locked_id else "NORMAL"
                    self.last_valid_state = 4
                    self.serial.set_target_data(self.last_valid_yaw, self.last_valid_state)
                    cv2.putText(frame, state_text, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                with frame_lock: global_output_frame = frame.copy()
            except Exception as e: 
                print(f"[에러 발생] 추론 중 문제가 발생했습니다: {e}")
            time.sleep(0.005)

    def stop(self): self.stopped = True

# ===========================================================================
# [메인 실행부] 로컬 GUI 출력(imshow) 
# ===========================================================================
if __name__ == "__main__":
    cam = CameraStream(src=0)
    serial_comm = SerialCommunicator(port='/dev/ttyAMA0', baudrate=115200)
    ai_engine = InferenceEngine(cam, serial_comm)
    
    try:
        while True:
            with frame_lock:
                display_frame = global_output_frame.copy() if global_output_frame is not None else None
            
            if display_frame is not None:
                cv2.imshow("AI Tracking Control (Press 'q' to exit)", display_frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            time.sleep(0.01) 
            
    finally:
        cam.stop()
        ai_engine.stop()
        serial_comm.stop()
        cv2.destroyAllWindows()