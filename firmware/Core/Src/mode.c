/*
 * mode.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "mode.h"
#include "motor.h"
#include "sensor_types.h"
#include "navigation.h"

extern IMU_Data imu_data;
extern uint8_t is_straight_requested;
extern uint8_t target_speed;
extern uint8_t target_dir;
extern uint8_t rpi_stop_flag;
uint8_t current_robot_mode = 1;
static uint8_t is_first_entry = 1;
static uint8_t none_cnt = 0;

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
				Nav_Search();
				none_cnt = 0;
			} else {
				none_cnt ++;
			}
		} else {
			none_cnt = 0;
			if (rpi_stop_flag) {
				if (diff >= ROTATE_TRIGGER) {
					Nav_RotateTo(target_angle, imu_data.yaw_f);
				}
				else{
					Stop_Robot();
				}
			} else {
				if (diff >= ROTATE_TRIGGER) {
					Nav_RotateTo(target_angle, imu_data.yaw_f);
				} else {
					target_dir = 0;
					Nav_DriveStraight(ROTATE_SPEED, imu_data.yaw_f);
				}
			}
		}

	case MODE_MANUAL:
		if (is_straight_requested) {
			if (is_first_entry) {
				Nav_Reset(imu_data.yaw_f);
				is_first_entry = 0;
			}
			Nav_DriveStraight(target_speed, imu_data.yaw_f);
		} else {
			is_first_entry = 1;
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


