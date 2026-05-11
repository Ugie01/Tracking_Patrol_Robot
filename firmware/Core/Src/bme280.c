#include "bme280.h"

// 필터 사용시 필요한 변수 정의
#define MA_SIZE 5
static float ma_buffer[MA_SIZE] = {0};
static int ma_index = 0;
static float lp_filtered = 0.0f;
static float alpha = 0.1f;

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
 * BME280 센서에서 온도 raw값을 읽어서 실제 온도로 변환
 */
void BME280_ReadData(BME280_Data *data) {
	uint8_t raw[3];
	HAL_I2C_Mem_Read(&hi2c1, 0x77 << 1, 0xFA, 1, raw, 3, 100);

	int32_t adc_T = ((int32_t)raw[0] << 12) | ((int32_t)raw[1] << 4) | (raw[2] >> 4);

	int32_t var1, var2, t_fine;
	var1 = ((((adc_T >> 3) - ((int32_t)dig_T1 << 1))) * ((int32_t)dig_T2)) >> 11;
	var2 = (((((adc_T >> 4) - ((int32_t)dig_T1)) * ((adc_T >> 4) - ((int32_t)dig_T1))) >> 12) * ((int32_t)dig_T3)) >> 14;
	t_fine = var1 + var2;

	float raw_tmp = (float)((t_fine * 5 + 128) >> 8) / 100.0f;

	data->temperature = BME280_Filter(raw_tmp);
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


void BME280_Init(void) {
	// 온도 x1 Normal 모드 설정
	uint8_t config_meas = 0x27;
	HAL_I2C_Mem_Write(&hi2c1, 0x77 << 1, 0xF4, 1, &config_meas, 1, 100);

	// 보정값 읽기
	BME280_ReadCalibration();
}
