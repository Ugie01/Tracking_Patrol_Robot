/*
 * sensor_types.h
 *
 *  Created on: May 8, 2026
 *      Author: KCCISTC
 */

#ifndef INC_SENSOR_TYPES_H_
#define INC_SENSOR_TYPES_H_

#include <stdint.h>

typedef struct {
	float temperature;
	float temperature_f;
	uint32_t bme_tick;
} BME280_Data;

typedef struct {
    float yaw;
    float yaw_f;
    uint32_t imu_tick;
} IMU_Data;

typedef struct {
	BME280_Data bme_data;
	IMU_Data imu_data;
	uint32_t tick;
} SensorPacket;



#endif /* INC_SENSOR_TYPES_H_ */
