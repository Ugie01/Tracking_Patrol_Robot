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
} BME280_Data;

typedef struct {
    float roll;
    float pitch;
    float yaw;
} IMU_Data;

typedef struct {
	BME280_Data bme_data;
	IMU_Data imu_data;
} SensorPacket;



#endif /* INC_SENSOR_TYPES_H_ */
