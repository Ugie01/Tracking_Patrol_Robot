/*
 * mode.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "mode.h"
#include "motor.h"
#include "sensor_types.h"

extern BME280_Data bme_data;
extern IMU_Data imu_data;

static uint8_t current_robot_mode = MODE_MANUAL;

void Set_RobotMode(uint8_t mode) {
    current_robot_mode = mode;
}

uint8_t Get_RobotMode(void) {
    return current_robot_mode;
}

void Process_By_Mode(void) {
    switch (current_robot_mode) {

        case MODE_TRACKING:
            break;

        case MODE_MANUAL:
            break;

        default:
            current_robot_mode = MODE_MANUAL;
            break;
    }
}
