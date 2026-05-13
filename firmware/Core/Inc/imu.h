/*
 * imu.h
 *
 *  Created on: May 9, 2026
 *      Author: KCCISTC
 */

#ifndef INC_IMU_H_
#define INC_IMU_H_

#include <stdint.h>
#include <stdlib.h>
#include "sensor_types.h"
#include "usart.h"
#include "string.h"

void IMU_RxCallback_RPI(void);
void IMU_Process(void);
void IMU_ReadData(void);
void IMU_RxCallback(void);
void IMU_Init(void);
void IMU_Filter(IMU_Data *data);

#endif /* INC_IMU_H_ */
