/*
 * imu.h
 *
 *  Created on: May 9, 2026
 *      Author: KCCISTC
 */

#ifndef INC_IMU_H_
#define INC_IMU_H_

#include "main.h"

#define DMA_BUF_SIZE 10

extern UART_HandleTypeDef huart3;
extern IMU_Data_t imu_data;

extern uint8_t dma_rx_buffer[DMA_BUF_SIZE];
extern uint8_t rx_data;
extern int buffer_idx;
extern int data_ready;

void IMU_RxCallback_RPI(void);
void IMU_Process(void);
void IMU_ReadData(void);
void IMU_StartReceive(void);
void IMU_Init(void);
void IMU_Filter(IMU_Data_t *data);

#endif /* INC_IMU_H_ */
