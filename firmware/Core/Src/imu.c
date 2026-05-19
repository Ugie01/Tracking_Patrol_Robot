#include "imu.h"

uint8_t dma_rx_buffer[DMA_BUF_SIZE];
uint8_t rx_data = 0;
int buffer_idx = 0;
int data_ready = 0;

static volatile uint8_t imu_request_flag = 0;

// 필터링 전용
static float yaw_f = 0.0f;
static float alpha = 0.95f;

IMU_Data_t imu_data;

void IMU_ReadData(void) {
	// SOP(Start of Packet) 확인 : 0x55 0x55 검색
	if (dma_rx_buffer[0] == 0x55 && dma_rx_buffer[1] == 0x55) {

		// 체크섬(CHK) 검증 계산
		// SOP를 포함하여 데이터 마지막 바이트까지 모두 더함
		uint16_t calculated_chk = 0;
		for (uint8_t j = 0; j < DMA_BUF_SIZE - 2; j++) {
			calculated_chk += dma_rx_buffer[j];
		}

		// 패킷에 포함되어 들어온 체크섬 값 추출 (Big-Endian 결합)
		uint16_t received_chk = (uint16_t) __REV16(
				*(uint16_t*) &dma_rx_buffer[DMA_BUF_SIZE - 2]);

		// 체크섬이 일치하는 경우에만 데이터 신뢰 및 파싱 진행
		if (calculated_chk == received_chk) {
			// 데이터 추출 (2바이트 정수형 결합, 매뉴얼 상 상위 바이트가 먼저 오는 Big-Endian 형태)
			int16_t raw_yaw = (int16_t) __REV16(*(uint16_t*) &dma_rx_buffer[6]);

			// 스케일링 복원
			// 매뉴얼 예시 상 -719가 -7.19도이므로 100.0f로 나누어 실수형(float) 변환
			imu_data.yaw = (float) raw_yaw / 100.0f;

			// 필터 함수 호출
			IMU_Filter(&imu_data);
		}
	}
}

// 필터링 (상보 필터 적용)
void IMU_Filter(IMU_Data_t *data) {
	yaw_f = alpha * data->yaw + (1.0f - alpha) * yaw_f;
	data->yaw_f = yaw_f;
}

void IMU_RxCallback_RPI(void) {
	imu_request_flag = 1;
}

void IMU_Process(void) {
	if (!imu_request_flag)
		return;
	imu_request_flag = 0;

	HAL_UART_Transmit(&huart1, (uint8_t*) &imu_data.yaw_f, sizeof(float), 100);
}

void IMU_Init(void) {
	HAL_UART_Receive_DMA(&huart3, dma_rx_buffer, DMA_BUF_SIZE);
}
