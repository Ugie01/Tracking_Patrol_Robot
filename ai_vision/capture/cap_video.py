import cv2
import time
import threading
import sys
import os
from flask import Flask, Response

# ===========================================================================
# [기본 설정]
# ===========================================================================
TARGET_FPS = 15.0
WIDTH, HEIGHT = 640, 480
BASE_NAME = 'dataset'

def get_next_filename(base_name, extension='mp4'):
    i = 1
    while os.path.exists(f"{base_name}_{i}.{extension}"):
        i += 1
    return f"{base_name}_{i}.{extension}"

app = Flask(__name__)
global_frame = None
lock = threading.Lock()
exit_event = threading.Event()

# 전역 상태 변수
is_recording = False
out = None
current_filename = ""

# ===========================================================================
# [백엔드 제어 라우트 (API)] 웹 버튼에서 호출되는 함수
# ===========================================================================
@app.route('/start')
def start_record():
    global is_recording, out, current_filename
    with lock: # 동시 접근 방지
        if not is_recording:
            current_filename = get_next_filename(BASE_NAME)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(current_filename, fourcc, TARGET_FPS, (WIDTH, HEIGHT))
            is_recording = True
            print(f"🔴 [웹 제어] 녹화 시작: {current_filename}")
            return f"녹화 중... ({current_filename})"
        return "이미 녹화가 진행 중입니다."

@app.route('/stop')
def stop_record():
    global is_recording, out
    with lock:
        if is_recording:
            is_recording = False
            if out is not None:
                out.release()
                out = None
            print(f"⏹️ [웹 제어] 녹화 중지 완료")
            return "녹화가 중지되었습니다. (저장 완료)"
        return "현재 녹화 중이 아닙니다."

# ===========================================================================
# [카메라 처리 로직]
# ===========================================================================
def record_loop():
    global global_frame, is_recording, out
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    delay = 1.0 / TARGET_FPS

    try:
        while not exit_event.is_set():
            t1 = time.time()
            ret, frame = cap.read()
            if not ret: 
                time.sleep(0.1)
                continue
            
            with lock:
                # 상태가 True일 때만 프레임 기록
                if is_recording and out is not None:
                    out.write(frame)
                global_frame = frame.copy()
            
            processing_time = time.time() - t1
            sleep_time = delay - processing_time
            if sleep_time > 0:
                time.sleep(sleep_time)
    finally:
        cap.release()
        if out is not None:
            out.release()

def generate_frames():
    while not exit_event.is_set():
        with lock:
            if global_frame is None:
                continue
            temp_frame = global_frame.copy()
        
        ret, buffer = cv2.imencode('.jpg', temp_frame, [cv2.IMWRITE_JPEG_QUALITY, 40])
        if not ret: continue
        
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.1)

# ===========================================================================
# [프론트엔드 (웹 UI)] JavaScript가 포함된 HTML
# ===========================================================================
@app.route('/')
def index():
    html = """
    <html>
    <head>
        <title>웹캠 녹화 제어기</title>
        <style>
            body { font-family: sans-serif; text-align: center; background: #222; color: #fff; margin-top: 20px; }
            .btn { padding: 15px 30px; font-size: 18px; margin: 10px; cursor: pointer; border: none; border-radius: 5px; color: white; font-weight: bold; }
            .btn-start { background-color: #d32f2f; }
            .btn-start:hover { background-color: #b71c1c; }
            .btn-stop { background-color: #1976d2; }
            .btn-stop:hover { background-color: #1565c0; }
            #status { font-size: 20px; margin: 20px; color: #4caf50; }
            img { border: 3px solid #555; border-radius: 10px; max-width: 100%; height: auto; }
        </style>
    </head>
    <body>
        <h1>CCTV / 녹화 제어 모니터</h1>
        
        <div>
            <button class="btn btn-start" onclick="sendCommand('/start')">▶ 녹화 시작</button>
            <button class="btn btn-stop" onclick="sendCommand('/stop')">■ 녹화 중지 (저장)</button>
        </div>
        
        <div id="status">현재 상태: 대기 중</div>
        
        <img src="/video_feed" width="640">

        <script>
            // 버튼 클릭 시 Python 백엔드 라우트로 비동기 요청(Fetch)을 보냄
            function sendCommand(endpoint) {
                fetch(endpoint)
                    .then(response => response.text())
                    .then(text => {
                        // 서버에서 돌아온 응답 텍스트로 상태창 업데이트
                        document.getElementById('status').innerText = '현재 상태: ' + text;
                    })
                    .catch(err => console.error('Error:', err));
            }
        </script>
    </body>
    </html>
    """
    return html

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ===========================================================================
# [메인 실행부]
# ===========================================================================
if __name__ == '__main__':
    t_record = threading.Thread(target=record_loop, daemon=True)
    t_record.start()

    print("[알림] 서버가 실행되었습니다. 브라우저에서 http://[라즈베리파이IP]:5000 으로 접속하세요.")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        exit_event.set()
        if out is not None:
            out.release()