/*
 * bme280.h
 *
 *  Created on: May 9, 2026
 *      Author: KCCISTC
 */

#ifndef INC_BME280_H_
#define INC_BME280_H_

#include "sensor_types.h"
#include "i2c.h"


void BME280_ReadCalibration(void);

void BME280_ReadData(BME280_Data *data);

float BME280_Filter(float new_temp);

void BEM280_Init(void);


#endif /* INC_BME280_H_ */
