/*
 * blt.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "blt.h"

volatile uint8_t bl_data = 0;
volatile uint8_t bl_index = 0;
volatile uint8_t is_straight_flag = 0;
uint8_t bl_buffer[BT_PACKET_SIZE] = { };

uint8_t robot_L_dir = 0;
uint8_t robot_L_speed = 0;
uint8_t robot_R_dir = 0;
uint8_t robot_R_speed = 0;

extern MotorPID_t motor_pid;
extern void Set_RobotMode(uint8_t mode);

void BLT_Init(void) {
	BLT_StartReceive();
}

void BLT_StartReceive() {
	HAL_UART_Receive_IT(&huart4, (uint8_t*) &bl_data, 1);
}

void BLT_ProcessPacket(void) {
	if (bl_index == 0 && bl_data != BT_START_BYTE) {
		BLT_StartReceive();
		return;
	}

	bl_buffer[bl_index++] = bl_data;

	if (bl_index >= BT_PACKET_SIZE) {
		if (bl_buffer[0] == BT_START_BYTE
				&& bl_buffer[BT_PACKET_SIZE - 1] == BT_END_BYTE) {
			uint8_t mode = bl_buffer[1];
			Set_RobotMode(mode);

			if (mode == MODE_MANUAL) {
				// 전진 또는 후진하는 상황 (전진: 0, 0, Left Speed, 0, Right Speed, P, I, D)
				if (bl_buffer[2] == bl_buffer[4] && bl_buffer[3] == bl_buffer[5]
						&& bl_buffer[3] > 0) {
					is_straight_flag = 1;
				}
				// 좌회전하는 상황 0, 1, Left Speed, 0 Right Speed, P, I, D
				// 우회전하는 상황 0, 0, Left Speed, 1 Right Speed, P, I, D
				// 뒤는 1, 앞은 0
				else {
					is_straight_flag = 0;
				}
			}

			robot_L_dir = bl_buffer[2];
			robot_L_speed = bl_buffer[3];
			robot_R_dir = bl_buffer[4];
			robot_R_speed = bl_buffer[5];

			Motor_PID_UpdateGain((float) bl_buffer[6], (float) bl_buffer[7], (float) bl_buffer[8]);
		}
		bl_index = 0;
	}

	BLT_StartReceive();
}
