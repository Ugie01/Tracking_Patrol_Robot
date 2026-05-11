/*
 * blt.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "blt.h"
#include "usart.h"
#include "mode.h"

uint8_t bl_data;
uint8_t bl_buffer[BT_PACKET_SIZE];
int bl_index = 0;

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
    bl_buffer[bl_index++] = bl_data;

    if (bl_index >= BT_PACKET_SIZE) {
        // [0]AA [1]모드 [2]L방향 [3]L속도 [4]R방향 [5]R속도 [6]55
        if (bl_buffer[0] == BT_START_BYTE && bl_buffer[6] == BT_END_BYTE) {

            Set_RobotMode(bl_buffer[1]);

            if (bl_buffer[1] == MODE_MANUAL) {
                Move_Robot(bl_buffer[2], bl_buffer[3], bl_buffer[4], bl_buffer[5]);
            }
        }
        bl_index = 0;
    }
    BLT_StartReceive();
}
