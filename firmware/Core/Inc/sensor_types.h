/*
 * sensor_types.h
 *
 *  Created on: May 8, 2026
 *      Author: KCCISTC
 */

#ifndef INC_SENSOR_TYPES_H_
#define INC_SENSOR_TYPES_H_

typedef struct {
	float temperature;
	float temperature_f;
} BME280_Data_t;

typedef struct {
    float yaw;
    float yaw_f;
} IMU_Data_t;

#endif /* INC_SENSOR_TYPES_H_ */
