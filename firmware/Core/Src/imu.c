#include "imu.h"

uint8_t rx_data;
char rx_buffer[100];
int buffer_idx = 0;
int data_ready = 0;

// 필터링 전용
static float roll_f = 0.0f;
static float pitch_f = 0.0f;
static float yaw_f = 0.0f;
static float alpha = 0.95f;

extern IMU_Data imu_data;

void IMU_ReadData(void) {
	if (data_ready == 1) {
	    if (rx_buffer[0] == '*') {
	        sscanf(rx_buffer, "*%f,%f,%f",
	        		&imu_data.roll, &imu_data.pitch,  &imu_data.yaw);
	    }
	    data_ready = 0;
	}
}

/*
 * 필터링 (상보 필터 적용)
 */
void IMU_Filter(IMU_Data *data) {
	roll_f  = alpha * data->roll  + (1.0f - alpha) * roll_f;
	pitch_f = alpha * data->pitch + (1.0f - alpha) * pitch_f;
	yaw_f   = alpha * data->yaw   + (1.0f - alpha) * yaw_f;

	data->roll_f  = roll_f;
	data->pitch_f = pitch_f;
	data->yaw_f   = yaw_f;
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
