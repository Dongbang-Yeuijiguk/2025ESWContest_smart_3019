#pragma once

#include <stdint.h>
#include "esp_err.h"
#include "driver/uart.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint16_t pm1_0_cf1;
    uint16_t pm2_5_cf1;
    uint16_t pm10_cf1;
    uint16_t pm1_0_atm; // 대기 환경 농도 (주로 사용)
    uint16_t pm2_5_atm; // PM2.5
    uint16_t pm10_atm;  // PM10
} em_PmsData;

/**
 * @brief PMS7003 UART 초기화
 */
esp_err_t em_pms7003_init(uart_port_t port, int tx_gpio, int rx_gpio, int baud);

/**
 * @brief 데이터 읽기 (Blocking, 타임아웃 적용)
 */
esp_err_t em_pms7003_read(uart_port_t port, em_PmsData *out, uint32_t timeout_ms);

#ifdef __cplusplus
}
#endif