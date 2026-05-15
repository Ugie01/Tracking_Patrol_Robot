/*
 * mode.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "mode.h"
#include "motor.h"
#include "sensor_types.h"
#include "blt.h"

extern IMU_Data imu_data;
extern uint8_t is_straight_requested;
extern uint8_t target_speed;
extern uint8_t target_dir;
extern uint8_t rpi_stop_flag;
extern uint8_t bl_buffer[BT_PACKET_SIZE];
uint8_t current_robot_mode = 1;
static uint8_t is_first_entry = 1;
static uint8_t none_cnt = 0;
uint8_t ROTATE_SPEED = 80;
uint8_t STRAIGHT_SPEED = 150;
float target_angle = 0.0f;

void Set_RobotMode(uint8_t mode) {
//	if (current_robot_mode != mode) {
//		is_first_entry = 1;
		Stop_Robot();
//	}
	current_robot_mode = mode;
}

uint8_t Get_RobotMode(void) {
	return current_robot_mode;
}

void Process_By_Mode(void) {

	switch (current_robot_mode) {

	case MODE_TRACKING:
		float diff = Get_Diff();
		if (target_angle == TARGET_ANGLE_NONE_SIGN) {
			if ( none_cnt >= NONE_TRIGGER ) {
				Object_Search();
				none_cnt = 0;
			} else {
				none_cnt ++;
			}
		} else {
			none_cnt = 0;
			if (rpi_stop_flag) {
				if (diff >= ROTATE_TRIGGER) {
					Rotate_Robot(target_angle, imu_data.yaw_f);
				}
				else{
					Stop_Robot();
				}
			} else {
				if (diff >= ROTATE_TRIGGER) {
					Rotate_Robot(target_angle, imu_data.yaw_f);
				} else {
					target_dir = 0;
					Straight_Robot(STRAIGHT_SPEED, &imu_data.yaw_f, target_dir);
				}
			}
		}
		break;

	case MODE_MANUAL:
		if (is_straight_requested) {
			if (is_first_entry) {
				MOTOR_PID_Reset(imu_data.yaw_f);
				is_first_entry = 0;
			}
			Straight_Robot(target_speed, &imu_data.yaw_f, target_dir);
		} else {
			is_first_entry = 1;
			// 직진이 아니면 즉시 모터 제어
			Move_Robot(bl_buffer[2], bl_buffer[3], bl_buffer[4], bl_buffer[5]);
		}
		break;
	}

}


float Get_Diff(void) {
	float diff = target_angle - imu_data.yaw_f;
	if (diff > 180.0f)
		diff -= 360.0f;
	if (diff < -180.0f)
		diff += 360.0f;

	return diff;
}


