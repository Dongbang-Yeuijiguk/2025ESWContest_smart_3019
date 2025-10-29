#pragma once

/* WHY: PMS7003 센서 UART 프레임 파싱과 초기화를 캡슐화하여
 *      앱(main)에서 간단히 호출 가능하도록 모듈화.
 *      프로젝트 규칙: em_ 접두사는 예시로 남김.
 */

#include <stdbool.h>
#include <stdint.h>
#include "driver/uart.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint16_t pm1_0_cf1;    // CF=1, std dust (μg/m3)
    uint16_t pm2_5_cf1;
    uint16_t pm10_cf1;
    uint16_t pm1_0_atm;    // atmospheric environment (μg/m3)
    uint16_t pm2_5_atm;
    uint16_t pm10_atm;
} em_PmsData;

/* WHY: 드라이버 초기화 분리. 핀/포트/baud를 주입하여 하드웨어 의존성 낮춤. */
esp_err_t em_pms7003_init(uart_port_t port, int tx_gpio, int rx_gpio, int baud);

/* WHY: 블로킹 읽기 API. 타임아웃 내 유효 프레임 수신 시 파싱하여 반환. */
esp_err_t em_pms7003_read(uart_port_t port, em_PmsData *out, uint32_t timeout_ms);

/* WHY: 연속 로깅 테스크(옵션). 주기적으로 읽어서 로그로 뿌림. */
void em_pms7003_task(void *arg);

#ifdef __cplusplus
}
#endif
