/*
 * navigation.h
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#ifndef INC_NAVIGATION_H_
#define INC_NAVIGATION_H_
////////// 트래킹 모드 제어 관련 //////////
// 오차 허용값
//#define ROTATE_THRESHOLD 1.0f
// 회전 임계값
#define ROTATE_TRIGGER   10.0f
#define ROTATE_SPEED 150

extern float target_angle;
//////////////////////////////////////

#include "main.h"
#include <math.h>



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
uint8_t Nav_RotateTo(float target_angle, float current_yaw);

extern PID_Navigation nav;

#endif /* INC_NAVIGATION_H_ */
