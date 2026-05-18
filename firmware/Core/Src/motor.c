/*
 * motor.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "motor.h"

const uint8_t DIR_FORWARD = 0;	// 전진
const uint8_t DIR_BACKWARD = 1;	// 후진
//const uint8_t NONE_TRIGGER = 200;	// None 객체 필터링
const float ROTATE_TRIGGER = 6.3f;	// 회전 임계값
const float TARGET_ANGLE_NONE_SIGN = 200.0f;	// None 사인

volatile float output_pid = 0.0f;

uint8_t BASE_ROTATE_SPEED = 130;	// 회전 속도
uint8_t BASE_STRAIGHT_SPEED = 130;	// 직진 속도

MotorPID_t motor_pid;

void Motor_PID_Init(float p, float i, float d) {
	motor_pid.Kp = p;
	motor_pid.Ki = i;
	motor_pid.Kd = d;
	motor_pid.output_limit = 120.0f;
	motor_pid.i_limit = 100.0f;
}

void Motor_PID_Reset(float current_yaw) {
	motor_pid.target_yaw = current_yaw;
	motor_pid.prev_error = 0.0f;
	motor_pid.integral = 0.0f;
	output_pid = 0.0f;
}

void Motor_PID_UpdateGain(float p, float i, float d){
	motor_pid.Kp = p * 0.25f;		// 0 ~ 100 스케일링 -> 0.0 ~ 25.0
	motor_pid.Ki = i * 0.02f;		// 0 ~ 100 스케일링 -> 0.0 ~ 20.0
	motor_pid.Kd = d * 0.02f;		// 0 ~ 100 스케일링 -> 0.0 ~ 20.0
}

void Motor_Init(void) {
	HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1); // 왼쪽 모터
	HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2); // 오른쪽 모터
}

void Move_Robot(uint8_t left_dir, uint8_t left_speed, uint8_t right_dir,
		uint8_t right_speed) {

	// 왼쪽 모터 전진
	if (left_dir == DIR_FORWARD) {
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_1, GPIO_PIN_SET);
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_0, GPIO_PIN_RESET);
	} else {
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_1, GPIO_PIN_RESET);
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_0, GPIO_PIN_SET);
	}

	// 오른쪽 모터 전진
	if (right_dir == DIR_FORWARD) {
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_3, GPIO_PIN_RESET);
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_2, GPIO_PIN_SET);
	} else {
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_3, GPIO_PIN_SET);
		HAL_GPIO_WritePin(GPIOC, GPIO_PIN_2, GPIO_PIN_RESET);
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
	// Anti-windup
	if (motor_pid.integral > motor_pid.i_limit) motor_pid.integral = motor_pid.i_limit;
	if (motor_pid.integral < -motor_pid.i_limit) motor_pid.integral = -motor_pid.i_limit;

	float I = motor_pid.Ki * motor_pid.integral;
	float D = motor_pid.Kd * (error - motor_pid.prev_error) / dt;
	motor_pid.prev_error = error;

	motor_pid.output = P + I + D; // 구조체 업데이트

	// 출력 제한
	if (motor_pid.output > motor_pid.output_limit) motor_pid.output = motor_pid.output_limit;
	if (motor_pid.output < -motor_pid.output_limit) motor_pid.output = -motor_pid.output_limit;

	return motor_pid.output;
}

void Straight_Robot(int base_speed, float *current_yaw, uint8_t target_dir) {
	float l_f, r_f;
	float diff = Get_Diff();
	if(diff > 0){
		l_f = (float) base_speed + output_pid;
		r_f = (float) base_speed - output_pid;
	}
	else {
		l_f = (float) base_speed - output_pid;
		r_f = (float) base_speed + output_pid;
	}

	if (l_f > 255.0f) l_f = 255.0f;
	else if (l_f < 0.0f) l_f = 0.0f;
	if (r_f > 255.0f) r_f = 255.0f;
	else if (r_f < 0.0f) r_f = 0.0f;

	// 속도 제한 (0~255)
	uint8_t left_speed = (uint8_t) l_f;
	uint8_t right_speed = (uint8_t) r_f;

	Move_Robot(target_dir, left_speed, target_dir, right_speed);
}

// 계산된 오차값으로 로봇 회전
uint8_t Rotate_Robot(float error) {
	// 에러가 양수면  우회전
	if (error > 0) {
		Move_Robot(DIR_FORWARD, BASE_ROTATE_SPEED, DIR_BACKWARD, BASE_ROTATE_SPEED);
	} else {
		Move_Robot(DIR_BACKWARD, BASE_ROTATE_SPEED, DIR_FORWARD, BASE_ROTATE_SPEED);
	}
	return 0;
}

void Object_Search(void) {
	Move_Robot(DIR_BACKWARD, BASE_ROTATE_SPEED, DIR_FORWARD, BASE_ROTATE_SPEED);
}

void Stop_Robot(void) {
	Move_Robot(0, 0, 0, 0);
}

