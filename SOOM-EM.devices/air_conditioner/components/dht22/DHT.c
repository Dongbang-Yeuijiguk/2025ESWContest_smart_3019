#include "DHT.h"
#include <string.h>
#include "esp_log.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"   // esp_rom_delay_us()

static const char *TAG = "DHT";

static gpio_num_t s_dht_gpio = GPIO_NUM_NC;
static float      s_hum = 0.0f;
static float      s_tmp = 0.0f;

// ===== 유틸 =====
static inline void delay_us(uint32_t us)
{
    // IDF에서 제공하는 ROM 딜레이(바쁜대기)
    esp_rom_delay_us(us);
}

// level이 desired(0/1)가 될 때까지 대기, 최대 timeout_us
// 성공 시 경과 시간(마이크로초), 타임아웃 시 음수
static int32_t wait_for_level(int desired_level, uint32_t timeout_us)
{
    int level = gpio_get_level(s_dht_gpio);
    int64_t start = esp_timer_get_time();

    while (level != desired_level) {
        if ((uint32_t)(esp_timer_get_time() - start) > timeout_us) {
            return -1;
        }
        level = gpio_get_level(s_dht_gpio);
    }

    // 이제 desired_level이 된 시점부터 얼마나 유지되는지 측정
    start = esp_timer_get_time();
    while (level == desired_level) {
        if ((uint32_t)(esp_timer_get_time() - start) > timeout_us) {
            // 유지시간이 timeout보다 길면 timeout 처리하지만,
            // 상한만 잘라내고 경과값을 리턴하도록 하자.
            return (int32_t)timeout_us;
        }
        level = gpio_get_level(s_dht_gpio);
    }
    return (int32_t)(esp_timer_get_time() - start);
}

// ===== 공개 API =====

void setDHTgpio(gpio_num_t gpio)
{
    s_dht_gpio = gpio;

    // 기본은 풀업 입력(외부 10k 풀업 권장)
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << s_dht_gpio,
        .mode = GPIO_MODE_INPUT_OUTPUT_OD, // 오픈드레인
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config(&io);

    // 라인을 High로 풀어두기
    gpio_set_level(s_dht_gpio, 1);
    delay_us(10);
}

int readDHT(void)
{
    if (s_dht_gpio == GPIO_NUM_NC) {
        ESP_LOGE(TAG, "GPIO not set. Call setDHTgpio() first.");
        return DHT_BUS_HUNG;
    }

    uint8_t data[5] = {0};

    // === 시작 시퀀스 ===
    // 1) 라인을 Low로 1~2ms 끌어내려 Start 신호
    gpio_set_level(s_dht_gpio, 0);
    delay_us(1800); // 1.8ms (안정적으로 넉넉히)

    // 2) 라인 High (오픈드레인 해제)
    gpio_set_level(s_dht_gpio, 1);
    delay_us(30);   // 20~40us 정도

    // 3) 이제 센서의 응답을 기다리며 입력 읽기
    // 응답: LOW ~80us -> HIGH ~80us
    if (wait_for_level(0, 100) < 0) { // 센서가 먼저 LOW로 내려와야 함
        ESP_LOGE(TAG, "No response (LOW) from sensor");
        return DHT_TIMEOUT_ERROR;
    }
    if (wait_for_level(1, 100) < 0) { // 이후 HIGH이어야 함
        ESP_LOGE(TAG, "No response (HIGH) from sensor");
        return DHT_TIMEOUT_ERROR;
    }

    // === 40비트 읽기 ===
    // 각 비트: LOW ~50us 후 HIGH가 26~28us(0) 또는 ~70us(1)
    for (int i = 0; i < 40; i++) {
        // LOW 구간(~50us)
        if (wait_for_level(0, 100) < 0) {
            ESP_LOGE(TAG, "Timeout waiting for bit %d LOW", i);
            return DHT_TIMEOUT_ERROR;
        }
        // HIGH 길이 측정
        int32_t t_high = wait_for_level(1, 100);
        if (t_high < 0) {
            ESP_LOGE(TAG, "Timeout waiting for bit %d HIGH", i);
            return DHT_TIMEOUT_ERROR;
        }

        // 하이 펄스 길이로 0/1 판정 기준(임계값 40us)
        uint8_t bit = (t_high > 40) ? 1 : 0;

        data[i / 8] <<= 1;
        data[i / 8] |= bit;
    }

    // === 체크섬 ===
    uint8_t sum = (uint8_t)(data[0] + data[1] + data[2] + data[3]);
    if (sum != data[4]) {
        ESP_LOGE(TAG, "Checksum error: calc=%u recv=%u", sum, data[4]);
        return DHT_CHECKSUM_ERROR;
    }

    // === 데이터 해석 ===
    // DHT22:
    //  - 습도: 16비트 (0.1% 단위)
    //  - 온도: 16비트 (부호비트 포함, 0.1°C 단위)
    uint16_t raw_hum = ((uint16_t)data[0] << 8) | data[1];
    uint16_t raw_tmp = ((uint16_t)data[2] << 8) | data[3];

    float hum = raw_hum / 10.0f;
    float tmp;

    if (raw_tmp & 0x8000) { // 음수
        raw_tmp &= 0x7FFF;
        tmp = -(raw_tmp / 10.0f);
    } else {
        tmp = raw_tmp / 10.0f;
    }

    // 값 저장
    s_hum = hum;
    s_tmp = tmp;

    // 라인 정리: 풀업 상태 유지
    gpio_set_level(s_dht_gpio, 1);

    return DHT_OK;
}

float getHumidity(void)
{
    return s_hum;
}

float getTemperature(void)
{
    return s_tmp;
}

void errorHandler(int response)
{
    switch (response) {
    case DHT_OK:
        //ESP_LOGI(TAG, "DHT read OK");
        break;
    case DHT_TIMEOUT_ERROR:
        ESP_LOGW(TAG, "DHT timeout");
        break;
    case DHT_CHECKSUM_ERROR:
        ESP_LOGW(TAG, "DHT checksum error");
        break;
    case DHT_BUS_HUNG:
        ESP_LOGW(TAG, "DHT bus hung or GPIO not set");
        break;
    default:
        ESP_LOGW(TAG, "DHT unknown error: %d", response);
        break;
    }
}
