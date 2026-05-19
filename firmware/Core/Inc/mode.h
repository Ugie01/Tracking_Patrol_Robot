/*
 * mode.h
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#ifndef INC_MODE_H_
#define INC_MODE_H_

#include "main.h"

#define MODE_MANUAL   0
#define MODE_TRACKING 1

extern uint8_t rpi_stop_flag;
extern float target_angle;
extern uint8_t current_robot_mode;

void Set_RobotMode(uint8_t mode);
uint8_t Get_RobotMode(void);
void Process_By_Mode(float yaw, float last_yaw);
float Get_Diff(float yaw) ;

#endif /* INC_MODE_H_ */

