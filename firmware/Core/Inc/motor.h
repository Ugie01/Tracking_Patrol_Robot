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
    float Kp;
    float Ki;
    float Kd;
    //유지하려는 목표 yaw 각도
    float target_yaw;
    //이전 오차 → D항 계산에 사용
    float prev_error;
    //누적 오차 → I항 계산에 사용
    float integral;
    // PID 출력 최대값(100)
    float output_limit;
    float error;
	float output;
} MOTOR_PID;

#define MOTOR_MAX_SPEED 255
#define DIR_FORWARD     1
#define DIR_BACKWARD    0

////////// 트래킹 모드 제어 관련 //////////
// 오차 허용값
//#define ROTATE_THRESHOLD 1.0f
// 회전 임계값
#define ROTATE_TRIGGER   10.0f
//#define ROTATE_SPEED	133
#define NONE_TRIGGER 	100
#define TARGET_ANGLE_NONE_SIGN 	200.0f

extern float target_angle;
extern float output_pid;
extern MOTOR_PID motor_pid;
extern uint8_t ROTATE_SPEED;
extern uint8_t STRAIGHT_SPEED;

//////////////////////////////////////

void MOTOR_PID_Init(float p, float i, float d) ;
void MOTOR_PID_Reset(float current_yaw) ;
void Motor_Init(void);
void Move_Robot(uint8_t left_dir, uint8_t left_speed, uint8_t right_dir, uint8_t right_speed);
void Stop_Robot(void);
void Straight_Robot(int base_speed, float *current_yaw, uint8_t target_dir) ;
uint8_t Rotate_Robot(float target_angle, float current_yaw) ;
void Motor_SetSpeed(int16_t left_speed, int16_t right_speed);
float Calculate_PID(float error) ;
void Object_Search(void) ;

#endif /* INC_MOTOR_H_ */
