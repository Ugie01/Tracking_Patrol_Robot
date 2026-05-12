/*
 * uart_protocol.h
 *
 *  Created on: May 12, 2026
 *      Author: KCCISTC
 */

#ifndef INC_UART_PROTOCOL_H_
#define INC_UART_PROTOCOL_H_

#include <stdint.h>
#include "sensor_types.h"
#include "usart.h"

uint8_t UART_CalcChecksum(uint8_t *data, uint16_t len);
void UART_SendPacket(UART_HandleTypeDef *huart, SensorPacket *packet);


#endif /* INC_UART_PROTOCOL_H_ */
