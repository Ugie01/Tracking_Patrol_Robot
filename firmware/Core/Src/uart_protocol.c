#include "uart_protocol.h"

// 체크섬 계산
uint8_t UART_CalcChecksum(uint8_t *data, uint16_t len) {
    uint8_t sum = 0;
    for (int i = 0; i < len; i++) {
        sum += data[i];
    }
    return sum;
}

// 패킷 전송
void UART_SendPacket(UART_HandleTypeDef *huart, SensorPacket *packet) {
    uint8_t header[2] = {0xAA, 0xBB};
    uint8_t length    = sizeof(SensorPacket);
    uint8_t checksum  = UART_CalcChecksum((uint8_t*)packet, length);
    uint8_t end       = 0xEE;

    HAL_UART_Transmit(huart, header,           2,      100);
    HAL_UART_Transmit(huart, &length,          1,      100);
    HAL_UART_Transmit(huart, (uint8_t*)packet, length, 100);
    HAL_UART_Transmit(huart, &checksum,        1,      100);
    HAL_UART_Transmit(huart, &end,             1,      100);
}
