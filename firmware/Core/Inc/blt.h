/*
 * blt.h
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#ifndef INC_BLT_H_
#define INC_BLT_H_

#include "main.h"

#define BT_PACKET_SIZE  7
#define BT_START_BYTE   0xAA
#define BT_END_BYTE     0x55

extern uint8_t bl_data;

void BLT_Init(void);
void BLT_StartReceive(void);
void BLT_ProcessPacket(void);

#endif /* INC_BLT_H_ */
