/*
 * motor.c
 *
 *  Created on: May 11, 2026
 *      Author: KCCISTC
 */

#include "motor.h"
#include "tim.h"
#include <stdlib.h>

extern TIM_HandleTypeDef htim2;


void Motor_Init(void) {
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1); // 왼쪽 모터
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2); // 오른쪽 모터
}

void Move_Robot(uint8_t left_dir, uint8_t left_speed, uint8_t right_dir, uint8_t right_speed) {

    if(left_dir == DIR_FORWARD) {
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_0, GPIO_PIN_SET);
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_1, GPIO_PIN_RESET);
    } else {
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_0, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_1, GPIO_PIN_SET);
    }

    if(right_dir == DIR_FORWARD) {
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_2, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_3, GPIO_PIN_SET);
    } else {
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_2, GPIO_PIN_SET);
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_3, GPIO_PIN_RESET);
    }

    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, left_speed);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, right_speed);
}

void Stop_Robot(void) {
    Move_Robot(0, 0, 0, 0);
}

//void Motor_SetSpeed(int16_t left, int16_t right) {
//    uint8_t l_dir = (left >= 0) ? DIR_FORWARD : DIR_BACKWARD;
//    uint8_t r_dir = (right >= 0) ? DIR_FORWARD : DIR_BACKWARD;
//
//    uint16_t l_spd = abs(left);
//    uint16_t r_spd = abs(right);
//
//    if (l_spd > MOTOR_MAX_SPEED) l_spd = MOTOR_MAX_SPEED;
//    if (r_spd > MOTOR_MAX_SPEED) r_spd = MOTOR_MAX_SPEED;
//
//    Move_Robot(l_dir, (uint8_t)l_spd, r_dir, (uint8_t)r_spd);
//}
