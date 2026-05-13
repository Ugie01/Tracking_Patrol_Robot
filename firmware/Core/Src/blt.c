/*
 * blt.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "blt.h"
#include "usart.h"
#include "mode.h"
#include "navigation.h"

uint8_t bl_data;
uint8_t bl_buffer[BT_PACKET_SIZE];
int bl_index = 0;

uint8_t target_speed = 0;
uint8_t target_dir = 0;
uint8_t is_straight_requested = 0;

extern PID_Navigation nav;
extern void Set_RobotMode(uint8_t mode);
extern void Move_Robot(uint8_t left_dir, uint8_t left_speed, uint8_t right_dir, uint8_t right_speed);

void BLT_Init(void) {
	bl_index = 0;
	BLT_StartReceive();
}

void BLT_StartReceive() {
	HAL_UART_Receive_IT(&huart4, &bl_data, 1);
}

void BLT_ProcessPacket(void) {
	if (bl_index == 0 && bl_data != BT_START_BYTE) {
		BLT_StartReceive();
		return;
	}

    bl_buffer[bl_index++] = bl_data;

    if (bl_index >= BT_PACKET_SIZE) {
        if (bl_buffer[BT_PACKET_SIZE - 1] == BT_END_BYTE) {

    	if (bl_buffer[0] == BT_START_BYTE && bl_buffer[9] == BT_END_BYTE) {

            uint8_t mode = bl_buffer[1];
            Set_RobotMode(mode);

            nav.Kp = (float)bl_buffer[6] * 0.1f;
			nav.Ki = (float)bl_buffer[7] * 0.01f;
			nav.Kd = (float)bl_buffer[8] * 0.1f;

            if (mode == MODE_MANUAL) {
                if (bl_buffer[2] == bl_buffer[4] && bl_buffer[3] == bl_buffer[5] && bl_buffer[3] > 0) {
                    is_straight_requested = 1;
                    target_dir = bl_buffer[2];
                    target_speed = bl_buffer[3];
                }
                else {

                }
                    is_straight_requested = 0;
                    // 직진이 아니면 즉시 모터 제어
                    Move_Robot(bl_buffer[2], bl_buffer[3], bl_buffer[4], bl_buffer[5]);
                }
            }
        }
        bl_index = 0;
    }
    BLT_StartReceive();
}
