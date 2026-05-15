/*
 * navigation.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "navigation.h"
#include "motor.h"

extern uint8_t target_dir;
float target_angle = 0.0f;

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


/*
 * 타겟 각도를 사용하여 로봇 회전
 */
uint8_t Nav_RotateTo(float target_angle, float current_yaw) {
  float error = target_angle - current_yaw;

  if (error > 180.0f)  error -= 360.0f;
  if (error < -180.0f) error += 360.0f;

//  if (fabsf(error) <= ROTATE_THRESHOLD) {
//	  Stop_Robot();
//	  return 1;
//  }

  if (error > 0) {
        Move_Robot(1, ROTATE_SPEED, 0, ROTATE_SPEED);
  } else {
    	Move_Robot(0, ROTATE_SPEED, 1, ROTATE_SPEED);
  }
  return 0;
}


void Nav_DriveStraight(int base_speed, float current_yaw) {
    float error = nav.target_yaw - current_yaw;

    if (error > 180.0f) error -= 360.0f;
    if (error < -180.0f) error += 360.0f;

    nav.error = error;

    // 시간 주기
    float dt = 0.02f;

    // PID 연산
    float P = nav.Kp * error;
    nav.integral += error * dt;
    if (nav.integral > 50.0f) nav.integral = 50.0f;
    if (nav.integral < -50.0f) nav.integral = -50.0f;
    float I = nav.Ki * nav.integral;
    float D = nav.Kd * (error - nav.prev_error) / dt;
    nav.prev_error = error;

    float output = P + I + D;

    if (output > nav.output_limit) output = nav.output_limit;
    if (output < -nav.output_limit) output = -nav.output_limit;

    float l_f, r_f;

    if (target_dir == 1) { // 전진
        l_f = (float)base_speed - output;
        r_f = (float)base_speed + output;
    }
    else if (target_dir == 2) { // 후진
        l_f = (float)base_speed + output;
        r_f = (float)base_speed - output;
    }
    else {
        l_f = (float)base_speed;
        r_f = (float)base_speed;
    }

    // 속도 제한 (0~255)
    int left_speed = (int)l_f;
    int right_speed = (int)r_f;

    if (left_speed > 255)  left_speed = 255;
    if (left_speed < 0)    left_speed = 0;
    if (right_speed > 255) right_speed = 255;
    if (right_speed < 0)   right_speed = 0;

    Move_Robot(target_dir, (uint8_t)left_speed, target_dir, (uint8_t)right_speed);
}

void Nav_Search(void) {
      Move_Robot(1, ROTATE_SPEED, 0, ROTATE_SPEED);
  }
