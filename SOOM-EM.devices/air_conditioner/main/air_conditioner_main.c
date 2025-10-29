#include <stdio.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "cJSON.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_sntp.h"
#include "dht.h"

static const char *TAG = "SOOM_AC";

#include "sdkconfig.h"   // ← Kconfig 값 불러오기

/* -------------------- 핀 설정 -------------------- */
#define MOTOR_A1A CONFIG_MOTOR_A1A
#define MOTOR_A1B CONFIG_MOTOR_A1B
#define RELAY_GPIO CONFIG_RELAY_GPIO
#define DHT_GPIO CONFIG_DHT_GPIO

/* -------------------- MQTT 설정 -------------------- */
#define MQTT_URI CONFIG_MQTT_URI
#define MQTT_TOPIC_SENSOR CONFIG_MQTT_TOPIC_SENSOR
#define MQTT_TOPIC_CMD CONFIG_MQTT_TOPIC_CMD

/* -------------------- 글로벌 변수 -------------------- */
static esp_mqtt_client_handle_t mqtt_client = NULL;
static float target_temp = 25.0, target_hum = 50.0;
static char target_mode[10] = "low";
static bool ac_power = false;

/* -------------------- PWM 설정 -------------------- */
#define PWM_CHANNEL       LEDC_CHANNEL_0
#define PWM_TIMER         LEDC_TIMER_0
#define PWM_MODE          LEDC_LOW_SPEED_MODE
#define PWM_DUTY_RES      LEDC_TIMER_8_BIT  // 0~255
#define PWM_FREQ_HZ       5000              // 5kHz

static void motor_init(void) {
    // 방향핀 설정
    gpio_set_direction(MOTOR_A1A, GPIO_MODE_OUTPUT);
    gpio_set_direction(MOTOR_A1B, GPIO_MODE_OUTPUT);

    // PWM 출력 설정 (속도 제어)
    ledc_timer_config_t timer_cfg = {
        .speed_mode = PWM_MODE,
        .timer_num = PWM_TIMER,
        .duty_resolution = PWM_DUTY_RES,
        .freq_hz = PWM_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK
    };
    ledc_timer_config(&timer_cfg);

    ledc_channel_config_t ch_cfg = {
        .gpio_num = MOTOR_A1A,
        .speed_mode = PWM_MODE,
        .channel = PWM_CHANNEL,
        .timer_sel = PWM_TIMER,
        .duty = 0,
        .hpoint = 0
    };
    ledc_channel_config(&ch_cfg);

    ESP_LOGI(TAG, "Motor + PWM initialized");
}

/* -------------------- Wi-Fi 이벤트 -------------------- */
static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "Wi-Fi disconnected. Reconnecting...");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
    }
}

static void wifi_init_sta(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL);

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = CONFIG_WIFI_SSID,
            .password = CONFIG_WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGI(TAG, "Wi-Fi init done, connecting to %s", CONFIG_WIFI_SSID);
}

/* -------------------- SNTP 시간 초기화 -------------------- */
static void sntp_init_kst(void) {
    ESP_LOGI(TAG, "Initializing SNTP (KST)");
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_init();
    setenv("TZ", "KST-9", 1);
    tzset();
}

/* -------------------- 모터 및 릴레이 제어 -------------------- */
static void set_motor_speed(const char *mode) {
    int duty = 0;

    if (strcmp(mode, "low") == 0)
        duty = 80;   // 약 30%
    else if (strcmp(mode, "mid") == 0)
        duty = 160;  // 약 60%
    else if (strcmp(mode, "high") == 0)
        duty = 255;  // 최대 속도
    else
        duty = 0;

    // 정방향 회전
    gpio_set_level(MOTOR_A1B, 0);
    ledc_set_duty(PWM_MODE, PWM_CHANNEL, duty);
    ledc_update_duty(PWM_MODE, PWM_CHANNEL);

    ESP_LOGI(TAG, "Motor speed set: %s (%d/255)", mode, duty);
}

static void ac_control_update(void) {
    if (ac_power) {
        gpio_set_level(RELAY_GPIO, 1);  // 릴레이 ON
        set_motor_speed(target_mode);
    } else {
        gpio_set_level(RELAY_GPIO, 0);  // 릴레이 OFF
        ledc_set_duty(PWM_MODE, PWM_CHANNEL, 0);
        ledc_update_duty(PWM_MODE, PWM_CHANNEL);
    }
}

/* -------------------- MQTT 이벤트 -------------------- */
static void mqtt_event_handler(void *arg, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = event_data;

    switch (event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "MQTT connected");
            esp_mqtt_client_subscribe(mqtt_client, MQTT_TOPIC_CMD, 1);
            break;
        case MQTT_EVENT_DATA: {
            char topic[64];
            snprintf(topic, event->topic_len + 1, "%.*s", event->topic_len, event->topic);

            if (strcmp(topic, MQTT_TOPIC_CMD) == 0) {
                char data[256];
                snprintf(data, event->data_len + 1, "%.*s", event->data_len, event->data);
                ESP_LOGI(TAG, "Received CMD: %s", data);

                cJSON *root = cJSON_Parse(data);
                if (root) {
                    cJSON *p = cJSON_GetObjectItem(root, "ac_power");
                    cJSON *t = cJSON_GetObjectItem(root, "target_ac_temperature");
                    cJSON *h = cJSON_GetObjectItem(root, "target_ac_humidity");
                    cJSON *m = cJSON_GetObjectItem(root, "target_ac_mode");

                    if (p && cJSON_IsString(p))
                        ac_power = (strcmp(p->valuestring, "on") == 0);
                    if (t && cJSON_IsNumber(t))
                        target_temp = t->valuedouble;
                    if (h && cJSON_IsNumber(h))
                        target_hum = h->valuedouble;
                    if (m && cJSON_IsString(m))
                        strncpy(target_mode, m->valuestring, sizeof(target_mode));

                    ac_control_update();
                    cJSON_Delete(root);
                }
            }
            break;
        }
        default:
            break;
    }
}

/* -------------------- MQTT 초기화 -------------------- */
static void mqtt_app_start(void) {
    esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = MQTT_URI,
    };

    mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(mqtt_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(mqtt_client);
}

/* -------------------- DHT22 태스크 -------------------- */
static void dht_task(void *arg) {
    setDHTgpio(DHT_GPIO);
    while (1) {
        int ret = readDHT();
        errorHandler(ret);

        // float hum = getHumidity();
        // float tmp = getTemperature();

        // if (!isnan(hum) && !isnan(tmp)) {
        //     cJSON *root = cJSON_CreateObject();
        //     cJSON_AddStringToObject(root, "power", ac_power ? "on" : "off");
        //     cJSON_AddNumberToObject(root, "temperature", tmp);
        //     cJSON_AddNumberToObject(root, "humidity", hum);
        //     cJSON_AddStringToObject(root, "mode", target_mode);

        float hum = getHumidity();
        float tmp = getTemperature();

        // 1자리 반올림
        hum = roundf(hum * 10.0f) / 10.0f;
        tmp = roundf(tmp * 10.0f) / 10.0f;

        char hum_s[8], tmp_s[8];
        snprintf(hum_s, sizeof(hum_s), "%.1f", hum);
        snprintf(tmp_s, sizeof(tmp_s), "%.1f", tmp);

        if (!isnan(hum) && !isnan(tmp)) {
            cJSON *root = cJSON_CreateObject();
            cJSON_AddStringToObject(root, "power", ac_power ? "on" : "off");
            cJSON_AddStringToObject(root, "temperature", tmp_s);
            cJSON_AddStringToObject(root, "humidity", hum_s);
            cJSON_AddStringToObject(root, "mode", target_mode);
            char *msg = cJSON_PrintUnformatted(root);
            cJSON_Delete(root);

            esp_mqtt_client_publish(mqtt_client, MQTT_TOPIC_SENSOR, msg, 0, 1, 0);
            ESP_LOGI(TAG, "Published: %s", msg);
            free(msg);
        }
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

/* -------------------- app_main -------------------- */
void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());
    wifi_init_sta();
    sntp_init_kst();
    mqtt_app_start();

    gpio_set_direction(RELAY_GPIO, GPIO_MODE_OUTPUT);
    motor_init();

    gpio_set_level(RELAY_GPIO, 0);

    xTaskCreate(dht_task, "dht_task", 4096, NULL, 5, NULL);
}
