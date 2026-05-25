# AI 기반 로봇 관제 및 추적 시스템 (AI-based Robot Monitoring & Tracking System)

이 프로젝트는 딥러닝 기반의 비전 기술을 활용하여 객체를 탐지하고 자세를 추정하며, 이를 통해 로봇의 자율적인 관제 및 추적을 수행하는 시스템입니다. 감지된 객체의 행동(예: 낙상, 이상 행동)에 따라 로봇이 적절하게 반응하고, 웹 또는 로컬 GUI를 통해 실시간으로 상황을 모니터링할 수 있도록 설계되었습니다.

## 핵심 기능 (Core Features)

### 1. AI 기반 객체 탐지 및 자세 추정 (AI-based Object Detection & Pose Estimation)
*   **객체 탐지**: 사람, 화재, 무기 등 지정된 클래스를 실시간으로 탐지합니다.
*   **자세 추정**: 탐지된 사람 객체의 랜드마크(키포인트)를 추출하여 신체 자세를 분석합니다.
*   **이상 행동 감지**: 자세 추정 결과를 기반으로 다음 행동을 판별합니다.
    *   **낙상 (FALLEN)**: 사람이 쓰러져 있는 자세를 감지합니다.
    *   **이상 행동 (ABNORMAL)**: 무기 소지, 주먹질, 발차기 등의 위협적인 행동을 감지합니다.
*   **온도 연동 화재 신뢰도**: 시리얼 통신으로 수신된 온도 센서 데이터를 활용하여 화재 탐지 신뢰도를 보정합니다.

### 2. 다중 객체 추적 및 재식별 (Multi-Object Tracking & Re-Identification)
*   **ByteTrack 기반 추적**: `bytetrack.yaml` 트래커를 사용하여 프레임 간 객체의 고유 ID를 유지하고 부드러운 추적을 가능하게 합니다.
*   **색상 히스토그램 재식별**: 추적을 놓친 객체를 다시 찾을 때, 이전에 기록된 색상 히스토그램 유사도를 기반으로 동일한 객체인지 판단하고 추적을 복원합니다.
*   **위험 객체 고정 추적 (Locked Target)**: 'FALLEN' 또는 'ABNORMAL'과 같은 위험 상태의 객체가 탐지되면, 해당 객체를 최우선 타겟으로 고정하여 추적을 유지합니다. 객체의 일시적인 행동 변화에도 원래의 위험 상태를 보전합니다.

### 3. 하드웨어 연동 (Hardware Interfacing)
*   **카메라 스트림 (CameraStream)**: 별도의 스레드에서 카메라 영상을 비동기적으로 읽어와 메인 AI 추론 파이프라인의 병목 현상을 방지합니다. 프레임 해상도 및 버퍼 사이즈를 최적화하여 저지연 영상 처리를 지원합니다.
*   **시리얼 통신 (SerialCommunicator)**: 백그라운드 스레드에서 외부 마이크로컨트롤러(예: STM32)와 UART 통신을 수행합니다.
    *   **명령 송신**: AI 엔진에서 계산된 목표 Yaw 각도 및 로봇 주행 상태(정지, 전진, 후진, 탐색)를 전송합니다.
    *   **센서 데이터 수신**: 로봇의 현재 Yaw 각도 및 온도 센서 값(화재 감지에 활용)을 수신합니다.

### 4. 지능형 로봇 제어 로직 (Intelligent Robot Control Logic)
*   **타겟 중심 기반 Yaw 오차 계산**: 카메라 시야 내 타겟의 위치와 카메라 중심을 비교하여 로봇이 타겟을 향해 회전해야 할 각도(Yaw 오차)를 계산합니다.
*   **거리 기반 주행 상태 결정**: 타겟의 화면 점유율(바운딩 박스 높이 비율)을 분석하여 로봇의 주행 상태(전진, 정지, 후진)를 동적으로 결정합니다. 'FALLEN' 상태의 타겟에게는 다른 임계값을 적용하여 더 안전한 거리를 유지합니다.
*   **탐색 모드**: 추적 중인 타겟을 놓치거나, 초기화된 상태에서는 탐색 모드로 전환하여 주변을 스캔합니다.

### 5. 실시간 모니터링 (Real-time Monitoring)
*   **웹 기반 스트리밍 (Flask)**: `tracking_robot_custom.py` 및 `tracking_robot_yolo26n.py`는 Flask 웹 서버를 통해 처리된 영상 프레임을 실시간으로 웹 브라우저에 스트리밍합니다.
*   **로컬 GUI 모니터링 (OpenCV `imshow`)**: `tracking_robot_11point.py`는 OpenCV의 `imshow` 함수를 사용하여 처리된 영상을 로컬 화면에 직접 표시합니다.

## 사용 방법 (How to Use)

### 1. 사전 준비 (Prerequisites)

*   **Python 환경**: Python 3.x가 설치되어 있어야 합니다.
*   **패키지 설치**: 다음 Python 라이브러리를 설치합니다.
    ```bash
    pip install ultralytics opencv-python numpy pyserial flask tensorflow-lite
    ```
    (참고: `tensorflow-lite`는 TFLite 모델을 사용하는 경우에 필요하며, 모델 변환 방식에 따라 `tflite-runtime`을 설치해야 할 수도 있습니다.)
*   **모델 파일**:
    *   `bytetrack.yaml`: `ultralytics` 라이브러리에 포함된 기본 트래커 설정 파일을 사용하거나 프로젝트 루트에 준비합니다.
    *   AI 모델 파일:
        *   `tracking_robot_custom.py`는 `model_full_integer_quant.tflite` (객체 탐지) 및 `yolo11n-pose_full_integer_quant.tflite` (자세 추정)을 사용합니다.
        *   `tracking_robot_yolo26n.py`는 `yolo26n-pose.pt` (객체 탐지 및 자세 추정)을 사용합니다.
        *   `tracking_robot_11point.py`는 `best_float16.tflite` (커스텀 11포인트 자세 추정)을 사용합니다.
    해당 모델 파일들은 스크립트와 같은 디렉토리에 두거나, 스크립트 내 `MODEL_PATH` 변수를 수정하여 경로를 지정해야 합니다.

*   **하드웨어 설정**:
    *   **카메라**: `/dev/video0`과 같은 장치 경로를 가진 USB 카메라가 연결되어 있어야 합니다. (필요시 스크립트 내 `CameraStream` 초기화 시 `src` 인자 변경)
    *   **시리얼 통신**: 로봇 제어 보드와의 시리얼 통신을 위한 UART 포트(예: `/dev/ttyAMA0`)가 설정되어 있어야 합니다. (필요시 스크립트 내 `SerialCommunicator` 초기화 시 `port` 및 `baudrate` 인자 변경)

### 2. 스크립트 실행 (Running the Scripts)

프로젝트 루트 디렉토리에서 다음 명령어를 사용하여 각 스크립트를 실행할 수 있습니다.

*   **웹 관제 시스템 실행 (Flask 기반)**:
    ```bash
    python ai_vision/tracking_robot_custom.py
    # 또는
    python ai_vision/tracking_robot_yolo26n.py
    ```
    스크립트 실행 후, 웹 브라우저에서 `http://<로봇_IP_주소>:5000` 에 접속하여 실시간 영상을 확인할 수 있습니다.

*   **로컬 GUI 관제 시스템 실행 (OpenCV imshow 기반)**:
    ```bash
    python ai_vision/tracking_robot_11point.py
    ```
    스크립트 실행 후, 로컬 화면에 OpenCV 창이 나타나 실시간 영상을 표시합니다. 창을 닫으려면 `q` 키를 누르십시오.

## 파일별 특징 (File-specific Notes)

*   `ai_vision/tracking_robot_custom.py`:
    *   객체 탐지 및 자세 추정 모델로 TensorFlow Lite 양자화 모델을 사용합니다. `model_full_integer_quant.tflite`는 ROI 탐지를, `yolo11n-pose_full_integer_quant.tflite`는 해당 ROI 내에서 자세를 추정하는 데 사용됩니다.
    *   Flask를 이용한 웹 스트리밍 기능을 제공합니다.

*   `ai_vision/tracking_robot_yolo26n.py`:
    *   YOLOv8 기반의 `yolo26n-pose.pt` 모델을 사용하여 객체 탐지와 자세 추정을 동시에 처리합니다.
    *   Flask를 이용한 웹 스트리밍 기능을 제공합니다.

*   `ai_vision/tracking_robot_11point.py`:
    *   커스텀 훈련된 11포인트 자세 추정 TFLite 모델 (`best_float16.tflite`)을 사용합니다.
    *   로컬 환경에서 OpenCV `imshow`를 통해 실시간 GUI 모니터링을 제공하며, 웹 스트리밍 기능은 포함되어 있지 않습니다.
