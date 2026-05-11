#include "imu.h"

uint8_t rx_data;
char rx_buffer[100];
int buffer_idx = 0;
int data_ready = 0;

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
