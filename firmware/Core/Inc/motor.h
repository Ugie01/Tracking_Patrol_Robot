/*
 * motor.h
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#ifndef INC_MOTOR_H_
#define INC_MOTOR_H_

#include "main.h"

typedef struct {
	//PID 게인 파라미터
	float Kp, Ki, Kd;
	//유지하려는 목표 yaw 각도
	float target_yaw;
	//이전 오차 → D항 계산에 사용
	float prev_error;
	//누적 오차 → I항 계산에 사용
	float integral;
	// PID 출력 최대값(100)
	float output_limit;
	float i_limit;      // Anti-windup 제한값
	float error;        // 현재 오차
	float output;       // 최종 출력
} MotorPID_t;

extern const uint8_t DIR_FORWARD; 	// 전진
extern const uint8_t DIR_BACKWARD;	// 후진
//extern const uint8_t NONE_TRIGGER;	// None 객체 필터링
extern const float ROTATE_TRIGGER;	// 회전 임계값
extern const float TARGET_ANGLE_NONE_SIGN;	// None 사인

extern volatile float output_pid;

extern uint8_t BASE_ROTATE_SPEED;	// 회전 속도
extern uint8_t BASE_STRAIGHT_SPEED;	// 직진 속도

extern MotorPID_t motor_pid;

//////////////////////////////////////

void Motor_PID_Init(float p, float i, float d);
void Motor_PID_Reset(float current_yaw);
void Motor_PID_UpdateGain(float p, float i, float d);
void Motor_Init(void);
void Move_Robot(uint8_t left_dir, uint8_t left_speed, uint8_t right_dir, uint8_t right_speed);
float Calculate_PID(float error);
void Straight_Robot(int base_speed, float *current_yaw, uint8_t target_dir);
uint8_t Rotate_Robot(float error);
void Object_Search(void);
void Stop_Robot(void);

#endif /* INC_MOTOR_H_ */
