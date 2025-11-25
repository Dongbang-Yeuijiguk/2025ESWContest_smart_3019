#include <stdio.h>
#include <string.h>
#include <math.h>
#include "air_conditioner_main.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include "nvs_flash.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "mqtt_client.h"
#include "cJSON.h"

#include "driver/ledc.h" 
#include "DHT.h"

static const char *TAG = "air_conditioner";

/* -------------------- 구조체 정의 -------------------- */

// 에어컨 모드 열거형
typedef enum {
    AC_MODE_OFF = 0,
    AC_MODE_LOW,
    AC_MODE_MID,
    AC_MODE_HIGH
} ac_mode_t;

// 에어컨 상태 구조체
typedef struct {
    bool power_on;
    ac_mode_t mode;
    float target_temp;
    float target_hum;
    
    // 센서 측정값 (리포트용)
    float current_temp;
    float current_hum;
} ac_state_t;

// Queue 명령 메시지
typedef struct {
    bool update_power;
    bool power_val;

    bool update_mode;
    ac_mode_t mode_val;

    bool update_target;
    float temp_val;
    float hum_val;
} ac_cmd_t;

/* -------------------- 전역 변수 -------------------- */
static esp_mqtt_client_handle_t s_mqtt = NULL;
static QueueHandle_t s_ac_queue = NULL;

static ac_state_t s_state = {
    .power_on = false,
    .mode = AC_MODE_LOW,
    .target_temp = DEFAULT_TARGET_TEMP,
    .target_hum = DEFAULT_TARGET_HUM,
    .current_temp = 0.0f,
    .current_hum = 0.0f
};

/* -------------------- Hardware Init -------------------- */

static void hw_init_motor_relay(void) {
    // 1. Relay & Direction Pin
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << RELAY_GPIO) | (1ULL << MOTOR_A1B_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = 0,
        .pull_down_en = 0,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config(&io_conf);
    gpio_set_level(RELAY_GPIO, 0); // 초기 OFF
    gpio_set_level(MOTOR_A1B_GPIO, 0); // 방향 초기화

    // 2. PWM (Speed Pin)
    ledc_timer_config_t ledc_timer = {
        .speed_mode       = FAN_LEDC_MODE,
        .timer_num        = FAN_LEDC_TIMER,
        .duty_resolution  = FAN_LEDC_DUTY_RES,
        .freq_hz          = FAN_LEDC_FREQUENCY,
        .clk_cfg          = LEDC_AUTO_CLK
    };
    ESP_ERROR_CHECK(ledc_timer_config(&ledc_timer));

    ledc_channel_config_t ledc_channel = {
        .speed_mode     = FAN_LEDC_MODE,
        .channel        = FAN_LEDC_CHANNEL,
        .timer_sel      = FAN_LEDC_TIMER,
        .intr_type      = LEDC_INTR_DISABLE,
        .gpio_num       = FAN_LEDC_OUTPUT_IO,
        .duty           = 0,
        .hpoint         = 0
    };
    ESP_ERROR_CHECK(ledc_channel_config(&ledc_channel));
}

/* -------------------- Helper Functions -------------------- */

static ac_mode_t str_to_mode(const char* s) {
    if (!s) return AC_MODE_LOW;
    if (!strcasecmp(s, "low")) return AC_MODE_LOW;
    if (!strcasecmp(s, "mid")) return AC_MODE_MID;
    if (!strcasecmp(s, "high")) return AC_MODE_HIGH;
    return AC_MODE_LOW;
}

static const char* mode_to_str(ac_mode_t m) {
    switch (m) {
        case AC_MODE_LOW: return "low";
        case AC_MODE_MID: return "mid";
        case AC_MODE_HIGH: return "high";
        default: return "off";
    }
}

static void apply_ac_hardware(const ac_state_t* s) {
    if (s->power_on) {
        // 1. Relay ON
        gpio_set_level(RELAY_GPIO, 1);
        
        // 2. Motor Speed (PWM)
        uint32_t duty = 0;
        switch (s->mode) {
            case AC_MODE_LOW:  duty = 80;  break; // ~30%
            case AC_MODE_MID:  duty = 160; break; // ~60%
            case AC_MODE_HIGH: duty = 255; break; // 100%
            default: duty = 80; break;
        }
        
        // 방향 설정 (정방향)
        gpio_set_level(MOTOR_A1B_GPIO, 0);
        ledc_set_duty(FAN_LEDC_MODE, FAN_LEDC_CHANNEL, duty);
        ledc_update_duty(FAN_LEDC_MODE, FAN_LEDC_CHANNEL);

        ESP_LOGI(TAG, "AC ON: Mode=%s, Duty=%lu", mode_to_str(s->mode), duty);

    } else {
        // Power OFF
        gpio_set_level(RELAY_GPIO, 0);
        ledc_set_duty(FAN_LEDC_MODE, FAN_LEDC_CHANNEL, 0);
        ledc_update_duty(FAN_LEDC_MODE, FAN_LEDC_CHANNEL);
        ESP_LOGI(TAG, "AC OFF");
    }
}

/* -------------------- MQTT Publish -------------------- */

static void publish_status(void) {
    if (!s_mqtt) return;

    cJSON* root = cJSON_CreateObject();
    
    // 상태 정보
    cJSON_AddStringToObject(root, "power", s_state.power_on ? "on" : "off");
    cJSON_AddStringToObject(root, "mode", mode_to_str(s_state.mode));
    
    // 목표값
    cJSON_AddNumberToObject(root, "target_temp", s_state.target_temp);
    cJSON_AddNumberToObject(root, "target_hum", s_state.target_hum);

    // 센서 측정값 (반올림 처리)
    char buf[16];
    snprintf(buf, sizeof(buf), "%.1f", s_state.current_temp);
    cJSON_AddStringToObject(root, "temperature", buf);
    
    snprintf(buf, sizeof(buf), "%.1f", s_state.current_hum);
    cJSON_AddStringToObject(root, "humidity", buf);

    char* out = cJSON_PrintUnformatted(root);
    if (out) {
        esp_mqtt_client_publish(s_mqtt, MQTT_TOPIC_SENSOR, out, 0, 1, 0);
        ESP_LOGI(TAG, "Published: %s", out);
        cJSON_free(out);
    }
    cJSON_Delete(root);
}

/* -------------------- Tasks -------------------- */

// 1. 제어 태스크 (MQTT 명령 처리)
static void ac_control_task(void *pvParameters) {
    ac_cmd_t cmd;
    while (1) {
        if (xQueueReceive(s_ac_queue, &cmd, portMAX_DELAY)) {
            bool changed = false;

            if (cmd.update_power) {
                if (s_state.power_on != cmd.power_val) {
                    s_state.power_on = cmd.power_val;
                    changed = true;
                }
            }

            if (cmd.update_mode) {
                if (s_state.mode != cmd.mode_val) {
                    s_state.mode = cmd.mode_val;
                    changed = true;
                }
            }

            if (cmd.update_target) {
                s_state.target_temp = cmd.temp_val;
                s_state.target_hum = cmd.hum_val;
                // 목표값 변경은 하드웨어 즉시 반영보다는 로직에 쓰임
                // 여기서는 단순히 상태 업데이트로 간주
                changed = true; 
            }

            if (changed) {
                apply_ac_hardware(&s_state);
                publish_status();
            }
        }
    }
}

// 2. 센서 태스크 (주기적 측정 & 리포트)
static void dht_sensor_task(void *arg) {
    setDHTgpio(DHT_GPIO); 

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(5000)); // 5초 주기

        int ret = readDHT();
        errorHandler(ret);
        float hum = getHumidity();
        float temp = getTemperature();

        // 유효성 검사
        if (hum > 0 && temp > -100) {
             // 반올림
            temp = roundf(temp * 10.0f) / 10.0f;
            hum = roundf(hum * 10.0f) / 10.0f;

            // 상태 업데이트 (Mutex 없이 단순 대입. 필요 시 Mutex 추가)
            s_state.current_temp = temp;
            s_state.current_hum = hum;

            // 주기적 리포트
            publish_status();
        }
    }
}

/* -------------------- MQTT Handler -------------------- */

static void mqtt_on_data(esp_mqtt_event_handle_t event) {
    if (!event->topic || event->topic_len <= 0) return;
    if (strncmp(event->topic, MQTT_TOPIC_CMD, event->topic_len) != 0) return;

    char *payload = (char *)malloc(event->data_len + 1);
    if (!payload) return;
    memcpy(payload, event->data, event->data_len);
    payload[event->data_len] = '\0';

    cJSON *root = cJSON_Parse(payload);
    if (root) {
        ac_cmd_t cmd = {0};
        bool valid = false;

        // 1. Power
        cJSON *j_power = cJSON_GetObjectItemCaseSensitive(root, "ac_power");
        if (cJSON_IsString(j_power) && j_power->valuestring) {
            cmd.update_power = true;
            cmd.power_val = (strcasecmp(j_power->valuestring, "on") == 0);
            valid = true;
        }

        // 2. Mode
        cJSON *j_mode = cJSON_GetObjectItemCaseSensitive(root, "target_ac_mode");
        if (cJSON_IsString(j_mode) && j_mode->valuestring) {
            cmd.update_mode = true;
            cmd.mode_val = str_to_mode(j_mode->valuestring);
            valid = true;
        }

        // 3. Target Temp/Hum
        cJSON *j_temp = cJSON_GetObjectItemCaseSensitive(root, "target_ac_temperature");
        cJSON *j_hum = cJSON_GetObjectItemCaseSensitive(root, "target_ac_humidity");
        
        if (cJSON_IsNumber(j_temp)) {
            cmd.update_target = true;
            cmd.temp_val = (float)j_temp->valuedouble;
            valid = true;
        } else {
             cmd.temp_val = s_state.target_temp; // 유지
        }

        if (cJSON_IsNumber(j_hum)) {
            cmd.update_target = true;
            cmd.hum_val = (float)j_hum->valuedouble;
            valid = true;
        } else {
             cmd.hum_val = s_state.target_hum; // 유지
        }

        if (valid) {
            xQueueSend(s_ac_queue, &cmd, 0);
        }
        cJSON_Delete(root);
    }
    free(payload);
}

static void mqtt_event_handler(void *arg, esp_event_base_t base, int32_t eid, void *edata) {
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)edata;
    switch (event->event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "MQTT Connected");
            esp_mqtt_client_subscribe(s_mqtt, MQTT_TOPIC_CMD, 1);
            publish_status();
            break;
        case MQTT_EVENT_DATA:
            mqtt_on_data(event);
            break;
        default: break;
    }
}

/* -------------------- Wi-Fi -------------------- */

static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                               int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } 
    else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "Wi-Fi disconnected. Retrying...");
        esp_wifi_connect();
    } 
    else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
    }
}

static void wifi_start(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, NULL));

    wifi_config_t wifi_config = {0};
    strncpy((char *)wifi_config.sta.ssid, WIFI_SSID, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, WIFI_PASSWORD, sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
}

/* -------------------- app_main -------------------- */

void app_main(void) {
    // 1. NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 2. Queue
    s_ac_queue = xQueueCreate(5, sizeof(ac_cmd_t));

    // 3. Hardware
    hw_init_motor_relay();

    // DHT 라이브러리 초기화
    setDHTgpio(DHT_GPIO);

    // 4. Tasks
    // 제어 태스크 (높은 우선순위)
    xTaskCreate(ac_control_task, "ac_ctrl", 4096, NULL, 5, NULL);
    // 센서 태스크 (낮은 우선순위)
    xTaskCreate(dht_sensor_task, "ac_dht", 4096, NULL, 3, NULL);

    // 5. Wi-Fi
    wifi_start();

    // 6. MQTT
    esp_mqtt_client_config_t mcfg = {
        .broker.address.uri = MQTT_BROKER_URI,
    };
    s_mqtt = esp_mqtt_client_init(&mcfg);
    esp_mqtt_client_register_event(s_mqtt, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_mqtt));

    ESP_LOGI(TAG, "Smart AC System Started.");
}