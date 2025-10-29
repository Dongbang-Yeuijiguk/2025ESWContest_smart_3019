#include "pms7003.h"

#include <string.h>

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_rom_crc.h"
#include "esp_timer.h"

#define PMS_FRAME_HEADER_H     0x42
#define PMS_FRAME_HEADER_L     0x4D
#define PMS_FRAME_LEN_BYTES    32
#define PMS_TOTAL_BYTES        (2 + 2 + PMS_FRAME_LEN_BYTES + 2)

#define PMS_UART_RX_BUF        512
#define PMS_UART_TX_BUF        0

static const char *TAG = "pms7003";

static uint16_t s_checksum_sum(const uint8_t *buf, int n)
{
    uint32_t sum = 0;
    for (int i = 0; i < n; ++i) sum += buf[i];
    return (uint16_t)sum;
}

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

    ESP_ERROR_CHECK(uart_driver_install(port, PMS_UART_RX_BUF, PMS_UART_TX_BUF, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(port, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(port, tx_gpio, rx_gpio, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    return ESP_OK;
}

esp_err_t em_pms7003_read(uart_port_t port, em_PmsData *out, uint32_t timeout_ms)
{
    if (!out) return ESP_ERR_INVALID_ARG;

    int64_t t_end = esp_timer_get_time() + (int64_t)timeout_ms * 1000;

    uint8_t b = 0;
    bool got_42 = false;
    while (esp_timer_get_time() < t_end) {
        int n = uart_read_bytes(port, &b, 1, pdMS_TO_TICKS(10));
        if (n == 1) {
            if (!got_42) {
                got_42 = (b == 0x42);
            } else {
                if (b == 0x4D) break;
                got_42 = (b == 0x42);
            }
        }
    }
    if (!got_42) return ESP_ERR_TIMEOUT;

uint8_t len_bytes[2];
int got = 0;
while (got < 2 && esp_timer_get_time() < t_end) {
    int n = uart_read_bytes(port, len_bytes + got, 2 - got, pdMS_TO_TICKS(10));
    if (n > 0) got += n;
}
if (got < 2) return ESP_ERR_TIMEOUT;

uint16_t len = ((uint16_t)len_bytes[0] << 8) | len_bytes[1];

if (len < 10 || len > 40) {
    ESP_LOGW("pms7003", "Unexpected length=%u", (unsigned)len);
    return ESP_ERR_INVALID_RESPONSE;
}

const int tail_need = len;
uint8_t tail[64];
if (tail_need > (int)sizeof(tail)) return ESP_ERR_NO_MEM;

got = 0;
while (got < tail_need && esp_timer_get_time() < t_end) {
    int n = uart_read_bytes(port, tail + got, tail_need - got, pdMS_TO_TICKS(20));
    if (n > 0) got += n;
}
if (got < tail_need) return ESP_ERR_TIMEOUT;

uint16_t rx_ck = ((uint16_t)tail[len - 2] << 8) | tail[len - 1];

uint32_t sum = 0;
sum += 0x42; sum += 0x4D;
sum += len_bytes[0]; sum += len_bytes[1];
for (int i = 0; i < len - 2; ++i) sum += tail[i];
uint16_t calc_ck = (uint16_t)sum;

if (calc_ck != rx_ck) {
    ESP_LOGW("pms7003", "Checksum mismatch calc=0x%04x rx=0x%04x", calc_ck, rx_ck);
    return ESP_ERR_INVALID_CRC;
}

const uint8_t *p = tail;
em_PmsData d = {0};
d.pm1_0_cf1  = ((uint16_t)p[0] << 8)  | p[1];
d.pm2_5_cf1  = ((uint16_t)p[2] << 8)  | p[3];
d.pm10_cf1   = ((uint16_t)p[4] << 8)  | p[5];
d.pm1_0_atm  = ((uint16_t)p[6] << 8)  | p[7];
d.pm2_5_atm  = ((uint16_t)p[8] << 8)  | p[9];
d.pm10_atm   = ((uint16_t)p[10] << 8) | p[11];

*out = d;
return ESP_OK;

}


void em_pms7003_task(void *arg)
{
    uart_port_t port = (uart_port_t)(intptr_t)arg;
    em_PmsData d;
    while (1) {
        esp_err_t r = em_pms7003_read(port, &d, 1500);
        if (r == ESP_OK) {
            ESP_LOGI(TAG,
                     "PM(atm) μg/m3 — PM1.0:%u  PM2.5:%u  PM10:%u | (CF1) %u/%u/%u",
                     d.pm1_0_atm, d.pm2_5_atm, d.pm10_atm,
                     d.pm1_0_cf1, d.pm2_5_cf1, d.pm10_cf1);
        } else if (r == ESP_ERR_TIMEOUT) {
            ESP_LOGW(TAG, "Read timeout (no frame)");
        } else {
            ESP_LOGE(TAG, "Read error: %s", esp_err_to_name(r));
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
