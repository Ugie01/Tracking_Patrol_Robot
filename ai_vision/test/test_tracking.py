import cv2
import time
import threading
import serial
import math
import struct
from flask import Flask, Response, render_template_string
from ultralytics import YOLO

# ===========================================================================
# [글로벌 설정]
# ===========================================================================
MODEL_PATH = "yolo26n-pose.pt"
FRAME_W, FRAME_H = 640, 480
CENTER_X = FRAME_W / 2
H_FOV = 41.1
focal_length = CENTER_X / math.tan(math.radians(H_FOV / 2.0))

PRIORITY = {"NORMAL": 0, "THREAT": 1, "FIRE": 2, "EMERGENCY": 3}
CLASS_MAP = {0: "Person", 41: "Fire", 67: "Weapon"}

# 타겟 유실 시 블러 버퍼 유지 최대 프레임 수
MAX_LOST_FRAMES = 5
# 거리 측정 기준값 (객체의 높이가 화면 높이의 50% 이상이면 정지)
STOP_THRESHOLD_RATIO = 0.90

app = Flask(__name__)
global_output_frame = None
frame_lock = threading.Lock()
new_frame_event = threading.Event()

KP_FACE       = 0
KP_CHEST      = 1  # 가슴
KP_L_SHOULDER = 2
KP_L_ELBOW    = 3
KP_L_WRIST    = 4
KP_R_SHOULDER = 5
KP_R_ELBOW    = 6
KP_R_WRIST    = 7
KP_HIP        = 8   # 엉덩이
KP_L_FOOT     = 9   # 왼쪽 발
KP_R_FOOT     = 10  # 오른쪽 발

# ===========================================================================
# [모듈 1] I/O 스레드: 카메라 프레임 수집
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
        
        if not self.cap.isOpened():
            print("[ERROR] 카메라를 열 수 없습니다.")
            exit()
            
            
        self.ret, self.frame = self.cap.read()
        self.lock = threading.Lock()
        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        while not self.stopped:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            time.sleep(0.005) # 과부하 방지

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.stopped = True
        self.cap.release()

# ===========================================================================
# [모듈 2] I/O 스레드: 시리얼 통신 (미래 확장용)
# ===========================================================================
class SerialCommunicator:
    def __init__(self, port='/dev/ttyAMA0', baudrate=115200):
        self.current_yaw = 0.0
        self.current_temp = 0.0
        self.target_data = 0.0
        self.stopped = False
        
        self.temp_trigger_event = threading.Event()
        self.yaw_trigger_event = threading.Event()
        self.lock = threading.Lock()

        self.target_yaw = 0.0
        self.stop_signal = 0
        
        try:
            self.ser = serial.Serial(port, baudrate, timeout=0.05)
            print(f"[INFO] 시리얼 포트 연결 성공: {port}")
        except Exception as e:
            print(f"[ERROR] 시리얼 연결 실패: {e}")
            self.ser = None

        self.serial_thread = threading.Thread(target=self.run, daemon=True)
        self.serial_thread.start()

    def run(self):
        if not self.ser: return
        
        last_poll_time = time.time()
        poll_interval = 0.05  # 20Hz 주기로 target 데이터 전송

        while not self.stopped:
            current_time = time.time()

            # 1. 트리거 처리: 온도 요청 플래그 확인
            if self.temp_trigger_event.is_set():
                self.ser.write(bytes([0xAA, 0x0A, 0x55]))
                self.temp_trigger_event.clear()
                self.receive_response('T')

            # 2. 트리거 처리: Yaw 요청 플래그 확인
            if self.yaw_trigger_event.is_set():
                self.ser.write(bytes([0xAA, 0x0B, 0x55]))
                self.yaw_trigger_event.clear()
                self.receive_response('Y')

            # 3. 폴링 처리: 주기적으로 타겟 데이터 전송
            if current_time - last_poll_time >= poll_interval and self.target_yaw is not None:
                with self.lock:
                    payload = f"t{self.target_yaw:.2f},{self.stop_signal}\n"        # 0, 1, 2로 전진, 정지, 후진 신호 전송
                self.ser.write(payload.encode('utf-8'))
                last_poll_time = current_time

            time.sleep(0.001)  # 루프 속도 조절

    def receive_response(self, data_type):
        """트리거 송신 직후 해당 데이터의 응답을 수신 및 파싱"""
        # 응답이 올 때까지 최대 0.1초 대기
        packet = self.ser.read(4)
        if len(packet) < 4:
            print("센서 데이터 미수신")
            return None

        try:
            val = struct.unpack('<f', packet)[0]
            with self.lock:
                if data_type == 'T':
                    self.current_temp = val
                elif data_type == 'Y':
                    if val == 0.0:
                        self.current_yaw = self.target_data  # 타겟 데이터로 보정
                    else:
                        self.current_yaw = val

        except ValueError:
            pass # 파싱 에러 시 무시

    def request_temp(self):
        """외부 스레드에서 온도를 가져오고 싶을 때 호출"""
        self.temp_trigger_event.set()

    def request_yaw(self):
        """외부 스레드에서 Yaw 값을 가져오고 싶을 때 호출"""
        self.yaw_trigger_event.set()

    def get_temp(self):
        """다른 스레드에서 센서 데이터를 읽어갈 때 사용"""
        with self.lock:
            return self.current_temp
        
    def get_yaw(self):
        """다른 스레드에서 센서 데이터를 읽어갈 때 사용"""
        with self.lock:
            return self.current_yaw

    def set_target_data(self, yaw_val, stop_val):
        """계산 스레드에서 STM32로 보낼 목표 각도 및 정지 신호 업데이트"""
        with self.lock:
            self.target_yaw = yaw_val
            self.stop_signal = stop_val

    def stop(self):
        self.stopped = True
        if self.ser: self.ser.close()

# ===========================================================================
# [모듈 2] 메인 AI 추론 엔진 (비전 + IMU 결합)
# ===========================================================================
class InferenceEngine:
    def __init__(self, camera, serial_comm):
        self.camera = camera
        self.serial = serial_comm
        self.model = YOLO(MODEL_PATH)
        self.stopped = False
        self.lost_counter = 0
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
            curr_temp = self.serial.get_temp()
            if frame is None: continue

            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time
            
            try:
                results = self.model(frame, verbose=False, stream=True, classes=[0, 41, 67], imgsz=320)
                # 🌟 구조체 초기화 단순화 (distance 대신 height_ratio 저장)
                best_target = {"prio": -1, "label": "None", "vis_error": 0.0, "box": None, "center": None, "height_ratio": 0.0}

                cv2.line(frame, (int(CENTER_X), 0), (int(CENTER_X), FRAME_H), (100, 100, 100), 1)
                
                if results is not None:
                    for r in results:
                        if r.boxes:
                            for i, box_obj in enumerate(r.boxes):
                                cls = int(box_obj.cls[0])
                                label = CLASS_MAP.get(cls, "Unknown")
                                b = box_obj.xywh[0].cpu().numpy()
                                tx, ty = float(b[0]), float(b[1]) 
                                
                                # 🌟 [교정] 모든 객체의 화면 높이 대비 박스 크기 비율 상시 계산
                                bx, by, bw, bh = b
                                box_height_ratio = bh / float(FRAME_H)
                                
                                # 조향용 중심점(tx, ty)을 잡기 위한 최소한의 키포인트 평균 필터는 유지
                                if label == "Person" and r.keypoints is not None and len(r.keypoints.data) > i:
                                    kpts = r.keypoints.data[i].cpu().numpy() 
                                    valid_x, valid_y = [], []
                                    for kp in kpts:
                                        if kp[2] > 0.5:
                                            valid_x.append(kp[0])
                                            valid_y.append(kp[1])
                                            cv2.circle(frame, (int(kp[0]), int(kp[1])), 3, (0, 255, 0), -1)
                                    if len(valid_x) > 0:
                                        tx = sum(valid_x) / len(valid_x)
                                        ty = sum(valid_y) / len(valid_y)

                                vis_error = math.degrees(math.atan((tx - CENTER_X) / focal_length))
                                if abs(vis_error) < 2.0: vis_error = 0.0

                                prio = PRIORITY.get(label.upper(), 0)
                                if label == "Person" and (b[2]/b[3] > 1.2): prio = PRIORITY["EMERGENCY"]

                                if prio > best_target["prio"]:
                                    best_target.update({
                                        "prio": prio, "label": label, "vis_error": vis_error, 
                                        "box": b, "center": (tx, ty), 
                                        "height_ratio": box_height_ratio  # 비율 데이터 저장
                                    })

                    curr_yaw = self.serial.get_yaw() 
                    
                    if best_target["box"] is not None:
                        self.lost_counter = 0  
                        target_yaw = curr_yaw + best_target["vis_error"] 
                        if target_yaw > 180: target_yaw -= 360
                        elif target_yaw < -180: target_yaw += 360
                        
                        # 모든 클래스 통합 단순/명쾌한 박스 비율 제어 트리거
                        ratio = best_target["height_ratio"]
                        if ratio < 0.75:
                            drive_state = 0  # FORWARD (화면의 반보다 작게 보이면 쫓아감)
                        elif 0.75 <= ratio <= STOP_THRESHOLD_RATIO: 
                            drive_state = 1  # STOP (안전 버퍼 존 정지)
                        else:
                            drive_state = 2  # REVERSE (화면의 90% 이상 꽉 차면 위험하므로 후진)
                            
                        state_text = "FORWARD" if drive_state == 0 else "STOP" if drive_state == 1 else "REVERSE"
                        self.last_valid_yaw = target_yaw
                        self.last_valid_state = drive_state
                        self.serial.set_target_data(target_yaw, drive_state)

                        color = (0, 0, 255) if best_target["prio"] >= 2 else (0, 255, 255)
                        bx, by, bw, bh = best_target["box"]
                        cv2.rectangle(frame, (int(bx-bw/2), int(by-bh/2)), (int(bx+bw/2), int(by+bh/2)), color, 2)
                        cv2.circle(frame, (int(tx), int(ty)), 6, (0, 0, 255), -1)
                        cv2.line(frame, (int(CENTER_X), FRAME_H), (int(tx), int(ty)), color, 2)
                        
                        # 🌟 직관적 디버깅을 위해 화면 오버레이를 Ratio 수치로 즉시 모니터링 매핑
                        cv2.putText(frame, f"Ratio: {ratio:.2f} [{state_text}]", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                        cv2.putText(frame, f"IMU: {curr_yaw:.1f} | Temp: {curr_temp:.1f}C", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
                        print(f"\r[STATUS] FPS: {fps:>4.1f} | IMU: {curr_yaw:>6.1f}° | Ratio: {ratio:>4.2f} | Goal: {target_yaw:>6.1f}deg | State: {state_text:<7}\033[K", end="", flush=True)
                        
                    else:
                        self.lost_counter += 1
                        if self.lost_counter >= MAX_LOST_FRAMES:
                            self.last_valid_state = 4
                        self.serial.set_target_data(self.last_valid_yaw, self.last_valid_state)   
                        state_text = f"HOLD({self.lost_counter})" if self.last_valid_state != 4 else "LOST"

                        cv2.putText(frame, f"No Target Detected [{state_text}]", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 2)
                        cv2.putText(frame, f"IMU: {curr_yaw:.1f} | Temp: {curr_temp:.1f}C", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
                        print(f"\r[STATUS] FPS: {fps:>4.1f} | IMU: {curr_yaw:>6.1f}° | Temp: {curr_temp:>5.1f}°C | Goal:  None   | State: {state_text:<7}\033[K", end="", flush=True)
                    
                with frame_lock:
                    global_output_frame = frame.copy()
                new_frame_event.set()

            except Exception as e:
                print(f"\n[ERROR] {e}")

            time.sleep(0.005)

    def stop(self):
        self.stopped = True

# ===========================================================================
# [모듈 4] Flask 웹 스트리밍 라우터
# ===========================================================================
def generate_frames():
    global global_output_frame
    while True:
        # 새 프레임이 들어올 때까지 여기서 대기 (CPU 무한루프 점유 방지)
        new_frame_event.wait()
        new_frame_event.clear()

        with frame_lock:
            if global_output_frame is None:
                continue
            # 원본 연산에 영향이 안 가도록 크기를 절반으로 줄여서 전송 (스트리밍 속도 극대화)
            # 웹 모니터링용이므로 해상도가 조금 낮아도 판단에 무리가 없습니다.
            frame_resized = cv2.resize(global_output_frame, (320, 240)) 
            
        # JPEG 인코딩 퀄리티를 70%로 낮춰서 압축/전송 속도 2배 이상 향상
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
        ret, buffer = cv2.imencode('.jpg', frame_resized, encode_param)
        
        if not ret: continue
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    html = """
    <html>
        <head>
            <title>Robot Vision Tracker</title>
            <style> body { text-align: center; background-color: #222; color: white; font-family: sans-serif; } </style>
        </head>
        <body>
            <h1>Real-Time AI Tracking Dashboard</h1>
            <img src="/video_feed" width="640" height="480" style="border: 2px solid white; border-radius: 10px;" />
        </body>
    </html>
    """
    return render_template_string(html)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ===========================================================================
# [실행부] 메인 로직 
# ===========================================================================
if __name__ == '__main__':
    print("[INFO] 시스템 초기화 중...")
    cam = CameraStream(src=0)
    time.sleep(1.0) # 카메라 예열 대기
    
    serial_comm = SerialCommunicator()
    ai_engine = InferenceEngine(cam, serial_comm)
    
    print("[INFO] Flask 웹 서버를 시작합니다. (http://<라즈베리파이IP>:5000 접속)")
    
    try:
        # Flask 서버 실행 (메인 스레드 차단)
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[INFO] 강제 종료 신호 감지. 자원을 해제합니다...")
    finally:
        cam.stop()
        ai_engine.stop()
        serial_comm.stop()
        print("[INFO] 시스템이 안전하게 종료되었습니다.")