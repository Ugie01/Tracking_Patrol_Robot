/*
 * mode.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "mode.h"

static uint8_t is_first_entry = 1;
uint8_t current_robot_mode = 0;

uint8_t rpi_stop_flag = 0;
float target_angle = 0.0f;
void Set_RobotMode(uint8_t mode) {
	Stop_Robot();
	current_robot_mode = mode;
}

uint8_t Get_RobotMode(void) {
	return current_robot_mode;
}

void Process_By_Mode(float yaw, float last_yaw) {
	float diff = Get_Diff(yaw);
	switch (current_robot_mode) {

	case MODE_TRACKING:
		switch (rpi_stop_flag) {
		case 0:
			if (fabsf(diff) >= ROTATE_TRIGGER) {
				if (is_straight_flag == 1) {
					is_straight_flag = 0;
					motor_pid.integral = 0.0f;
				}
				Rotate_Robot(diff);
			} else {
				// [핵심 추가] 회전하다가 직진 궤도로 최초 진입하는 순간 PID 찌꺼기 초기화
				if (is_straight_flag == 0) {
					motor_pid.integral = 0.0f;
					motor_pid.prev_error = diff; // D항 폭발(Kick) 방지
					is_straight_flag = 1;
				}
				Straight_Robot(BASE_STRAIGHT_SPEED, diff, DIR_FORWARD, yaw);
			}
			break;
		case 1:
			is_straight_flag = 0;
			if (fabsf(diff) >= ROTATE_TRIGGER)
				Rotate_Robot(diff);
			else
				Stop_Robot();
			break;
		case 2: // 후진
			is_straight_flag = 1;
			Straight_Robot(BASE_STRAIGHT_SPEED, diff, DIR_BACKWARD, yaw);
			break;
		case 4: // 객체 탐지 불가
			is_straight_flag = 0; // 타이머 4의 자동 PID 연산 루프 강제 차단 (I항/D항 초기화)
			Object_Search(yaw, last_yaw);      // 객체 재탐지
			break;
		}
		break;

	case MODE_MANUAL:
		if (is_straight_flag) {
			if (is_first_entry) {
				Motor_PID_Reset(yaw);
				is_first_entry = 0;
				is_straight_flag = 1;
			}
			if (robot_L_dir)
				Straight_Robot(robot_L_speed, diff, DIR_BACKWARD, yaw);
			else
				Straight_Robot(robot_L_speed, diff, DIR_FORWARD, yaw);

		} else {
			is_first_entry = 1;
			is_straight_flag = 0;
			Move_Robot(robot_L_dir, robot_L_speed, robot_R_dir, robot_R_speed);
		}
		break;
	}

}

float Get_Diff(float yaw) {
	float diff = motor_pid.target_yaw - yaw;
	if (diff > 180.0f)
		diff -= 360.0f;
	if (diff < -180.0f)
		diff += 360.0f;

	return diff;
}

