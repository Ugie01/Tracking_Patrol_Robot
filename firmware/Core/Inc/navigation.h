/*
 * navigation.h
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#ifndef INC_NAVIGATION_H_
#define INC_NAVIGATION_H_

#include "main.h"

typedef struct {
    float Kp;
    float Ki;
    float Kd;
    float target_yaw;
    float prev_error;
    float integral;
    float output_limit;
    float error;
	float output;
} PID_Navigation;

void Nav_Init(float p, float i, float d);
void Nav_Reset(float current_yaw);
void Nav_DriveStraight(int base_speed, float current_yaw);

extern PID_Navigation nav;

#endif /* INC_NAVIGATION_H_ */
