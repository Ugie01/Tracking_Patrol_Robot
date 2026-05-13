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
#include "usart.h"

extern volatile uint8_t rpi_rx_buf;

void BME280_ReadCalibration(void);

void BME280_Process(void);

float BME280_Filter(float new_temp);

void BME280_RxCallback(void);

void BME280_Init(void);


#endif /* INC_BME280_H_ */
