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

static uint8_t current_robot_mode = MODE_MANUAL;
static uint8_t is_first_entry = 1;

void Set_RobotMode(uint8_t mode) {
    if (current_robot_mode != mode) {
        is_first_entry = 1;
        Stop_Robot();
    }
    current_robot_mode = mode;
}

uint8_t Get_RobotMode(void) {
    return current_robot_mode;
}

void Process_By_Mode(void) {
    switch (current_robot_mode) {

        case MODE_TRACKING:
            if (is_first_entry) {
                Nav_Reset(imu_data.yaw_f);
                is_first_entry = 0;
            }
            Nav_DriveStraight(150, imu_data.yaw_f);
            break;

        case MODE_MANUAL:
            if (is_straight_requested) {
                if (is_first_entry) {
                    Nav_Reset(imu_data.yaw_f);
                    is_first_entry = 0;
                }
                Nav_DriveStraight(target_speed, imu_data.yaw_f);
            }
            else {
                is_first_entry = 1;
            }
            break;

        default:
            current_robot_mode = MODE_MANUAL;
            break;
    }
}
