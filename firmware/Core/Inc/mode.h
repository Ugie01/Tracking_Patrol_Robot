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

void Set_RobotMode(uint8_t mode);
uint8_t Get_RobotMode(void);
void Process_By_Mode(void);

#endif /* INC_MODE_H_ */

