#include "pms7003.h"
#include <string.h>
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "PMS7003";

esp_err_t em_pms7003_init(uart_port_t port, int tx_gpio, int rx_gpio, int baud)
{
    uart_config_t cfg = {
        .baud_rate = baud,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    // RX 버퍼만 설정 (TX는 센서로 보낼 일 거의 없음)
    ESP_ERROR_CHECK(uart_driver_install(port, 512, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(port, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(port, tx_gpio, rx_gpio, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    
    ESP_LOGI(TAG, "Initialized UART%d (TX:%d, RX:%d)", port, tx_gpio, rx_gpio);
    return ESP_OK;
}

esp_err_t em_pms7003_read(uart_port_t port, em_PmsData *out, uint32_t timeout_ms)
{
    if (!out) return ESP_ERR_INVALID_ARG;

    // 헤더(0x42, 0x4D) 찾기 로직 등 복잡한 파싱 대신,
    // 간단하게 32바이트 프레임을 읽어 검증합니다.
    
    uint8_t buffer[64];
    int len = uart_read_bytes(port, buffer, 32, pdMS_TO_TICKS(timeout_ms));
    
    if (len < 32) return ESP_ERR_TIMEOUT;

    // 헤더 검색
    int start_idx = -1;
    for (int i = 0; i < len - 1; i++) {
        if (buffer[i] == 0x42 && buffer[i+1] == 0x4D) {
            start_idx = i;
            break;
        }
    }

    if (start_idx == -1) {
        // 버퍼에 헤더가 없으면 플러시하고 리턴
        uart_flush_input(port);
        return ESP_ERR_INVALID_RESPONSE;
    }
    
    // 만약 헤더가 중간에 있었다면 나머지 바이트 더 읽기 (생략 가능하나 안정성 위해)
    // 여기서는 단순화를 위해 버퍼 정렬이 잘 맞다고 가정하거나 다음 주기를 기다림
    
    uint8_t *p = &buffer[start_idx];
    
    // 길이 체크
    uint16_t frame_len = ((uint16_t)p[2] << 8) | p[3];
    if (frame_len != 28) return ESP_ERR_INVALID_SIZE; // 고정 길이

    // 체크섬 계산
    uint16_t checksum = ((uint16_t)p[30] << 8) | p[31];
    uint16_t sum = 0;
    for (int i = 0; i < 30; i++) sum += p[i];

    if (sum != checksum) return ESP_ERR_INVALID_CRC;

    // 데이터 파싱
    out->pm1_0_cf1 = (p[4] << 8) | p[5];
    out->pm2_5_cf1 = (p[6] << 8) | p[7];
    out->pm10_cf1  = (p[8] << 8) | p[9];
    out->pm1_0_atm = (p[10] << 8) | p[11];
    out->pm2_5_atm = (p[12] << 8) | p[13];
    out->pm10_atm  = (p[14] << 8) | p[15];

    return ESP_OK;
}