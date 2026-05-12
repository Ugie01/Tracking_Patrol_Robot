/*
 * navigation.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#ifndef __NAVIGATION_H
#define __NAVIGATION_H

#include "main.h"
#include "imu.h"
#include "motor.h"

typedef struct {
    float Kp;
    float Ki;
    float Kd;
    float target_yaw;
    float prev_error;
    float integral;
} PID_Controller;

void Nav_Init(void);
void Nav_SetTargetYaw(float target);
void Nav_DriveStraight(int base_speed);
void Nav_ResetPID(void);

#endif
