/*
 * blt.h
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#ifndef INC_BLT_H_
#define INC_BLT_H_

#include "main.h"

#define BT_PACKET_SIZE  10
#define BT_START_BYTE   0xAA
#define BT_END_BYTE     0x55

extern volatile uint8_t bl_data;
extern volatile uint8_t bl_index;
extern volatile uint8_t is_straight_flag;
extern uint8_t bl_buffer[BT_PACKET_SIZE];

extern uint8_t robot_L_dir;
extern uint8_t robot_L_speed;
extern uint8_t robot_R_dir;
extern uint8_t robot_R_speed;

void BLT_Init(void);
void BLT_StartReceive(void);
void BLT_ProcessPacket(void);

#endif /* INC_BLT_H_ */
