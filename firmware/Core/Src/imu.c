#include "imu.h"

#define IMU_BUF_SIZE 16

uint8_t rx_data;
char rx_buffer[100];
int buffer_idx = 0;
int data_ready = 0;

// 필터링 전용
static float yaw_f = 0.0f;
static float alpha = 0.95f;

extern IMU_Data imu_data;

// 링버퍼
static IMU_Data imu_buf[IMU_BUF_SIZE];
static uint8_t imu_buf_head  = 0;
static uint8_t imu_buf_count = 0;


void IMU_ReadData(void) {
	if (data_ready == 1) {
	    if (rx_buffer[0] == '*') {
	    	float roll, pitch;
		    sscanf(rx_buffer, "*%f,%f,%f", &roll, &pitch, &imu_data.yaw);


			IMU_Filter(&imu_data);

			imu_data.imu_tick = HAL_GetTick();

			// 링버퍼에 저장
			imu_buf[imu_buf_head] = imu_data;
			imu_buf_head = (imu_buf_head + 1) % IMU_BUF_SIZE;
			if (imu_buf_count < IMU_BUF_SIZE) imu_buf_count++;
	    }
	    data_ready = 0;
	}
}

/*
 * 필터링 (상보 필터 적용)
 */
void IMU_Filter(IMU_Data *data) {
	yaw_f   = alpha * data->yaw   + (1.0f - alpha) * yaw_f;
	data->yaw_f   = yaw_f;
}

/*
 *  링버퍼에서 target_tick과 가장 가까운 IMU_Data를 찾는 함수
 */
IMU_Data IMU_FindClosest(uint32_t target_tick) {

	IMU_Data best = imu_buf[0];
	uint32_t best_diff = UINT32_MAX;

	for (uint8_t i = 0; i < IMU_BUF_SIZE; i++) {
		int32_t  diff     = (int32_t)(imu_buf[i].imu_tick - target_tick);
		uint32_t abs_diff = (uint32_t)(diff < 0 ? -diff : diff);

		if (abs_diff < best_diff) {
			best_diff = abs_diff;
			best = imu_buf[i];
		}
	}

	return best;
}



void IMU_RxCallback(void) {
	if (rx_data == '\n' || rx_data == '\r') {
	    rx_buffer[buffer_idx] = '\0';
	    data_ready = 1;
	    buffer_idx = 0;
	} else {
	    if (buffer_idx < 99) {
	        rx_buffer[buffer_idx++] = rx_data;
	    }
	}

	HAL_UART_Receive_IT(&huart3, &rx_data, 1);
}


void IMU_Init(void) {
	HAL_UART_Receive_IT(&huart3, &rx_data, 1);
}
