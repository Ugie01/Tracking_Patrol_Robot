#include "imu.h"
#include "main.h"
#include <string.h>
#include <stdio.h>

#define IMU_BUF_SIZE 16
#define DMA_BUF_SIZE 100

extern UART_HandleTypeDef huart3;
extern IMU_Data imu_data;

uint8_t dma_rx_buffer[DMA_BUF_SIZE];
char rx_buffer[DMA_BUF_SIZE];
uint8_t rx_data;
int buffer_idx = 0;
int data_ready = 0;


static volatile uint8_t imu_request_flag = 0;


// 필터링 전용
static float yaw_f = 0.0f;
static float alpha = 0.95f;

// 링버퍼
static IMU_Data imu_buf[IMU_BUF_SIZE];
static uint8_t imu_buf_head  = 0;
static uint8_t imu_buf_count = 0;

void IMU_ReadData(void) {
    memcpy(rx_buffer, (char*)dma_rx_buffer, DMA_BUF_SIZE);

    for (int i = DMA_BUF_SIZE - 20; i >= 0; i--) {
        if (rx_buffer[i] == '*') {
            float roll, pitch, yaw_raw;
            if (sscanf(&rx_buffer[i], "*%f,%f,%f", &roll, &pitch, &yaw_raw) == 3) {
                imu_data.yaw = yaw_raw;
                IMU_Filter(&imu_data);
                return;
            }
        }
    }
}

/*
 * 필터링 (상보 필터 적용)
 */
void IMU_Filter(IMU_Data *data) {
	yaw_f   = alpha * data->yaw   + (1.0f - alpha) * yaw_f;
	data->yaw_f   = yaw_f;
}

void IMU_RxCallback_RPI(void) {
     imu_request_flag = 1;
 }


void IMU_Process(void) {
      if (!imu_request_flag) return;
      imu_request_flag = 0;

      char buf[32];
      snprintf(buf, sizeof(buf), "%.2f\n",imu_data.yaw_f);
      HAL_UART_Transmit(&huart1, (uint8_t*)buf, strlen(buf), 100);
  }



void IMU_RxCallback(void) {
//	if (rx_data == '\n' || rx_data == '\r') {
//	    rx_buffer[buffer_idx] = '\0';
//	    data_ready = 1;
//	    buffer_idx = 0;
//	} else {
//	    if (buffer_idx < 99) {
//	        rx_buffer[buffer_idx++] = rx_data;
//	    }
//	}

	HAL_UART_Receive_DMA(&huart3, &rx_data, sizeof(rx_data));
}


void IMU_Init(void) {
	HAL_UART_Receive_DMA(&huart3, dma_rx_buffer, DMA_BUF_SIZE);
}
