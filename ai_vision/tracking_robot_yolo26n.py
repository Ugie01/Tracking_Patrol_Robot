import cv2             # 영상 처리 및 컴퓨터 비전 알고리즘을 위한 OpenCV 라이브러리
import time            # 프레임 간 지연 시간 및 타임아웃 계산을 위한 표준 시간 모듈
import threading       # 카메라, 시리얼 통신, 웹, AI 추론의 비동기 병렬 처리를 위한 멀티스레딩 모듈
import math            # FOV(시야각) 기반 각도 계산 등 수학적 연산을 수행하기 위한 모듈
import struct          # 시리얼 통신 시 C언어 구조체와 float 데이터를 맞추기 위한 바이트 패킹 모듈
import serial          # 하위 모터 제어 보드와의 UART 직렬 통신을 위한 모듈
import numpy as np     # 고속 배열 및 행렬 연산을 처리하기 위한 넘파이 모듈
from flask import Flask, Response, render_template_string # 웹 기반 원격 관제 스트리밍 서버 구축용
from ultralytics import YOLO # 최신 객체 및 자세 추정 딥러닝 모델(YOLOv8 기반)

# ===========================================================================
# [하이퍼파라미터 설정] - 제어 및 임계치 상수 정의
# ===========================================================================
# 1. 쓰러짐(FALLEN) 감지 기하학적 임계값
FALL_LATERAL_RATIO = 1.0        
FALL_AXIAL_RATIO = 0.55         
FALL_CHEST_LOW_THRESH = 0.30    

# 2. 이상행동(ABNORMAL) 감지 임계값
PUNCH_REACH_RATIO = 0.60         
WEAPON_PROXIMITY_THRESH = 70.0   
WEAPON_DIST_SQ_THRESH = WEAPON_PROXIMITY_THRESH ** 2  

# 3. 로봇 주행 제어 임계값 (바운딩 박스 높이 비율 기준)
DRIVE_REVERSE_THRESH = 0.90      
DRIVE_STOP_THRESH = 0.75         

# 4. 쓰러진 객체 전용 접근 제어 임계값
FALL_DRIVE_STOP_THRESH = 0.60    
FALL_DRIVE_REVERSE_THRESH = 0.75 

# 5. 위협 상황별 제어 우선순위
PRIORITY = {"FALLEN": 3, "ABNORMAL": 2, "FIRE": 1, "NORMAL": 0} 

# 6. 비전 및 렌즈 물리 스펙
MODEL_PATH = "yolo26n-pose.pt"   
FRAME_W, FRAME_H = 640, 480      
CENTER_X = FRAME_W / 2           
H_FOV = 40.1                     
focal_length = CENTER_X / math.tan(math.radians(H_FOV / 2.0)) 

# 7. 추적(MOT) 및 재식별(Re-ID) 파라미터
TRACKING_TIMEOUT = 10.0         
REID_SIMILARITY_THRESH = 0.50   
KP_CONF_THRESH = 0.75            
MAX_LOST_FRAMES_BUFFER = 30     

# 8. 화재 연동 온도 가중치 파라미터
FIRE_TEMP_BASE = 40.0            
FIRE_TEMP_WEIGHT = 0.02          
FIRE_FINAL_CONF_THRESH = 0.60    

# 9. 클래스 맵핑 넘버
CLS_PERSON = 0
CLS_FIRE = 41
CLS_WEAPON = 67

# Flask 다중 스레드 동기화 객체
app = Flask(__name__)           
global_output_frame = None      
frame_lock = threading.Lock()   
new_frame_event = threading.Event() 

# 커스텀 11개 키포인트 인덱스 정의
KP_FACE, KP_CHEST, KP_HIP = 0, 1, 2
KP_R_FOOT, KP_L_FOOT = 3, 4
KP_R_SHOULDER, KP_L_SHOULDER = 5, 8
KP_R_ELBOW, KP_L_ELBOW = 6, 9
KP_R_WRIST, KP_L_WRIST = 7, 10

# 시각화 뼈대 연결 구조 정의
SKELETON_EDGES = [
    (KP_FACE, KP_CHEST), (KP_CHEST, KP_HIP), 
    (KP_CHEST, KP_R_SHOULDER), (KP_CHEST, KP_L_SHOULDER),
    (KP_R_SHOULDER, KP_R_ELBOW), (KP_R_ELBOW, KP_R_WRIST),
    (KP_L_SHOULDER, KP_L_ELBOW), (KP_L_ELBOW, KP_L_WRIST),
    (KP_HIP, KP_R_FOOT), (KP_HIP, KP_L_FOOT)
]

# ===========================================================================
# [알고리즘 함수군] - 휴리스틱 뼈대 연산 가동
# ===========================================================================
def remap_coco_to_custom(coco_kpts):
    custom_kpts = np.zeros((11, 3))
    if len(coco_kpts) < 17: return custom_kpts         
    
    def get_pt(idx):
        if idx >= len(coco_kpts): return np.array([0.0, 0.0, 0.0])
        pt = coco_kpts[idx]
        if len(pt) >= 3: return np.array([pt[0], pt[1], pt[2]])
        return np.array([pt[0], pt[1], 1.0 if (pt[0] > 0 and pt[1] > 0) else 0.0])

    custom_kpts[KP_FACE]       = get_pt(0)   
    custom_kpts[KP_L_SHOULDER] = get_pt(5)   
    custom_kpts[KP_R_SHOULDER] = get_pt(6)   
    custom_kpts[KP_L_ELBOW]    = get_pt(7)   
    custom_kpts[KP_R_ELBOW]    = get_pt(8)   
    custom_kpts[KP_L_WRIST]    = get_pt(9)   
    custom_kpts[KP_R_WRIST]    = get_pt(10)  
    custom_kpts[KP_L_FOOT]     = get_pt(15)  
    custom_kpts[KP_R_FOOT]     = get_pt(16)  

    ls = custom_kpts[KP_L_SHOULDER]
    rs = custom_kpts[KP_R_SHOULDER]
    if ls[2] > 0 and rs[2] > 0:
        custom_kpts[KP_CHEST] = [(ls[0] + rs[0]) / 2.0, (ls[1] + rs[1]) / 2.0, min(ls[2], rs[2])]

    lh = get_pt(11)
    rh = get_pt(12)
    if lh[2] > 0 and rh[2] > 0:
        custom_kpts[KP_HIP] = [(lh[0] + rh[0]) / 2.0, (lh[1] + rh[1]) / 2.0, min(lh[2], rh[2])]

    return custom_kpts

def get_color_hist(frame, bx, by, bw, bh):
    core_w, core_h = bw * 0.7, bh * 0.5
    x1, y1 = max(0, int(bx - core_w/2)), max(0, int(by - core_h/2))
    x2, y2 = min(FRAME_W, int(bx + core_w/2)), min(FRAME_H, int(by + core_h/2))
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0: return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist

def analyze_behavior(kpts, bw, bh, weapon_centers):
    """ 간섭 방지를 위해 낙상을 최상단에서 우선 조기 차단(Early Exit)합니다. """
    def is_valid(idx): 
        return kpts[idx][2] > KP_CONF_THRESH if idx < len(kpts) else False

    aspect_ratio = bw / bh if bh > 0 else 0

    # 1. 최우선 낙상 판별
    if aspect_ratio > 0.5 and is_valid(KP_CHEST) and is_valid(KP_HIP):
        chest_y_frame = kpts[KP_CHEST][1] / FRAME_H 
        t_x = abs(kpts[KP_CHEST][0] - kpts[KP_HIP][0])
        t_y = abs(kpts[KP_CHEST][1] - kpts[KP_HIP][1])

        if t_x > (t_y * FALL_LATERAL_RATIO): return "FALLEN"
        if is_valid(KP_R_SHOULDER) and is_valid(KP_L_SHOULDER):
            shoulder_w = abs(kpts[KP_R_SHOULDER][0] - kpts[KP_L_SHOULDER][0])
            if shoulder_w > 0 and t_y < (shoulder_w * FALL_AXIAL_RATIO) and chest_y_frame > 0.40:
                return "FALLEN"

    # 2. 이상행동 판별부
    weapon_held = False
    for w_idx in [KP_R_WRIST, KP_L_WRIST]:
        if is_valid(w_idx):
            wx, wy = kpts[w_idx][0], kpts[w_idx][1]
            for wbx, wby in weapon_centers:
                if (wx - wbx)**2 + (wy - wby)**2 < WEAPON_DIST_SQ_THRESH and wy < kpts[KP_HIP][1]:
                    weapon_held = True; break

    punch_detected = False
    if is_valid(KP_CHEST) and bh > 0:
        for w_idx in [KP_R_WRIST, KP_L_WRIST]:
            if is_valid(w_idx):
                is_punching = abs(kpts[w_idx][0] - kpts[KP_CHEST][0]) > (bw * 0.45) and kpts[w_idx][1] < kpts[KP_CHEST][1]
                is_raising_arm = kpts[w_idx][1] < (kpts[KP_CHEST][1] - (bh * 0.30))
                if is_punching or is_raising_arm:
                    punch_detected = True; break

    kick_detected = False
    if is_valid(KP_HIP) and bh > 0:
        for f_idx in [KP_R_FOOT, KP_L_FOOT]:
            if is_valid(f_idx):
                if aspect_ratio <= 0.6: # 낙상 과도기 연산 간섭 제거용 필터링
                    if kpts[f_idx][1] < kpts[KP_HIP][1] + (bh * 0.25):
                        kick_detected = True; break

    if weapon_held or punch_detected or kick_detected: return "ABNORMAL"
    return "NORMAL"

# ===========================================================================
# [하드웨어 모듈] - 기존 클래스 구조 유지
# ===========================================================================
class CameraStream:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src, cv2.CAP_V4L2)
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
# [모듈] 메인 AI 추론 엔진 (위험인물 상태 영구 박제 및 원천 고정 구현완료)
# ===========================================================================
class InferenceEngine:
    def __init__(self, camera, serial_comm):
        self.camera = camera
        self.serial = serial_comm
        self.model = YOLO(MODEL_PATH)
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
        prev_time = time.time() 
        
        while not self.stopped:
            frame = self.camera.read()
            self.serial.request_yaw()
            self.serial.request_temp()
            curr_yaw = self.serial.get_yaw()
            curr_temp = self.serial.get_temp()
            if frame is None: continue

            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time + 1e-6)
            prev_time = curr_time

            try:
                results = self.model.track(frame, tracker="bytetrack.yaml", persist=True, verbose=False, classes=[CLS_PERSON, CLS_FIRE, CLS_WEAPON], imgsz=320, conf=0.20)
                
                weapon_centers = []
                candidates = []
                current_time = time.time()

                if results and results[0].boxes:
                    for i, box_obj in enumerate(results[0].boxes):
                        cls = int(box_obj.cls[0])
                        conf = float(box_obj.conf[0].cpu().numpy())
                        box_xywh = box_obj.xywh[0].cpu().numpy()
                        bx, by, bw, bh = box_xywh
                        
                        if cls == CLS_WEAPON: 
                            weapon_centers.append((bx, by))
                            continue
                        
                        if cls == CLS_FIRE: 
                            temp_bonus = max(0.0, curr_temp - FIRE_TEMP_BASE) * FIRE_TEMP_WEIGHT
                            final_conf = min(1.0, conf + temp_bonus)
                            if final_conf < FIRE_FINAL_CONF_THRESH: continue
                            candidates.append({"id": -1, "type": "FIRE", "prio": PRIORITY["FIRE"], "box": box_xywh, "center": (bx, by), "height_ratio": bh/FRAME_H, "status": "FIRE", "hist": None, "conf": final_conf, "kpts": None})
                            continue

                        track_id = int(box_obj.id[0]) if box_obj.id is not None else -1
                        current_status = "NORMAL"
                        valid_kpts = None
                        
                        if results[0].keypoints is not None and len(results[0].keypoints.data) > i:
                            coco_kpts = results[0].keypoints.data[i].cpu().numpy()
                            custom_kpts = remap_coco_to_custom(coco_kpts)
                            current_status = analyze_behavior(custom_kpts, bw, bh, weapon_centers)
                            valid_kpts = custom_kpts

                        candidates.append({
                            "id": track_id, "type": current_status, "prio": PRIORITY[current_status],
                            "box": box_xywh, "center": (bx, by), "height_ratio": bh/FRAME_H,
                            "status": current_status, "hist": get_color_hist(frame, bx, by, bw, bh),
                            "conf": conf, "kpts": valid_kpts
                        })

                # 🌟 추적 코어 1단계: 기존 타겟 유지 및 원래 고유 ID/위험 상태 복원 공정
                best_target = None
                if self.locked_id is not None:
                    matched = [c for c in candidates if c["id"] == self.locked_id]
                    
                    # 피드백 반영: Re-ID 성공 시 새로 튀어 나온 가짜 ID를 원래 고유 록온 ID로 영구 치환
                    if not matched and candidates:
                        highest_sim = 0
                        reid_candidate = None
                        for c in candidates:
                            if c["id"] != -1 and c["hist"] is not None and self.locked_hist is not None:
                                sim = cv2.compareHist(self.locked_hist, c["hist"], cv2.HISTCMP_CORREL)
                                if sim > highest_sim: highest_sim = sim; reid_candidate = c
                        if highest_sim > REID_SIMILARITY_THRESH and reid_candidate is not None:
                            reid_candidate["id"] = self.locked_id 
                            matched = [reid_candidate]

                    if matched:
                        best_target = matched[0]
                        # 🌟 [기획 수정 핵심]: 팔을 내리거나 얌전해지더라도(NORMAL 복귀 시)
                        # 최초에 록온되었을 당시 기록된 고유 위험 딱지(self.locked_type)를 지우지 않고 무조건 덮어씌워 강제 보전합니다.
                        best_target["status"] = self.locked_type
                        best_target["type"] = self.locked_type
                        
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

                # 🌟 추적 코어 2단계: 신규 타겟 발굴 (NORMAL 차단 요건 유지)
                if self.locked_id is None and candidates:
                    # 오직 최초 시점에 위험 점수가 0점보다 높은(ABNORMAL, FALLEN, FIRE) 대상만 록온 풀에 등록
                    valid_candidates = [c for c in candidates if c["prio"] > 0 and c["id"] != -1]
                    if valid_candidates:
                        best_target = max(valid_candidates, key=lambda c: c["prio"])
                        self.locked_id = best_target["id"]
                        self.locked_type = best_target["type"] # 최초 위협 상태 영구 저장
                        self.locked_hist = best_target["hist"]
                        self.last_seen_time = current_time
                        self.lost_frame_count = 0
                        self.last_known_target = best_target
                    else:
                        best_target = None

                # 4단계: 디스플레이 렌더링 및 제어 명령 송신
                for c in candidates:
                    cbx, cby, cbw, cbh = c["box"]
                    c_status = c["status"]
                    c_conf = c["conf"]
                    c_kpts = c["kpts"]
                    
                    # 현재 록온된 타겟이라면 화면에 표시할 개별 자막 상태도 오리지널 록온 유형으로 변환
                    is_locked = (self.locked_id is not None and self.locked_id == c["id"])
                    if is_locked:
                        c_status = self.locked_type
                        box_color = (0, 255, 0) # 타겟은 무조건 초록색 볼드 박스 고정
                        thickness = 4
                    else:
                        if c_status == "NORMAL": box_color = (0, 255, 255)      
                        elif c_status == "ABNORMAL": box_color = (0, 0, 255)    
                        elif c_status == "FALLEN": box_color = (255, 0, 0)      
                        elif c_status == "FIRE": box_color = (0, 165, 255)      
                        thickness = 2

                    cv2.rectangle(frame, (int(cbx-cbw/2), int(cby-cbh/2)), (int(cbx+cbw/2), int(cby+cbh/2)), box_color, thickness)
                    cv2.putText(frame, f"ID:{c['id']} [{c_status}] {c_conf:.2f}", (int(cbx-cbw/2), int(cby-cbh/2)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

                    # 관절 상시 표시
                    if c_kpts is not None and len(c_kpts) == 11:
                        def pt_valid(idx): return c_kpts[idx][2] > KP_CONF_THRESH
                        for u, v in SKELETON_EDGES:
                            if pt_valid(u) and pt_valid(v):
                                pt1 = (int(c_kpts[u][0]), int(c_kpts[u][1]))
                                pt2 = (int(c_kpts[v][0]), int(c_kpts[v][1]))
                                cv2.line(frame, pt1, pt2, (255, 105, 180), 2)
                        for i in range(len(c_kpts)):
                            if pt_valid(i):
                                px, py = int(c_kpts[i][0]), int(c_kpts[i][1])
                                cv2.circle(frame, (px, py), 4, (0, 255, 255), -1)

                if best_target is not None:
                    bx, by = best_target["center"]
                    c_kpts = best_target["kpts"]
                    core_x, core_y = bx, by
                    
                    if c_kpts is not None and len(c_kpts) == 11:
                        def kpt_valid(idx): return c_kpts[idx][2] > KP_CONF_THRESH
                        if kpt_valid(KP_CHEST) and kpt_valid(KP_HIP):
                            core_x = (c_kpts[KP_CHEST][0] + c_kpts[KP_HIP][0]) / 2.0
                            core_y = (c_kpts[KP_CHEST][1] + c_kpts[KP_HIP][1]) / 2.0
                        elif kpt_valid(KP_CHEST):
                            core_x = c_kpts[KP_CHEST][0]
                            core_y = c_kpts[KP_CHEST][1]
                        elif kpt_valid(KP_L_SHOULDER) and kpt_valid(KP_R_SHOULDER):
                            core_x = (c_kpts[KP_L_SHOULDER][0] + c_kpts[KP_R_SHOULDER][0]) / 2.0
                            core_y = (c_kpts[KP_L_SHOULDER][1] + c_kpts[KP_R_SHOULDER][1]) / 2.0
                        elif kpt_valid(KP_FACE):
                            core_x = c_kpts[KP_FACE][0]
                            core_y = c_kpts[KP_FACE][1]
                            
                    vis_error = math.degrees(math.atan((core_x - CENTER_X) / focal_length))
                    if abs(vis_error) < 2.0: vis_error = 0.0

                    target_yaw = curr_yaw + vis_error
                    if target_yaw > 180: target_yaw -= 360
                    elif target_yaw < -180: target_yaw += 360

                    bx, by, bw, bh = best_target["box"]
                    t_status = best_target["status"]

                    if t_status == "FALLEN":
                        max_ratio = max(bw / FRAME_W, bh / FRAME_H)
                        stop_th = FALL_DRIVE_STOP_THRESH
                        rev_th = FALL_DRIVE_REVERSE_THRESH
                        current_ratio = max_ratio
                    else:
                        stop_th = DRIVE_STOP_THRESH
                        rev_th = DRIVE_REVERSE_THRESH
                        current_ratio = best_target["height_ratio"]

                    drive_state = 2 if current_ratio >= rev_th else 1 if current_ratio >= stop_th else 0
                    
                    self.last_valid_yaw, self.last_valid_state = target_yaw, drive_state
                    self.serial.set_target_data(target_yaw, drive_state)

                    # 조향 기준선 시각화 직선 작도 유지
                    cv2.line(frame, (int(CENTER_X), FRAME_H), (int(core_x), int(core_y)), (0, 255, 0), 2)
                    cv2.putText(frame, f"Err: {vis_error:.1f}deg | Target Yaw: {target_yaw:.1f}deg", 
                                (int((CENTER_X + core_x)/2) - 80, int((FRAME_H + core_y)/2)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
                    
                    state_msg = f"HOLD({self.lost_frame_count})" if self.lost_frame_count > 0 else f"LOCKED ID:{self.locked_id}"
                    cv2.putText(frame, f"{state_msg} [{self.locked_type}]", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    print(f"[INFO] FPS: {fps:.1f} | Curr Yaw: {curr_yaw:.1f} | Target Yaw: {target_yaw:.1f} | ID: {self.locked_id} | State: {self.locked_type} | Conf: {best_target['conf']:.2f}")
                else:
                    self.last_valid_state = 4
                    self.serial.set_target_data(self.last_valid_yaw, self.last_valid_state)
                    state_text = f"SEARCHING (Timeout: {TRACKING_TIMEOUT - (current_time - self.last_seen_time):.1f}s)" if self.locked_id else "NORMAL"
                    cv2.putText(frame, state_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    print(f"[INFO] FPS: {fps:.1f} | Curr Yaw: {curr_yaw:.1f} | SEARCHING...")

                with frame_lock: global_output_frame = frame.copy()
                new_frame_event.set()
            except Exception as e: pass
            time.sleep(0.005)

    def stop(self): self.stopped = True

# ===========================================================================
# [웹 모듈] Flask 비동기 스트리밍 (640x480, Quality 85 화질 보존)
# ===========================================================================
def generate_frames():
    global global_output_frame
    while True:
        new_frame_event.wait(); new_frame_event.clear()
        with frame_lock:
            if global_output_frame is None: continue
            frame_resized = cv2.resize(global_output_frame, (FRAME_W, FRAME_H)) 
        ret, buffer = cv2.imencode(".jpg", frame_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if ret: yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

@app.route("/")
def index():
    return render_template_string('<html><body style="text-align:center;background:#222;color:white;"><h1>AI 관제</h1><img src="/video_feed" width="640" height="480"/></body></html>')

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    cam = CameraStream(src=0)
    serial_comm = SerialCommunicator(port='/dev/ttyAMA0', baudrate=115200)
    ai_engine = InferenceEngine(cam, serial_comm)
    try: 
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False)
    finally:
        cam.stop(); ai_engine.stop(); serial_comm.stop()