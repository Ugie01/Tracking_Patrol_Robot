import serial
import struct

# 시리얼 포트 설정 (포트는 장치관리자에서 확인)
PORT     = 'COM3'
BAUDRATE = 115200

# 프로토콜 상수
HEADER_1 = 0xAA
HEADER_2 = 0xBB
END      = 0xEE

# SensorPacket 구조 (28 bytes, little-endian)
# BME280_Data: temperature(f), temperature_f(f), tick(I)
# IMU_Data:    yaw(f), yaw_f(f), tick(I)
# SensorPacket tick: (I)
PACKET_FORMAT = '<ffIffII'
PACKET_SIZE   = struct.calcsize(PACKET_FORMAT)  # 28 bytes


def calc_checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def parse_packet(data: bytes):
    temperature, temperature_f, bme_tick, yaw, yaw_f, imu_tick, packet_tick = struct.unpack(PACKET_FORMAT, data)
    return {
        'packet_tick'  : packet_tick,
        'bme_tick'     : bme_tick,
        'temperature'  : temperature,
        'temperature_f': temperature_f,
        'imu_tick'     : imu_tick,
        'yaw'          : yaw,
        'yaw_f'        : yaw_f,
    }


def read_packet(ser: serial.Serial):
    # 헤더 동기화
    while True:
        b1 = ser.read(1)
        if not b1:
            continue
        if b1[0] != HEADER_1:
            continue
        b2 = ser.read(1)
        if not b2:
            continue
        if b2[0] == HEADER_2:
            break

    length = ser.read(1)[0]
    if length != PACKET_SIZE:
        return None

    data     = ser.read(length)
    print("RAW:", data.hex())
    checksum = ser.read(1)[0]
    end      = ser.read(1)[0]

    if end != END:
        return None
    if calc_checksum(data) != checksum:
        print("체크섬 오류")
        return None

    return parse_packet(data)


def main():
    with serial.Serial(PORT, BAUDRATE, timeout=1) as ser:
        print(f"{PORT} 연결됨 ({BAUDRATE} baud)")
        print("-" * 60)
        while True:
            packet = read_packet(ser)
            if packet is None:
                continue
            print(
                f"[tick={packet['packet_tick']:6d}ms] "
                f"온도={packet['temperature']:6.2f}°C (필터={packet['temperature_f']:.2f}) bme_tick={packet['bme_tick']}ms | "
                f"yaw={packet['yaw']:7.2f}° (필터={packet['yaw_f']:.2f}) imu_tick={packet['imu_tick']}ms"
            )


if __name__ == '__main__':
    main()
