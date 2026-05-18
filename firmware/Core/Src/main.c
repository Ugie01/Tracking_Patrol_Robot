/* USER CODE BEGIN Header */
/**
 ******************************************************************************
 * @file           : main.c
 * @brief          : Main program body
 ******************************************************************************
 * @attention
 *
 * Copyright (c) 2026 STMicroelectronics.
 * All rights reserved.
 *
 * This software is licensed under terms that can be found in the LICENSE file
 * in the root directory of this software component.
 * If no LICENSE file comes with this software, it is provided AS-IS.
 *
 ******************************************************************************
 */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "crc.h"
#include "dma.h"
#include "i2c.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "sensor_types.h"
#include "bme280.h"
#include "imu.h"
#include "blt.h"
#include "mode.h"
#include "motor.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
extern uint8_t is_straight_requested;
extern uint8_t target_speed;
extern uint8_t target_dir;

// raspi 통신
static char rpi_str_buf[20];
volatile uint8_t rpi_cmd = 0;
volatile uint8_t rpi_state = 0;
volatile uint8_t rpi_str_idx = 0;
volatile uint8_t rpi_rx_buf = 0;
volatile uint8_t rpi_data_ready = 0;

float yaw = 0.0f;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
void RPI_ProcessByte(uint8_t rx_data);
void Bluetooth_Send_Telemetry(UART_HandleTypeDef *huart, float target_angle, float current_yaw, uint8_t left_pwm, uint8_t right_pwm);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_TIM2_Init();
  MX_I2C1_Init();
  MX_USART2_UART_Init();
  MX_USART3_UART_Init();
  MX_USART1_UART_Init();
  MX_UART4_Init();
  MX_CRC_Init();
  MX_TIM4_Init();
  /* USER CODE BEGIN 2 */
	BME280_Init();
	IMU_Init();
	Motor_Init();
	BLT_Init();
	Motor_PID_Init(1.8f, 0.05f, 0.15f); // PID 튜닝위해 초기값 설정 Kp=2.0
	HAL_TIM_Base_Start_IT(&htim4);

	uint32_t last_time = 0;
	static float last_yaw = 0.0f;
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
	while (1) {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
		IMU_ReadData();
		BME280_Process();
		IMU_Process();
		yaw = imu_data.yaw_f;
		uint32_t time = HAL_GetTick();
		if(time - last_time >= 20){
			Process_By_Mode(yaw, last_yaw);

			last_time = time;
			last_yaw = yaw;
		}
		if (rpi_data_ready && current_robot_mode == MODE_TRACKING) {
		    char *str = rpi_str_buf + 1; // 't' 제외
		    // sscanf는 메인 루프에서 실행하여 인터럽트 지연 방지
		    sscanf(str, "%f,%hhu", &motor_pid.target_yaw, &rpi_stop_flag);
		    rpi_data_ready = 0;
		}
	}
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 4;
  RCC_OscInitStruct.PLL.PLLN = 168;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 4;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
	if (huart->Instance == USART3) {
//		IMU_Init();
	} else if (huart->Instance == UART4) {
		BLT_ProcessPacket();
	} else if (huart->Instance == USART1) {
		RPI_ProcessByte(rpi_rx_buf);
		HAL_UART_Receive_IT(&huart1, (uint8_t *)&rpi_rx_buf, 1);
	}
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim) {
	if (htim->Instance == TIM4) {

		// 직진 모드일 때만 PID 연산 및 누적 허용
		if (is_straight_flag) {
			motor_pid.error = Get_Diff();

			// 미세 진동 방지를 위한 데드존 설정
			if (fabsf(motor_pid.error) > 0.5f) {
				output_pid = Calculate_PID(motor_pid.error);
			} else {
				output_pid = 0.0f;
			}
		}
		else {
			// 적분 메모리는 비우되, 이전 오차를 현재 오차로 상시 동기화하여 진입 시 D항 폭발 차단
			motor_pid.integral = 0.0f;
			motor_pid.prev_error = Get_Diff();
			output_pid = 0.0f;
		}
	}
}

// 별도 함수로 분리하여 가독성 및 관리 효율 증대
void RPI_ProcessByte(uint8_t rx_data) {
    switch (rpi_state) {
        case 0:
            if (rx_data == 0xAA) rpi_state = 1;
            else if (rx_data == 't') {
                rpi_str_idx = 0;
                rpi_str_buf[rpi_str_idx++] = 't';
                rpi_state = 3;
            }
            break;
        case 1:
            rpi_cmd = rx_data;
            rpi_state = 2;
            break;
        case 2:
            if (rx_data == 0x55) {
                if (rpi_cmd == 0x0A) BME280_RxCallback();
                else if (rpi_cmd == 0x0B) IMU_RxCallback_RPI();
            }
            rpi_state = 0;
            break;
        case 3:
            if (rx_data == '\n') {
                rpi_str_buf[rpi_str_idx] = '\0';
                rpi_data_ready = 1;
                rpi_state = 0;
            } else {
                if (rpi_str_idx < sizeof(rpi_str_buf) - 1)
                    rpi_str_buf[rpi_str_idx++] = rx_data;
            }
            break;
    }
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
	/* User can add his own implementation to report the HAL error return state */
	__disable_irq();
	while (1) {
	}
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
