import serial
import struct
import threading
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time

matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

# ── 설정 ──────────────────────────────────────────
PORT        = 'COM3'
BAUD        = 115200
WINDOW_SEC  = 20  # 슬라이딩 윈도우 시간 (초)

# ── 프로토콜 상수 ─────────────────────────────────
HEADER_1      = 0xAA
HEADER_2      = 0xBB
END           = 0xEE
PACKET_FORMAT = '<ffIffII'
PACKET_SIZE   = struct.calcsize(PACKET_FORMAT)

# ── 데이터 버퍼 (timestamp, value) 쌍으로 저장 ───
temperature   = []
temperature_f = []
yaw           = []
yaw_f         = []

# ── 시리얼 연결 ───────────────────────────────────
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"[연결됨] {PORT} @ {BAUD}bps")
except Exception as e:
    print(f"[에러] 시리얼 연결 실패: {e}")
    exit()


# ── 바이너리 패킷 파싱 ───────────────────────────
def calc_checksum(data):
    return sum(data) & 0xFF

def read_packet():
    while True:
        b1 = ser.read(1)
        if not b1 or b1[0] != HEADER_1:
            continue
        b2 = ser.read(1)
        if not b2 or b2[0] != HEADER_2:
            continue
        break

    length = ser.read(1)[0]
    if length != PACKET_SIZE:
        return None

    data     = ser.read(length)
    checksum = ser.read(1)[0]
    end      = ser.read(1)[0]

    if end != END or calc_checksum(data) != checksum:
        return None

    temperature, temperature_f, _, yaw, yaw_f, _, _ = struct.unpack(PACKET_FORMAT, data)
    return temperature, temperature_f, yaw, yaw_f


# ── 오래된 데이터 제거 ────────────────────────────
def trim_window(buf, now):
    cutoff = now - WINDOW_SEC
    while buf and buf[0][0] < cutoff:
        buf.pop(0)


# ── 차트 설정 ─────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(12, 9))
fig.patch.set_facecolor('#1a1a2e')
fig.suptitle('센서 데이터 실시간 모니터링', fontsize=14, color='white', fontweight='bold')
plt.subplots_adjust(hspace=0.6)

titles = ['온도 (°C)', 'Yaw - 전체 범위 (°)', 'Yaw - 정밀 범위 (°)']
colors = [('#ff6b6b', '#ffd93d'), ('#20c997', '#f06595'), ('#4d96ff', '#cc5de8')]

for ax, title, (c1, c2) in zip(axes, titles, colors):
    ax.set_facecolor('#16213e')
    ax.set_title(title, color='white', fontsize=10, pad=8)
    ax.tick_params(colors='#aaaaaa', labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor('#333366')
    ax.grid(True, color='#333366', alpha=0.5, linewidth=0.5)

axes[1].set_ylim(-180, 180)
axes[2].set_ylim(-1, 1)

lines = []
for ax, (c1, c2) in zip(axes, colors):
    l1, = ax.plot([], [], color=c1, linewidth=1.5, linestyle='--', label='원본', alpha=0.8)
    l2, = ax.plot([], [], color=c2, linewidth=2.0, linestyle='-',  label='필터링', alpha=1.0)
    ax.legend(loc='upper right', fontsize=7, facecolor='#16213e', labelcolor='white', framealpha=0.7)
    lines.append((l1, l2))

axes[0].set_xlabel('시간 (초)', color='#aaaaaa', fontsize=8)
axes[0].set_ylabel('온도 (°C)', color='#aaaaaa', fontsize=8)
axes[1].set_xlabel('시간 (초)', color='#aaaaaa', fontsize=8)
axes[1].set_ylabel('Yaw (°)', color='#aaaaaa', fontsize=8)
axes[2].set_xlabel('시간 (초)', color='#aaaaaa', fontsize=8)
axes[2].set_ylabel('Yaw (°)', color='#aaaaaa', fontsize=8)


# ── 시리얼 읽기 스레드 ───────────────────────────
SAMPLE_INTERVAL = 0.5  # 초 단위 샘플링 간격
last_sample_time = 0.0

def serial_reader():
    global last_sample_time
    while True:
        try:
            parsed = read_packet()
            if parsed:
                now = time.time()
                t, tf, y, yf = parsed
                print(f"온도={t:6.2f}°C (필터={tf:.2f}) | yaw={y:7.2f}° (필터={yf:.2f})")
                if now - last_sample_time >= SAMPLE_INTERVAL:
                    temperature.append((now, t))
                    temperature_f.append((now, tf))
                    yaw.append((now, y))
                    yaw_f.append((now, yf))
                    last_sample_time = now
        except:
            pass

thread = threading.Thread(target=serial_reader, daemon=True)
thread.start()


# ── 애니메이션 업데이트 ───────────────────────────
def update(frame):
    now = time.time()

    # 20초 이전 데이터 제거
    for buf in [temperature, temperature_f, yaw, yaw_f]:
        trim_window(buf, now)

    if len(temperature) == 0:
        return [l for pair in lines for l in pair]

    # X축: 현재 기준 상대 시간(초)
    def to_x(buf):
        return [t - now + WINDOW_SEC for t, _ in buf]

    def to_y(buf):
        return [v for _, v in buf]

    # 온도 차트 (슬라이딩 윈도우 + 동적 스케일)
    xs = to_x(temperature)
    lines[0][0].set_data(xs, to_y(temperature))
    lines[0][1].set_data(xs, to_y(temperature_f))
    axes[0].set_xlim(0, WINDOW_SEC)
    axes[0].relim()
    axes[0].autoscale_view(scalex=False)

    # Yaw 전체 범위 차트 (-180 ~ 180 고정)
    xs = to_x(yaw)
    lines[1][0].set_data(xs, to_y(yaw))
    lines[1][1].set_data(xs, to_y(yaw_f))
    axes[1].set_xlim(0, WINDOW_SEC)
    axes[1].set_ylim(-180, 180)

    # Yaw 정밀 범위 차트 (-1 ~ 1 고정, 중앙 0)
    lines[2][0].set_data(xs, to_y(yaw))
    lines[2][1].set_data(xs, to_y(yaw_f))
    axes[2].set_xlim(0, WINDOW_SEC)
    axes[2].set_ylim(-1, 1)

    return [l for pair in lines for l in pair]


# ── 실행 ──────────────────────────────────────────
ani = animation.FuncAnimation(fig, update, interval=100, blit=False)
plt.show()
ser.close()
