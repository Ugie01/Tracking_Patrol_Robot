/*
 * motor.h
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#ifndef INC_MOTOR_H_
#define INC_MOTOR_H_

#include "main.h"

#define MOTOR_MAX_SPEED 255
#define DIR_FORWARD     1
#define DIR_BACKWARD    0

void Motor_Init(void);
void Move_Robot(uint8_t left_dir, uint8_t left_speed, uint8_t right_dir, uint8_t right_speed);
void Stop_Robot(void);

#endif /* INC_MOTOR_H_ */
