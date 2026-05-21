# OpenCV 라이브러리를 불러와 이미지 및 영상 처리를 수행하는 것
import cv2
# 프레임 간 지연 시간 및 타임스탬프를 계산하기 위한 시간 모듈을 불러오는 것
import time
# 카메라, 시리얼 통신, AI 추론을 동시에 비동기적으로 실행하기 위한 스레딩 모듈을 불러오는 것
import threading
# FOV(시야각) 기반 각도 계산 등 수학적 연산을 수행하기 위한 모듈을 불러오는 것
import math
# 시리얼 통신으로 들어오는 바이너리(바이트) 데이터를 파싱하기 위한 모듈을 불러오는 것
import struct
# ST와의 직렬(Serial) 통신을 위한 모듈을 불러오는 것
import serial
# 배열 및 행렬 연산을 고속으로 처리하기 위한 넘파이 모듈을 불러오는 것
import numpy as np
# 웹 서버 구동 및 카메라 영상 비동기 스트리밍을 위한 플라스크 모듈을 불러오는 것
from flask import Flask, Response, render_template_string
# 객체 탐지 및 포즈 추정을 수행할 YOLO AI 모델 모듈을 불러오는 것
from ultralytics import YOLO

# ===========================================================================
# [하이퍼파라미터 설정] - 시스템 제어 및 임계치 상수 정의
# ===========================================================================
# 측면으로 쓰러짐을 판별하기 위한 가로/세로 비율 임계값을 설정하는 것
FALL_LATERAL_RATIO = 1.0        
# 정면/후면으로 쓰러짐을 판별하기 위한 어깨너비 대비 높이 비율 임계값을 설정하는 것
FALL_AXIAL_RATIO = 0.55         
# 화면 상에서 가슴의 위치가 특정 높이 이하(아래쪽)로 내려갔는지 판별하는 임계값을 설정하는 것
FALL_CHEST_LOW_THRESH = 0.30    

# 주먹질(펀치) 판별을 위해 팔을 뻗은 거리가 박스 너비의 몇 % 이상인지 설정하는 것
PUNCH_REACH_RATIO = 0.60         
# 손목과 무기 사이의 근접 판별을 위한 최대 픽셀 거리를 설정하는 것
WEAPON_PROXIMITY_THRESH = 70.0   
# 거리 계산 시 제곱근 연산을 생략하여 속도를 높이기 위해 거리의 제곱 값을 미리 계산해두는 것
WEAPON_DIST_SQ_THRESH = WEAPON_PROXIMITY_THRESH ** 2  

# 정상 서 있는 객체가 화면에 너무 크게 잡힐 경우 후진 명령을 내리기 위한 높이 비율 임계값을 설정하는 것
DRIVE_REVERSE_THRESH = 0.90      
# 정상 서 있는 객체가 적당히 가까워졌을 때 정지 명령을 내리기 위한 높이 비율 임계값을 설정하는 것
DRIVE_STOP_THRESH = 0.75         

# 쓰러진 객체 전체 모습을 확보하기 위해 더 먼 거리에서 정지하도록 화면 점유율 임계값을 하향 설정하는 것
FALL_DRIVE_STOP_THRESH = 0.60
# 쓰러진 객체가 화면의 75% 이상을 차지할 경우 시야각 한계 방지를 위해 후진 명령을 내리는 임계값을 설정하는 것
FALL_DRIVE_REVERSE_THRESH = 0.75

# 위협 상황별 우선순위를 수치화하여 타겟을 결정할 때 기준으로 사용하는 것
PRIORITY = {"FALLEN": 3, "ABNORMAL": 2, "FIRE": 1, "NORMAL": 0} 

# 양자화(Quantization)되어 연산 속도가 최적화된 화재/사람/무기 탐지용 모델 파일 경로를 설정하는 것
M1_ROI_PATH = "model_full_integer_quant.tflite"
# 양자화되어 연산 속도가 최적화된 포즈(관절) 추정용 모델 파일 경로를 설정하는 것
M2_POSE_PATH = "yolo11n-pose_full_integer_quant.tflite"

# 시스템에서 처리할 카메라 프레임의 해상도(가로, 세로)를 고정하는 것
FRAME_W, FRAME_H = 640, 480     
# 카메라 화면의 정중앙 X 좌표를 계산하여 추적의 기준점으로 사용하는 것
CENTER_X = FRAME_W / 2          
# 카메라 렌즈의 수평 시야각(Horizontal FOV)을 설정하는 것
H_FOV = 40.1                    
# 시야각과 화면 너비를 이용해 픽셀 단위의 초점 거리(Focal Length)를 계산하는 기능
focal_length = CENTER_X / math.tan(math.radians(H_FOV / 2.0)) 

# 추적하던 타겟을 놓쳤을 때 해당 타겟 정보를 메모리에서 지우기 전 대기하는 초 단위 시간을 설정하는 것
TRACKING_TIMEOUT = 10.0         
# 놓친 타겟을 다시 찾을 때 색상 히스토그램 유사도의 최소 일치 기준을 설정하는 것 (Re-ID 용도)
REID_SIMILARITY_THRESH = 0.50   
# 포즈 추정 시 각 관절(키포인트)의 신뢰도가 이 값 이상일 때만 유효한 포인트로 인정하는 것
KP_CONF_THRESH = 0.75            
# 타겟을 놓쳤을 때 즉시 초기화하지 않고 과거 정보를 유지하는 최대 프레임 수를 설정하는 것
MAX_LOST_FRAMES_BUFFER = 30     

# 화재 인식 시 온도 센서 기반으로 가중치를 부여하기 위한 기준 온도 (예: 40도 이상부터 가중치 부여)
FIRE_TEMP_BASE = 40.0
# 기준 온도를 초과할 때 1도당 증가시킬 신뢰도(Confidence) 가중치 비율 (예: 0.02 = 1도당 2% 증가)
FIRE_TEMP_WEIGHT = 0.02
# 온도 가중치가 반영된 최종 화재 신뢰도가 이 값을 넘어야만 진짜 화재로 인정하는 컷오프 임계값
FIRE_FINAL_CONF_THRESH = 0.60

# 모델 내부에서 학습된 클래스 번호와 실제 객체를 매핑하는 것 (0: 불)
CLS_FIRE = 0
# 1: 사람
CLS_PERSON = 1
# 2: 무기
CLS_WEAPON = 2

# 웹 스트리밍을 위한 Flask 애플리케이션 객체를 생성하는 기능
app = Flask(__name__)
# 웹 서버 스레드와 AI 스레드 간에 공유할 최종 출력 프레임 전역 변수를 선언하는 것
global_output_frame = None
# 프레임 데이터를 읽고 쓸 때 스레드 충돌(Race Condition)을 방지하기 위한 락(Lock)을 생성하는 기능
frame_lock = threading.Lock()
# 새로운 프레임이 준비되었음을 웹 서버 스레드에 알리기 위한 이벤트 객체를 생성하는 기능
new_frame_event = threading.Event()

# 11개 커스텀 키포인트 배열에서 각 관절이 위치할 인덱스를 지정하는 것 (머리, 가슴, 골반)
KP_FACE, KP_CHEST, KP_HIP = 0, 1, 2
# (오른발, 왼발)
KP_R_FOOT, KP_L_FOOT = 3, 4
# (오른쪽 어깨, 왼쪽 어깨)
KP_R_SHOULDER, KP_L_SHOULDER = 5, 8
# (오른쪽 팔꿈치, 왼쪽 팔꿈치)
KP_R_ELBOW, KP_L_ELBOW = 6, 9
# (오른쪽 손목, 왼쪽 손목)
KP_R_WRIST, KP_L_WRIST = 7, 10

# 포즈 추정 결과를 화면에 그릴 때 관절들을 선으로 잇기 위한 연결 구조를 정의하는 것
SKELETON_EDGES = [
    (KP_FACE, KP_CHEST), (KP_CHEST, KP_HIP), 
    (KP_CHEST, KP_R_SHOULDER), (KP_CHEST, KP_L_SHOULDER),
    (KP_R_SHOULDER, KP_R_ELBOW), (KP_R_ELBOW, KP_R_WRIST),
    (KP_L_SHOULDER, KP_L_ELBOW), (KP_L_ELBOW, KP_L_WRIST),
    (KP_HIP, KP_R_FOOT), (KP_HIP, KP_L_FOOT)
]

# ===========================================================================
# [알고리즘 함수군] - 휴리스틱 행동 분석 및 특징 추출
# ===========================================================================
def remap_coco_to_custom(raw_kpts):
    # 11개의 관절 데이터(x, y, conf)를 담을 비어있는 넘파이 배열을 생성하는 기능
    custom_kpts = np.zeros((11, 3))
    
    # YOLO의 원본 키포인트 배열에서 특정 인덱스의 좌표와 신뢰도를 안전하게 추출하는 내부 기능
    def get_pt(idx):
        # 인덱스가 원본 배열 크기를 벗어나면 0값 반환하여 에러를 방지하는 기능
        if idx >= len(raw_kpts): return np.array([0.0, 0.0, 0.0])
        # 해당 인덱스의 포인트를 가져오는 것
        pt = raw_kpts[idx]
        # x, y, conf 세 가지 값이 모두 있다면 그대로 넘파이 배열로 묶어서 반환하는 기능
        if len(pt) >= 3: return np.array([pt[0], pt[1], pt[2]])
        # conf 값이 생략된 모델의 경우 좌표가 0보다 크면 임의로 conf를 1.0으로 부여하여 반환하는 기능
        return np.array([pt[0], pt[1], 1.0 if (pt[0] > 0 and pt[1] > 0) else 0.0])

    # 들어온 원본 키포인트가 비어있으면 그대로 0으로 채워진 배열을 반환하는 기능
    if len(raw_kpts) == 0: return custom_kpts

    # YOLO 원본 포인트를 미리 정의한 커스텀 인덱스에 직접 매핑(대입)하는 기능
    custom_kpts[KP_FACE]       = get_pt(0)   # 코(Nose) 데이터를 얼굴로 매핑하는 것
    custom_kpts[KP_L_SHOULDER] = get_pt(5)   # 왼쪽 어깨 데이터를 매핑하는 것
    custom_kpts[KP_R_SHOULDER] = get_pt(6)   # 오른쪽 어깨 데이터를 매핑하는 것
    custom_kpts[KP_L_ELBOW]    = get_pt(7)   # 왼쪽 팔꿈치 데이터를 매핑하는 것
    custom_kpts[KP_R_ELBOW]    = get_pt(8)   # 오른쪽 팔꿈치 데이터를 매핑하는 것
    custom_kpts[KP_L_WRIST]    = get_pt(9)   # 왼쪽 손목 데이터를 매핑하는 것
    custom_kpts[KP_R_WRIST]    = get_pt(10)  # 오른쪽 손목 데이터를 매핑하는 것
    custom_kpts[KP_L_FOOT]     = get_pt(15)  # 왼쪽 발목 데이터를 발로 매핑하는 것
    custom_kpts[KP_R_FOOT]     = get_pt(16)  # 오른쪽 발목 데이터를 발로 매핑하는 것

    # 가슴 위치를 계산하기 위해 양 어깨 좌표를 가져오는 기능
    ls = custom_kpts[KP_L_SHOULDER]
    rs = custom_kpts[KP_R_SHOULDER]
    # 양 어깨가 모두 탐지되었다면(신뢰도가 0보다 크다면) 가슴 중심점 좌표를 계산하여 매핑하는 기능
    if ls[2] > 0 and rs[2] > 0:
        # X, Y는 어깨의 중앙값, 신뢰도는 양쪽 중 더 낮은 값을 채택하는 기능
        custom_kpts[KP_CHEST] = [(ls[0] + rs[0]) / 2.0, (ls[1] + rs[1]) / 2.0, min(ls[2], rs[2])]

    # 골반 위치를 계산하기 위해 YOLO 골반 인덱스(11, 12) 좌표를 가져오는 기능
    lh = get_pt(11)
    rh = get_pt(12)
    # 양쪽 골반이 모두 탐지되었다면 골반 중심점 좌표를 계산하여 매핑하는 기능
    if lh[2] > 0 and rh[2] > 0:
        # X, Y는 골반의 중앙값, 신뢰도는 양쪽 중 더 낮은 값을 채택하는 기능
        custom_kpts[KP_HIP] = [(lh[0] + rh[0]) / 2.0, (lh[1] + rh[1]) / 2.0, min(lh[2], rh[2])]

    # 완성된 11개의 커스텀 키포인트 배열을 반환하는 기능
    return custom_kpts

# 객체의 중심부 색상 정보를 추출하여 동일 객체 추적(Re-ID)에 활용하기 위한 컬러 히스토그램 생성 기능
def get_color_hist(frame, bx, by, bw, bh):
    # X축(가로)은 15~85%(중심 70%), Y축(세로)은 25~75%(중심 50%) 영역을 사용하여 데이터 모수를 최적화하는 기능
    core_w, core_h = bw * 0.7, bh * 0.5
    
    # 영역의 좌상단(x1, y1) 및 우하단(x2, y2) 좌표를 계산하며, 화면 밖을 벗어나지 않도록 클리핑하는 기능
    x1, y1 = max(0, int(bx - core_w/2)), max(0, int(by - core_h/2))
    x2, y2 = min(FRAME_W, int(bx + core_w/2)), min(FRAME_H, int(by + core_h/2))
    
    # 계산된 좌표로 프레임 이미지를 잘라내는(Crop) 기능
    crop = frame[y1:y2, x1:x2]
    # 잘려진 이미지가 없다면 처리를 중단하고 None을 반환하는 기능
    if crop.size == 0: return None
    
    # BGR 색상 공간을 조명 변화에 강한 HSV 색상 공간으로 변환하는 기능
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # 색상(H)과 채도(S) 채널을 기반으로 2D 히스토그램을 계산하는 기능 (밝기 V는 역광 방지를 위해 배제), 마지막은 범위지정
    hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    # 추출된 히스토그램 수치를 0~1 사이의 값으로 정규화하여 크기에 관계없이 비교 가능하게 만드는 기능
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    
    return hist

# 변환된 키포인트와 박스 정보를 바탕으로 대상의 행동(쓰러짐, 주먹질 등)을 추론하는 기능
def analyze_behavior(kpts, bw, bh, weapon_centers):
    # 특정 인덱스의 관절이 임계값 이상의 신뢰도로 탐지되었는지 확인하는 내부 검증 기능
    def is_valid(idx): 
        # 인덱스가 유효 범위 내에 있고, conf 값이 기준치 이상이면 참(True)을 반환하는 것
        return kpts[idx][2] > KP_CONF_THRESH if idx < len(kpts) else False

    # 객체의 세로 대비 가로 비율을 계산하여 형태학적 특성을 파악하는 기능
    aspect_ratio = bw / bh if bh > 0 else 0

    # 객체가 가로로 넓게 퍼져있고(비율 > 0.5), 가슴과 골반이 모두 탐지되었을 경우 쓰러짐 여부를 판별하는 기능
    if aspect_ratio > 0.5 and is_valid(KP_CHEST) and is_valid(KP_HIP):
        # 전체 화면 높이 대비 가슴 위치의 비율(Y축)을 계산하는 기능
        chest_y_frame = kpts[KP_CHEST][1] / FRAME_H 
        # 가슴과 골반 사이의 X축 거리 차이(수평 거리)를 계산하는 기능
        t_x = abs(kpts[KP_CHEST][0] - kpts[KP_HIP][0])
        # 가슴과 골반 사이의 Y축 거리 차이(수직 거리)를 계산하는 기능
        t_y = abs(kpts[KP_CHEST][1] - kpts[KP_HIP][1])

        # 가슴-골반 수평 거리가 수직 거리보다 특정 비율 이상 길다면 '측면 쓰러짐'으로 판별하는 기능
        if t_x > (t_y * FALL_LATERAL_RATIO): return "FALLEN"
        # 양 어깨가 모두 탐지되었다면 앞뒤로 쓰러진 경우를 추가로 판별하는 기능
        if is_valid(KP_R_SHOULDER) and is_valid(KP_L_SHOULDER):
            # 양 어깨 사이의 거리를 계산하는 기능
            shoulder_w = abs(kpts[KP_R_SHOULDER][0] - kpts[KP_L_SHOULDER][0])
            # 어깨 너비보다 수직 길이가 극단적으로 짧고, 가슴 위치가 화면 아래쪽에 치우쳐 있다면 '정면 쓰러짐'으로 판별하는 기능
            if shoulder_w > 0 and t_y < (shoulder_w * FALL_AXIAL_RATIO) and chest_y_frame > FALL_CHEST_LOW_THRESH:
                return "FALLEN"

    # 무기 소지 여부를 기록하기 위한 초기값을 거짓(False)으로 설정하는 것
    weapon_held = False
    # 양쪽 손목 좌표를 순회하며 무기 좌표와의 근접성을 확인하는 반복문 기능
    for w_idx in [KP_R_WRIST, KP_L_WRIST]:
        # 해당 손목이 화면상에 잘 탐지되었는지 확인하는 기능
        if is_valid(w_idx):
            # 손목의 X, Y 좌표를 추출하는 것
            wx, wy = kpts[w_idx][0], kpts[w_idx][1]
            # 탐지된 모든 무기의 중심점 좌표를 순회하며 비교하는 기능
            for wbx, wby in weapon_centers:
                # 손목과 무기 중심 사이의 거리 제곱이 임계값보다 작고, 손목이 골반보다 위에 위치해 있다면(무기를 들고 있다면)
                if (wx - wbx)**2 + (wy - wby)**2 < WEAPON_DIST_SQ_THRESH and wy < kpts[KP_HIP][1]:
                    # 무기를 소지한 것으로 상태를 변경하고 즉시 반복문을 종료하는 기능
                    weapon_held = True; break

    # 주먹질(펀치) 동작 여부를 기록하기 위한 초기값을 거짓(False)으로 설정하는 것
    punch_detected = False
    # 가슴 좌표가 탐지되었고 박스 너비가 유효한 경우 펀치 동작을 판별하는 기능
    if is_valid(KP_CHEST) and bw > 0:
        # 양쪽 손목을 순회하는 반복문 기능
        for w_idx in [KP_R_WRIST, KP_L_WRIST]:
            # 손목이 잘 탐지되었는지 확인하는 기능
            if is_valid(w_idx):
                # 손목이 가슴으로부터 박스 너비 대비 특정 비율 이상 멀리 뻗어졌고, 손목이 가슴보다 위에 있다면 펀치로 판별하는 기능
                if abs(kpts[w_idx][0] - kpts[KP_CHEST][0]) > (bw * PUNCH_REACH_RATIO) and kpts[w_idx][1] < kpts[KP_CHEST][1]:
                    # 펀치 동작으로 상태를 변경하고 즉시 반복문을 종료하는 기능
                    punch_detected = True; break

    # 발차기 동작 여부를 기록하기 위한 초기값을 거짓(False)으로 설정하는 것
    kick_detected = False
    # 골반 좌표가 탐지되었고 박스 높이가 유효한 경우 발차기 동작을 판별하는 기능
    if is_valid(KP_HIP) and bh > 0:
        # 양쪽 발목을 순회하는 반복문 기능
        for f_idx in [KP_R_FOOT, KP_L_FOOT]:
            # 발목이 잘 탐지되었는지 확인하는 기능
            if is_valid(f_idx):
                # 발목의 위치가 골반과 거의 비슷하거나 더 위로 올라갔다면(허리 높이까지 발이 올라왔다면) 발차기로 판별하는 기능
                if kpts[f_idx][1] < kpts[KP_HIP][1] - (bh * 0.05):
                    # 발차기 동작으로 상태를 변경하고 즉시 반복문을 종료하는 기능
                    kick_detected = True; break

    # 앞서 판별한 무기 소지, 주먹질, 발차기 중 하나라도 참이라면 '이상 행동(ABNORMAL)'을 반환하는 기능
    if weapon_held or punch_detected or kick_detected: return "ABNORMAL"
    # 모든 조건을 통과했다면 '정상(NORMAL)' 상태를 반환하는 기능
    return "NORMAL"

# ===========================================================================
# [하드웨어 모듈] I/O 비동기 분리
# ===========================================================================
# 카메라 영상 입력 시 발생하는 프레임 병목 현상을 방지하기 위해 별도의 스레드에서 영상을 읽어오는 클래스 기능
class CameraStream:
    # 클래스 생성 시 카메라를 초기화하고 스레드를 시작하는 기능
    def __init__(self, src=0):
        # 지정된 디바이스(기본 0번 카메라)를 V4L2 백엔드를 이용해 캡처 객체로 여는 기능
        self.cap = cv2.VideoCapture(src, cv2.CAP_V4L2)

        # 캡처될 프레임의 가로 해상도를 설정하는 기능
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        # 캡처될 프레임의 세로 해상도를 설정하는 기능
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        # 영상 지연(Latency)을 최소화하기 위해 버퍼 사이즈를 1로 고정하는 기능
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # 스레드 종료 여부를 제어하기 위한 플래그 변수를 초기화하는 것
        self.stopped = False
        # 카메라로부터 초기 첫 프레임을 읽어오는 기능
        self.ret, self.frame = self.cap.read()
        # 프레임 변수를 읽고 쓸 때 데이터가 꼬이지 않도록 락을 설정하는 기능
        self.lock = threading.Lock()
        # 데몬 스레드를 생성하여 메인 프로그램이 종료될 때 같이 종료되도록 하고, update 함수를 백그라운드에서 실행하는 기능
        threading.Thread(target=self.update, daemon=True).start()

    # 무한 루프를 돌며 최신 프레임을 지속적으로 메모리에 갱신하는 스레드 내부 구동 기능
    def update(self):
        # 중지 명령이 내려지기 전까지 반복하는 기능
        while not self.stopped:
            # 카메라로부터 최신 프레임을 읽어오는 기능
            ret, frame = self.cap.read()
            # 프레임이 정상적으로 읽혔다면
            if ret:
                # 락을 걸어 다른 곳에서 접근하지 못하게 한 뒤, 최신 프레임으로 덮어씌우는 기능
                with self.lock: self.frame = frame
            # CPU 점유율이 100%로 치솟는 것을 막기 위해 미세한 지연(0.005초)을 주는 기능
            time.sleep(0.005) 
            
    # 외부 모듈에서 현재 최신 프레임 복사본을 안전하게 가져갈 수 있도록 지원하는 인터페이스 기능
    def read(self):
        # 원본 프레임이 손상되지 않도록 락을 걸고 프레임의 복사본(copy)을 반환하는 기능
        with self.lock: return self.frame.copy() if self.frame is not None else None
        
    # 스트리밍 루프를 종료하고 카메라 장치 자원을 운영체제에 반환하는(해제하는) 기능
    def stop(self):
        self.stopped = True; self.cap.release()

# 모터 제어 및 센서 조회를 위한 아두이노 등과의 직렬(Serial) 통신을 백그라운드 스레드로 분리하여 병목을 막는 클래스 기능
class SerialCommunicator:
    # 클래스 생성 시 통신 포트와 속도를 지정하고 스레드를 시작하는 기능
    def __init__(self, port='/dev/ttyAMA0', baudrate=115200):
        # 현재 로봇의 방향(Yaw 각도)과 온도 센서 값을 저장할 변수를 0.0으로 초기화하는 기능
        self.current_yaw, self.current_temp = 0.0, 0.0
        # 스레드 동작을 제어하기 위한 중지 플래그 변수 설정하는 것
        self.stopped = False
        # 특정 시점에만 온도나 각도를 요청할 수 있도록 트리거(이벤트) 객체를 준비하는 기능
        self.temp_trigger_event, self.yaw_trigger_event = threading.Event(), threading.Event()
        # 통신 데이터 경합을 방지하기 위한 락을 설정하는 기능
        self.lock = threading.Lock()
        # AI 모델이 계산하여 보내줄 목표 요(Yaw) 각도와 모터 정지 신호 상태 변수를 초기화하는 기능
        self.target_yaw, self.stop_signal = 0.0, 0
        
        # 지정된 포트로 시리얼 연결을 시도하는 기능
        try:
            # 연결 시 타임아웃을 0.05초로 주어 응답이 없을 때 프로그램이 멈추지 않게 방지하는 기능
            self.ser = serial.Serial(port, baudrate, timeout=0.05)
        # 하드웨어 포트가 없거나 오류가 발생하면 ser 객체를 None으로 처리하여 예외를 방지하는 기능
        except: self.ser = None
        # 통신 제어를 백그라운드에서 전담할 데몬 스레드를 실행하는 기능
        threading.Thread(target=self.run, daemon=True).start()

    # 백그라운드 통신 루프를 구동하는 메인 스레드 동작 기능
    def run(self):
        # 시리얼 포트 연결에 실패했다면 통신 루프를 실행하지 않고 종료하는 기능
        if not self.ser: return
        # 일정 주기 단위로 명령을 보내기 위해 마지막 송신 시간을 기록하는 기능
        last_poll_time = time.time()
        # 정지 플래그가 참이 되기 전까지 무한 반복하는 통신 루프 기능
        while not self.stopped:
            # 온도를 읽어오라는 이벤트 트리거가 활성화되었는지 확인하는 기능
            if self.temp_trigger_event.is_set():
                # 하드웨어에 온도 요청 프로토콜(0xAA, 0x0A, 0x55)을 바이트 형태로 전송하는 기능
                self.ser.write(bytes([0xAA, 0x0A, 0x55]))
                # 온도 요청 이벤트를 초기화(해제)하고 수신 대기 함수를 호출하는 기능
                self.temp_trigger_event.clear(); self.receive_response('T')
            # 로봇 방향(Yaw)을 읽어오라는 이벤트 트리거가 활성화되었는지 확인하는 기능
            if self.yaw_trigger_event.is_set():
                # 하드웨어에 방향 요청 프로토콜(0xAA, 0x0B, 0x55)을 바이트 형태로 전송하는 기능
                self.ser.write(bytes([0xAA, 0x0B, 0x55]))
                # 방향 요청 이벤트를 초기화하고 수신 대기 함수를 호출하는 기능
                self.yaw_trigger_event.clear(); self.receive_response('Y')
                
            # 마지막 데이터 송신 이후 0.05초(50ms) 이상 경과했는지 확인하는 기능
            if time.time() - last_poll_time >= 0.05:
                # 락을 걸고 목표 각도와 정지 신호를 텍스트 프로토콜 규격(t각도,신호\n)에 맞춰 문자열로 생성하는 기능
                with self.lock: payload = f"t{self.target_yaw:.2f},{self.stop_signal}\n"
                # 생성된 문자열 명령어를 UTF-8 바이트로 인코딩하여 하드웨어로 전송하는 기능
                self.ser.write(payload.encode('utf-8'))
                # 송신 시간을 현재 시간으로 갱신하는 기능
                last_poll_time = time.time()
            # CPU 점유율 최적화를 위한 대기(Sleep) 기능
            time.sleep(0.01)

    # 하드웨어에서 센서 값 등 응답 패킷이 돌아올 때 파싱하는 수신 전담 기능
    def receive_response(self, data_type):
        # 포트 연결이 안 되어있으면 무시하는 기능
        if not self.ser: return
        # 포트에서 4바이트(Float 크기)만큼 데이터를 읽어오는 기능
        packet = self.ser.read(4)
        # 데이터가 4바이트 미만으로 들어와 패킷이 깨진 경우 무시하고 종료하는 기능
        if len(packet) < 4: return
        try:
            # 4바이트 바이너리 패킷을 C언어 구조체 리틀엔디안 Float 형태로 파싱하여 실수(float) 값으로 변환하는 기능
            val = struct.unpack('<f', packet)[0]
            # 데이터를 갱신할 때 변수 보호를 위해 락을 거는 기능
            with self.lock:
                # 데이터 타입이 온도(T)라면 온도 변수에 값을 갱신하는 기능
                if data_type == 'T': self.current_temp = val
                # 데이터 타입이 각도(Y)라면 각도 변수에 값을 갱신하는 기능
                elif data_type == 'Y': self.current_yaw = val
        # 바이너리 파싱 중 에러가 발생하면 다운되지 않고 그냥 넘어가는 예외 처리 기능
        except: pass

    # 외부에서 통신 클래스로 온도를 읽어오도록 지시하기 위해 이벤트를 세팅하는 기능
    def request_temp(self): self.temp_trigger_event.set()
    # 외부에서 통신 클래스로 현재 로봇 각도를 읽어오도록 지시하기 위해 이벤트를 세팅하는 기능
    def request_yaw(self): self.yaw_trigger_event.set()
    
    # 캐시된(최근 업데이트된) 온도 변수 값을 안전하게 읽어가는 외부 공개 기능
    def get_temp(self):
        with self.lock: return self.current_temp
    # 캐시된(최근 업데이트된) 로봇 방향(Yaw) 변수 값을 안전하게 읽어가는 외부 공개 기능
    def get_yaw(self):
        with self.lock: return self.current_yaw
        
    # AI 엔진에서 계산된 타겟 각도 및 주행 상태 명령을 시리얼 전송용 변수에 입력하는 기능
    def set_target_data(self, yaw_val, stop_val):
        with self.lock: self.target_yaw, self.stop_signal = yaw_val, stop_val
        
    # 무한 루프를 멈추고 열려있는 시리얼 포트를 완전히 닫아 운영체제에 반환하는 기능
    def stop(self):
        self.stopped = True
        if self.ser: self.ser.close()

# ===========================================================================
# [모듈] 메인 AI 추론 엔진 
# ===========================================================================
# 영상 스트림과 시리얼 통신 모듈을 결합하여 딥러닝 추론 및 전체 시스템 흐름을 총괄하는 중앙 통제 클래스 기능
class InferenceEngine:
    def __init__(self, camera, serial_comm):
        self.camera = camera
        self.serial = serial_comm
        self.roi_model = YOLO(M1_ROI_PATH, task='detect')
        self.pose_model = YOLO(M2_POSE_PATH, task='pose')
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
                results = self.roi_model.track(frame, tracker="bytetrack.yaml", persist=True, verbose=False, classes=[CLS_FIRE, CLS_PERSON, CLS_WEAPON], imgsz=320, conf=0.10)
                
                weapon_centers = []
                candidates = []
                current_time = time.time()

                if results and results[0].boxes:
                    for i, box_obj in enumerate(results[0].boxes):
                        cls = int(box_obj.cls[0])
                        conf = float(box_obj.conf[0].cpu().numpy())
                        box_xywh = box_obj.xywh[0].cpu().numpy()
                        bx, by, bw, bh = box_xywh
                        x1, y1, x2, y2 = map(int, box_obj.xyxy[0].cpu().numpy())
                        
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
                        
                        if cls == CLS_PERSON:
                            roi_x1, roi_y1 = max(0, x1), max(0, y1)
                            roi_x2, roi_y2 = min(FRAME_W, x2), min(FRAME_H, y2)
                            roi_img = frame[roi_y1:roi_y2, roi_x1:roi_x2]
                            
                            if roi_img.size > 0:
                                pose_results = self.pose_model.predict(roi_img, imgsz=160, conf=0.10, verbose=False)
                                if len(pose_results) > 0 and pose_results[0].keypoints is not None:
                                    if hasattr(pose_results[0].keypoints, 'data') and len(pose_results[0].keypoints.data) > 0:
                                        raw_kpts = pose_results[0].keypoints.data[0].cpu().numpy()
                                    elif hasattr(pose_results[0].keypoints, 'xy') and len(pose_results[0].keypoints.xy) > 0:
                                        raw_kpts = pose_results[0].keypoints.xy[0].cpu().numpy()
                                    else: raw_kpts = []
                                        
                                    if len(raw_kpts) > 0:
                                        for k in range(len(raw_kpts)):
                                            if len(raw_kpts[k]) > 2 and raw_kpts[k][2] > 0:  
                                                raw_kpts[k][0] += roi_x1
                                                raw_kpts[k][1] += roi_y1
                                            elif len(raw_kpts[k]) == 2 and raw_kpts[k][0] > 0:
                                                raw_kpts[k][0] += roi_x1
                                                raw_kpts[k][1] += roi_y1
                                        
                                        mapped_kpts = remap_coco_to_custom(raw_kpts)
                                        current_status = analyze_behavior(mapped_kpts, bw, bh, weapon_centers)
                                        valid_kpts = mapped_kpts

                        candidates.append({
                            "id": track_id, "type": current_status, "prio": PRIORITY[current_status],
                            "box": box_xywh, "center": (bx, by), "height_ratio": bh/FRAME_H,
                            "status": current_status, "hist": get_color_hist(frame, bx, by, bw, bh),
                            "conf": conf, "kpts": valid_kpts
                        })

                # [타겟 필터링 및 추적 타겟 결정 제어 흐름 수행]
                best_target = None
                if self.locked_id is not None:
                    matched = [c for c in candidates if c["id"] == self.locked_id]
                    if not matched and candidates:
                        highest_sim = 0
                        reid_candidate = None
                        for c in candidates:
                            if c["id"] != -1 and c["hist"] is not None and self.locked_hist is not None:
                                sim = cv2.compareHist(self.locked_hist, c["hist"], cv2.HISTCMP_CORREL)
                                if sim > highest_sim: highest_sim = sim; reid_candidate = c
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
                    valid_candidates = [c for c in candidates if c["prio"] > 0 and c["id"] != -1]
                    if not valid_candidates: valid_candidates = [c for c in candidates if c["id"] != -1]
                    if valid_candidates:
                        best_target = max(valid_candidates, key=lambda c: c["prio"])
                        self.locked_id = best_target["id"]
                        self.locked_type = best_target["type"]
                        self.locked_hist = best_target["hist"]
                        self.last_seen_time = current_time
                        self.lost_frame_count = 0
                        self.last_known_target = best_target

                # -------------------------------------------------------------------
                # [개선된 시각화 섹션] 모든 객체의 상시 출력과 타겟 지정선 분리
                # -------------------------------------------------------------------
                for c in candidates:
                    cbx, cby, cbw, cbh = c["box"]
                    c_status = c["status"]
                    c_kpts = c["kpts"]
                    
                    # 1단계: 기본 박스 및 포즈 상시 시각화 (모든 후보 대상)
                    if c_status == "NORMAL": box_color = (0, 255, 255)      # 노란색
                    elif c_status == "ABNORMAL": box_color = (0, 0, 255)    # 빨간색
                    elif c_status == "FALLEN": box_color = (255, 0, 0)      # 파란색
                    elif c_status == "FIRE": box_color = (0, 165, 255)      # 주황색                       
                    
                    # 현재 타겟으로 고정(Locked)된 객체는 초록색 볼드 형태로 타겟 박스 구별 처리
                    is_locked = (self.locked_id is not None and self.locked_id == c["id"])
                    if is_locked:
                        box_color = (0, 255, 0)  # 타겟은 초록색 박스로 표시
                        thickness = 4
                    else:
                        thickness = 2

                    cv2.rectangle(frame, (int(cbx-cbw/2), int(cby-cbh/2)), (int(cbx+cbw/2), int(cby+cbh/2)), box_color, thickness)
                    text_str = f"ID:{c['id']} [LOCKED]" if is_locked else f"ID:{c['id']} [{c_status}]"
                    cv2.putText(frame, text_str, (int(cbx-cbw/2), int(cby-cbh/2)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
                    
                    # 관절(Skeleton) 상시 출력
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

                # 2단계: 최우선 확정 타겟이 있을 때 '타겟 중심선' 및 '오차 각도' 추가 투사
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

                    # 카메라 중심(화면 중앙 바닥)에서 타겟 중심(core_x, core_y)으로 이어지는 오차 측정 녹색 추적선 작도
                    cv2.line(frame, (int(CENTER_X), FRAME_H), (int(core_x), int(core_y)), (0, 255, 0), 2)
                    # 추적선 중앙에 상대 오차 각도(vis_error)와 연동된 로봇의 절대 목표 각도(target_yaw) 명시
                    cv2.putText(frame, f"Err: {vis_error:.1f}deg | Target Yaw: {target_yaw:.1f}deg", 
                                (int((CENTER_X + core_x)/2) - 80, int((FRAME_H + core_y)/2)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
                    
                    state_msg = f"HOLD({self.lost_frame_count})" if self.lost_frame_count > 0 else f"LOCKED ID:{self.locked_id}"
                    cv2.putText(frame, f"{state_msg} [{self.locked_type}]", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    print(f"[INFO] FPS: {fps:.1f} | Curr Yaw: {curr_yaw:.1f} | Target Yaw: {target_yaw:.1f} | ID: {self.locked_id} | State: {self.locked_type}")
                else:
                    self.last_valid_state = 4
                    self.serial.set_target_data(self.last_valid_yaw, self.last_valid_state)
                    state_text = f"SEARCHING (Timeout: {TRACKING_TIMEOUT - (current_time - self.last_seen_time):.1f}s)" if self.locked_id else "NORMAL"
                    cv2.putText(frame, state_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    print(f"[INFO] FPS: {fps:.1f} | Curr Yaw: {curr_yaw:.1f} | SEARCHING...")

                with frame_lock: 
                    global_output_frame = frame.copy()
                new_frame_event.set()
            except Exception as e: pass
            time.sleep(0.005)

    def stop(self): self.stopped = True

# ===========================================================================
# [웹 모듈] Flask 비동기 스트리밍 (해상도 및 압축비 최적화)
# ===========================================================================
def generate_frames():
    global global_output_frame
    while True:
        new_frame_event.wait()
        new_frame_event.clear()
        with frame_lock:
            if global_output_frame is None: continue
            # 기존 320x240 강제 리사이즈로 인한 자막 깨짐을 해결하기 위해 원본 비율을 보존한 640x480 해상도로 웹 스트리밍 송출 유도
            frame_resized = cv2.resize(global_output_frame, (FRAME_W, FRAME_H)) 
        
        # 가독성을 위해 압축 화질 수준을 기존 70%에서 85%로 상향 조정
        ret, buffer = cv2.imencode(".jpg", frame_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if ret: 
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

# Flask 웹 서버의 기본 루트 경로('/')에 접속했을 때 동작하는 라우터 설정 기능
@app.route("/")
def index():
    # 사용자가 접속 시 영상 화면을 띄워줄 기본적인 HTML 코드를 렌더링해서 문자열로 반환하는 기능
    return render_template_string('<html><body style="text-align:center;background:#222;color:white;"><h1>AI 관제</h1><img src="/video_feed" width="640" height="480"/></body></html>')

# 브라우저의 img 태그 src에서 영상을 호출할 때 실제로 JPEG 프레임을 연속 전송하는 엔드포인트 라우터 설정 기능
@app.route("/video_feed")
def video_feed():
    # 위에서 정의한 generate_frames 제너레이터를 호출하여 multipart 혼합 스트림 방식으로 웹 브라우저에 연속 전송(Response)하는 기능
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

# 이 파이썬 파일이 모듈로 쓰이지 않고 직접 실행되었을 때만 작동하는 메인 진입점(엔트리 포인트) 판별 기능
if __name__ == "__main__":
    # 카메라 스트림 클래스 인스턴스를 생성해 영상을 별도 스레드로 백그라운드 캡처 시작하는 것
    cam = CameraStream(src=0)
    # 아두이노 모터 및 센서 통신용 클래스 인스턴스를 생성해 시리얼 통신을 백그라운드 시작하는 것
    serial_comm = SerialCommunicator(port='/dev/ttyAMA0', baudrate=115200)
    # 카메라와 통신 객체를 메인 AI 엔진에 주입하여 추론 무한 루프를 가동하는 것
    ai_engine = InferenceEngine(cam, serial_comm)
    try: 
        # 모든 센서와 AI가 준비되었으니 Flask 웹 서버를 모든 외부 IP(0.0.0.0)에 개방하여 5000 포트에서 실행하는 기능 (안정성을 위해 디버그와 릴로더 끔)
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False)
    # 콘솔에서 Ctrl+C를 누르거나 프로그램 종료 명령이 내려왔을 때 자원을 깔끔하게 해제하는 예외 마무리 구문 기능
    finally:
        # 카메라 자원을 반납하는 것
        cam.stop(); 
        # AI 스레드 루프를 정지시키는 것
        ai_engine.stop(); 
        # 열려있는 시리얼 포트를 강제로 닫는 것
        serial_comm.stop()