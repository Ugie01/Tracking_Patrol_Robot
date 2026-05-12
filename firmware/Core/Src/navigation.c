/*
 * navigation.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "navigation.h"
#include "motor.h"

extern uint8_t target_dir;

PID_Navigation nav;

void Nav_Init(float p, float i, float d) {
    nav.Kp = p;
    nav.Ki = i;
    nav.Kd = d;
    nav.prev_error = 0.0f;
    nav.integral = 0.0f;
    nav.output_limit = 100.0f;
}

void Nav_Reset(float current_yaw) {
    nav.target_yaw = current_yaw;
    nav.prev_error = 0.0f;
    nav.integral = 0.0f;
}

void Nav_DriveStraight(int base_speed, float current_yaw) {
    float error = nav.target_yaw - current_yaw;

    if (error > 180.0f) error -= 360.0f;
    if (error < -180.0f) error += 360.0f;

    nav.error = error;

    // PID 연산
    float P = nav.Kp * error;
    nav.integral += error;
    float I = nav.Ki * nav.integral;
    float D = nav.Kd * (error - nav.prev_error);
    nav.prev_error = error;

    float output = P + I + D;

    if (output > nav.output_limit) output = nav.output_limit;
    if (output < -nav.output_limit) output = -nav.output_limit;

    int left_speed, right_speed;

    if (target_dir == 1) { // 전진
        left_speed = base_speed - (int)output;
        right_speed = base_speed + (int)output;
    }
    else if (target_dir == 2) { // 후진
        left_speed = base_speed + (int)output;
        right_speed = base_speed - (int)output;
    }
    else {
        left_speed = base_speed;
        right_speed = base_speed;
    }

    // 속도 제한 (0~255)
    if (left_speed > 255) left_speed = 255;
    if (left_speed < 0) left_speed = 0;
    if (right_speed > 255) right_speed = 255;
    if (right_speed < 0) right_speed = 0;

    Move_Robot(target_dir, (uint8_t)left_speed, target_dir, (uint8_t)right_speed);
}
