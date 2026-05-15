/*
 * motor.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "motor.h"
#include "tim.h"
#include <stdlib.h>

extern TIM_HandleTypeDef htim2;
float output_pid = 0.0f;
MOTOR_PID motor_pid;


void MOTOR_PID_Init(float p, float i, float d) {
    motor_pid.Kp = p;
    motor_pid.Ki = i;
    motor_pid.Kd = d;
    motor_pid.prev_error = 0.0f;
    motor_pid.integral = 0.0f;
    motor_pid.output_limit = 100.0f;
}

void MOTOR_PID_Reset(float current_yaw) {
    motor_pid.target_yaw = current_yaw;
    motor_pid.prev_error = 0.0f;
    motor_pid.integral = 0.0f;
}

void Motor_Init(void) {
	HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1); // 왼쪽 모터
	HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2); // 오른쪽 모터
}

void Move_Robot(uint8_t left_dir, uint8_t left_speed, uint8_t right_dir,
		uint8_t right_speed) {

	if (left_dir == DIR_FORWARD) {
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_0, GPIO_PIN_SET);
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_1, GPIO_PIN_RESET);
	} else {
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_0, GPIO_PIN_RESET);
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_1, GPIO_PIN_SET);
	}

	if (right_dir == DIR_FORWARD) {
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_2, GPIO_PIN_RESET);
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_3, GPIO_PIN_SET);
	} else {
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_2, GPIO_PIN_SET);
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_3, GPIO_PIN_RESET);
	}

	__HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, left_speed);
	__HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, right_speed);
}

float Calculate_PID(float error) {
	// 시간 주기
	float dt = 0.02f;

	// PID 연산
	float P = motor_pid.Kp * error;
	motor_pid.integral += error * dt;
	if (motor_pid.integral > 50.0f)
		motor_pid.integral = 50.0f;
	if (motor_pid.integral < -50.0f)
		motor_pid.integral = -50.0f;
	float I = motor_pid.Ki * motor_pid.integral;
	float D = motor_pid.Kd * (error - motor_pid.prev_error) / dt;
	motor_pid.prev_error = error;

	float output = P + I + D;

	if (output > motor_pid.output_limit)
		output = motor_pid.output_limit;
	if (output < -motor_pid.output_limit)
		output = -motor_pid.output_limit;

	return output;
}

void Straight_Robot(int base_speed, float *current_yaw, uint8_t target_dir) {
    float l_f, r_f;

    if (target_dir == 1) { // 전진
        l_f = (float)base_speed - output_pid;
        r_f = (float)base_speed + output_pid;
    }
    else if (target_dir == 2) { // 후진
        l_f = (float)base_speed + output_pid;
        r_f = (float)base_speed - output_pid;
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


/*
 * 타겟 각도를 사용하여 로봇 회전
 */
uint8_t Rotate_Robot(float target_angle, float current_yaw) {
  float error = target_angle - current_yaw;

  if (error > 180.0f)  error -= 360.0f;
  if (error < -180.0f) error += 360.0f;

  if (error > 0) {
        Move_Robot(1, ROTATE_SPEED, 0, ROTATE_SPEED);
  } else {
    	Move_Robot(0, ROTATE_SPEED, 1, ROTATE_SPEED);
  }
  return 0;
}

void Object_Search(void) {
      Move_Robot(1, ROTATE_SPEED, 0, ROTATE_SPEED);
  }

void Stop_Robot(void) {
	Move_Robot(0, 0, 0, 0);
}

