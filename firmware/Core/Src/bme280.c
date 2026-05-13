#include "bme280.h"

// 필터 사용시 필요한 변수 정의
#define MA_SIZE 5
static float ma_buffer[MA_SIZE] = {0};
static int ma_index = 0;
static float lp_filtered = 0.0f;
static float alpha = 0.1f;



static volatile uint8_t bme_request_flag = 0;
volatile uint8_t rpi_rx_buf;

// 데이터 보정값
uint16_t dig_T1;
int16_t  dig_T2, dig_T3;

void BME280_ReadCalibration(void) {
	uint8_t calib[6];
	HAL_I2C_Mem_Read(&hi2c1, 0x77 << 1, 0x88, 1, calib, 6, 100);

	dig_T1 = (calib[1] << 8) | calib[0];
	dig_T2 = (calib[3] << 8) | calib[2];
	dig_T3 = (calib[5] << 8) | calib[4];
}

/*
 * BME280 센서에서 온도 raw값을 읽어서 필터링 적용
 */
void BME280_Process(void) {
	if (!bme_request_flag) return;
	bme_request_flag = 0;

	uint8_t raw[3];
	HAL_I2C_Mem_Read(&hi2c1, 0x77 << 1, 0xFA, 1, raw, 3, 100);

	int32_t adc_T = ((int32_t)raw[0] << 12) | ((int32_t)raw[1] << 4) | (raw[2] >> 4);
	      int32_t var1 = ((((adc_T >> 3) - ((int32_t)dig_T1 << 1))) * ((int32_t)dig_T2)) >> 11;
	      int32_t var2 = (((((adc_T >> 4) - ((int32_t)dig_T1)) * ((adc_T >> 4) - ((int32_t)dig_T1))) >> 12) *
	  ((int32_t)dig_T3)) >> 14;
	      float temp = (float)(((var1 + var2) * 5 + 128) >> 8) / 100.0f;


	char buf[16];
	snprintf(buf, sizeof(buf), "%.2f\n", temp);
	HAL_UART_Transmit(&huart1, (uint8_t*)buf, strlen(buf), 100);
}

/*
 * 필터 적용 -> 이동 평균 필터 / 저역 통과 필터
 */
float BME280_Filter(float new_temp) {
	// 이동 평균 필터 적용
    ma_buffer[ma_index % MA_SIZE] = new_temp;
    ma_index++;
    float sum = 0;
    for(int i = 0; i < MA_SIZE; i++) sum += ma_buffer[i];
    float ma_result = sum / MA_SIZE;

    // 저역 통과 필터 적용
    lp_filtered = alpha * ma_result + (1 - alpha) * lp_filtered;

    return lp_filtered;
}

void BME280_RxCallback(void) {
	bme_request_flag = 1;
}


void BME280_Init(void) {
	// 온도 x1 Normal 모드 설정
	uint8_t config_meas = 0x27;
	HAL_I2C_Mem_Write(&hi2c1, 0x77 << 1, 0xF4, 1, &config_meas, 1, 100);

	// 보정값

	BME280_ReadCalibration();

	// 수신읽기
	HAL_UART_Receive_IT(&huart1, (uint8_t*)&rpi_rx_buf, 1);
}
