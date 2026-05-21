/*
 * motor.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "motor.h"

const uint8_t DIR_FORWARD = 0;   // 전진
const uint8_t DIR_BACKWARD = 1;   // 후진
const float ROTATE_TRIGGER = 6.3f;   // 회전 임계값
const float TARGET_ANGLE_NONE_SIGN = 200.0f;   // None 사인
volatile float output_pid = 0.0f;
volatile float diff_search = 0.0f;
uint32_t cnt = 0;
float *ds;

uint8_t BASE_ROTATE_SPEED = 130;   // 회전 속도
uint8_t BASE_STRAIGHT_SPEED = 130;   // 직진 속도
uint8_t SEARCH_SPEED = 100;
MotorPID_t motor_pid;

void Motor_PID_Init(float p, float i, float d) {
	motor_pid.Kp = p;
	motor_pid.Ki = i;
	motor_pid.Kd = d;
	motor_pid.output_limit = 255.0f;
	motor_pid.i_limit = 100.0f;
}

void Motor_PID_Reset(float current_yaw) {
	motor_pid.target_yaw = current_yaw;
	motor_pid.prev_error = 0.0f;
	motor_pid.integral = 0.0f;
	output_pid = 0.0f;
}

void Motor_PID_UpdateGain(float p, float i, float d) {
	motor_pid.Kp = p * 0.7f;      	// 0 ~ 100 스케일링 -> 0.0 ~ 70.0
	motor_pid.Ki = i * 0.1f;      	// 0 ~ 100 스케일링 -> 0.0 ~ 10.0
	motor_pid.Kd = d * 0.03f;      	// 0 ~ 100 스케일링 -> 0.0 ~  3.0
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

float Calculate_PID(float error, float current_yaw) {
	// 시간 주기
	float dt = 0.01f;

	// PID 연산
	float P = motor_pid.Kp * error;

	motor_pid.integral += error * dt;
	// Anti-windup
	if (motor_pid.integral > motor_pid.i_limit)
		motor_pid.integral = motor_pid.i_limit;
	if (motor_pid.integral < -motor_pid.i_limit)
		motor_pid.integral = -motor_pid.i_limit;

	float I = motor_pid.Ki * motor_pid.integral;

	float d_yaw = current_yaw - motor_pid.prev_yaw;
	if (d_yaw > 180.0f) d_yaw -= 360.0f;
	if (d_yaw < -180.0f) d_yaw += 360.0f;

	// 주의: 센서값이 증가하면 오차는 감소하므로 앞에 -(마이너스)를 붙여야 함
	float D = -motor_pid.Kd * (d_yaw / dt);
	motor_pid.prev_yaw = current_yaw;

//	float D = motor_pid.Kd * (error - motor_pid.prev_error) / dt;
//	motor_pid.prev_error = error;

	motor_pid.output = P + I + D; // 구조체 업데이트

	// 출력 제한
	if (motor_pid.output > motor_pid.output_limit)
		motor_pid.output = motor_pid.output_limit;
	if (motor_pid.output < -motor_pid.output_limit)
		motor_pid.output = -motor_pid.output_limit;

	return motor_pid.output;
}

void Straight_Robot(int base_speed, float diff, uint8_t target_dir, float yaw) {
	// TIM4 인터럽트에 의해 20ms 주기로 호출되므로,
	// 내부 dt = 0.02f 연산이 정확히 성립함
	output_pid = Calculate_PID(diff, yaw);

	float l_f, r_f;
//	l_f = (float) base_speed + output_pid;
//	r_f = (float) base_speed - output_pid;

//	아래걸로 후진할때 PID 테스트
	if (target_dir == DIR_FORWARD) {
		// 전진 시: 방금 전 테스트해서 맞췄던 정상적인 부호
		l_f = (float) base_speed + output_pid;
		r_f = (float) base_speed - output_pid;
	} else {
		// 후진 시: 꼬리가 반대로 쏠리는 것을 막기 위해 부호 반전
		l_f = (float) base_speed - output_pid;
		r_f = (float) base_speed + output_pid;
	}

	// 포화(Saturation) 방지
	if (l_f > 255.0f)
		l_f = 255.0f;
	else if (l_f < 0.0f)
		l_f = 0.0f;
	if (r_f > 255.0f)
		r_f = 255.0f;
	else if (r_f < 0.0f)
		r_f = 0.0f;

	Move_Robot(target_dir, (uint8_t) l_f, target_dir, (uint8_t) r_f);
}

// 계산된 오차값으로 로봇 회전
uint8_t Rotate_Robot(float error) {
	// 에러가 양수면  우회전
	if (error > 0) {
		Move_Robot(DIR_FORWARD, BASE_ROTATE_SPEED, DIR_BACKWARD,
				BASE_ROTATE_SPEED);
	} else {
		Move_Robot(DIR_BACKWARD, BASE_ROTATE_SPEED, DIR_FORWARD,
				BASE_ROTATE_SPEED);
	}
	return 0;
}

void Object_Search(float yaw, float last_yaw) {
	uint8_t speed = Adjust_Speed(yaw, last_yaw);
	Move_Robot(DIR_BACKWARD, speed, DIR_FORWARD, speed);
}

uint8_t Adjust_Speed(float yaw, float last_yaw) {
	diff_search = last_yaw - yaw;

	if (diff_search > 180.0f)
		diff_search -= 360.0f;
	if (diff_search < -180.0f)
		diff_search += 360.0f;

	if (SEARCH_SPEED >= 252)
		SEARCH_SPEED = 252;
	else if (SEARCH_SPEED <= 90)
		SEARCH_SPEED = 90;

	// yaw값의 차이가 임계값보다 작으면 PWM(BASE_SPEED) 증가
	if (fabsf(diff_search) < 0.1f)
		SEARCH_SPEED += 2;
	else if (fabsf(diff_search) > 0.2f)
		SEARCH_SPEED -= 2;

	return SEARCH_SPEED;
}

void Stop_Robot(void) {
	Move_Robot(0, 0, 0, 0);
}

