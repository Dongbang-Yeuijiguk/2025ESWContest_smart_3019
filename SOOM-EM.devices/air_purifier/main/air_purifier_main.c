#include "sdkconfig.h"
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"

#include "driver/gpio.h"
#include "hal/gpio_types.h"

#include "esp_wifi.h"
#include "mqtt_client.h"
#include "cJSON.h"

#include "pms7003.h"
#include "mq135.h"

static const char *TAG = "app";

// ========= 공유 상태 =========
static volatile float g_pm25 = 0;
static volatile float g_pm10 = 0;
static volatile int   g_aq   = 0;

static volatile bool  g_power_on = false;     // 명령 기반 전원 상태
static volatile bool  g_relay_on = false;     // 실제 릴레이 출력
static volatile char  g_mode[16] = "auto";    // slow/low/mid/high/power/auto
static volatile float g_target_pm = -1.0f;    // (옵션) 목표 PM 저장

// 릴레이(GPIO19)
#undef RELAY_GPIO
#define RELAY_GPIO CONFIG_AP_RELAY_GPIO

// MQTT 핸들
static esp_mqtt_client_handle_t g_mqtt = NULL;

// ===================== Wi-Fi(STA) =====================
static EventGroupHandle_t s_wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW("wifi", "disconnected, reconnecting...");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = (ip_event_got_ip_t *)data;
        ESP_LOGI("wifi", "got ip: " IPSTR, IP2STR(&e->ip_info.ip));
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

static void start_wifi_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        NULL, NULL));

    wifi_config_t wifi_config = {
        .sta = {
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
            .sae_pwe_h2e = WPA3_SAE_PWE_BOTH,
        },
    };
    strncpy((char *)wifi_config.sta.ssid, CONFIG_WIFI_SSID, sizeof(wifi_config.sta.ssid));
    strncpy((char *)wifi_config.sta.password, CONFIG_WIFI_PASSWORD, sizeof(wifi_config.sta.password));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group,
                                           WIFI_CONNECTED_BIT,
                                           pdFALSE, pdFALSE,
                                           pdMS_TO_TICKS(15000));
    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI("wifi", "connected");
    } else {
        ESP_LOGW("wifi", "connect timeout, continue anyway");
    }
}

// ===================== 센서 태스크 =====================
static void task_pms_reader(void *arg)
{
    uart_port_t port = (uart_port_t)(intptr_t)arg;
    em_PmsData d;

    while (1) {
        if (em_pms7003_read(port, &d, 1500) == ESP_OK) {
            g_pm25 = (float)d.pm2_5_atm;
            g_pm10 = (float)d.pm10_atm;
            ESP_LOGI("pms7003", "PM2.5=%.0f PM10=%.0f", g_pm25, g_pm10);
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

static void task_mq135_reader(void *arg)
{
    em_MQ135Ctx *ctx = (em_MQ135Ctx *)arg;
    em_MQ135Data d;

    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << RELAY_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);
    gpio_set_level(RELAY_GPIO, 0);
    g_relay_on = false;

    while (1) {
        if (em_mq135_read(ctx, &d) == ESP_OK) {
            g_aq = (int)(d.aq_index + 0.5f);
        }

        // MQTT 명령 상태 동기화
        bool want_on = g_power_on;
        if (want_on != g_relay_on) {
            gpio_set_level(RELAY_GPIO, want_on ? 1 : 0);
            g_relay_on = want_on;
            ESP_LOGI("relay", "Relay -> %s (by MQTT)", want_on ? "ON" : "OFF");
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

// ===================== MQTT =====================
static bool mode_allowed(const char *m)
{
    return (!strcmp(m, "slow") || !strcmp(m, "low") || !strcmp(m, "mid") ||
            !strcmp(m, "high") || !strcmp(m, "power") || !strcmp(m, "auto"));
}

// ✅ 새 API + 구(호환) API 모두 처리
static void handle_command_payload(const char *data, int len)
{
    cJSON *root = cJSON_ParseWithLength(data, len);
    if (!root) {
        ESP_LOGW("cmd", "JSON parse error");
        return;
    }

    // 새 포맷: 루트가 곧 payload
    // 구 포맷: {"payload":{...}}
    cJSON *p = NULL;
    if (cJSON_IsObject(root) && cJSON_GetObjectItemCaseSensitive(root, "payload")) {
        p = cJSON_GetObjectItemCaseSensitive(root, "payload"); // 구포맷
    } else {
        p = root; // 신포맷
    }

    // ap_power: "on"/"off"
    cJSON *ap_power = cJSON_GetObjectItemCaseSensitive(p, "ap_power");
    if (cJSON_IsString(ap_power)) {
        if (!strcmp(ap_power->valuestring, "on"))      g_power_on = true;
        else if (!strcmp(ap_power->valuestring, "off")) g_power_on = false;
        else ESP_LOGW("cmd", "unknown ap_power: %s", ap_power->valuestring);
    }

    // target_ap_mode
    cJSON *mode = cJSON_GetObjectItemCaseSensitive(p, "target_ap_mode");
    if (cJSON_IsString(mode)) {
        const char *m = mode->valuestring;
        if (mode_allowed(m)) {
            strncpy((char *)g_mode, m, sizeof(g_mode) - 1);
            ((char *)g_mode)[sizeof(g_mode) - 1] = '\0';
        } else {
            ESP_LOGW("cmd", "unknown mode: %s", m);
        }
    }

    // target_ap_pm (보관만)
    cJSON *tpm = cJSON_GetObjectItemCaseSensitive(p, "target_ap_pm");
    if (cJSON_IsNumber(tpm)) g_target_pm = (float)tpm->valuedouble;

    ESP_LOGI("cmd", "CMD → power=%s, mode=%s, target_pm=%.1f",
             g_power_on ? "on" : "off", (const char *)g_mode, g_target_pm);

    cJSON_Delete(root);
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t e = event_data;
    switch (event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI("mqtt", "CONNECTED");
        esp_mqtt_client_subscribe(e->client, CONFIG_MQTT_CMD_TOPIC, 1);
        ESP_LOGI("mqtt", "SUB [%s]", CONFIG_MQTT_CMD_TOPIC);
        break;
    case MQTT_EVENT_DATA:
        ESP_LOGI("mqtt_rx", "▼ Topic: %.*s", e->topic_len, e->topic);
        ESP_LOGI("mqtt_rx", "▼ Message: %.*s", e->data_len, e->data);
        if (e->topic && e->topic_len == (int)strlen(CONFIG_MQTT_CMD_TOPIC) &&
            strncmp(e->topic, CONFIG_MQTT_CMD_TOPIC, e->topic_len) == 0) {
            handle_command_payload(e->data, e->data_len);
        }
        break;
    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW("mqtt", "DISCONNECTED");
        break;
    case MQTT_EVENT_ERROR:
        ESP_LOGE("mqtt", "ERROR");
        break;
    default:
        break;
    }
}

static void task_mqtt_publisher(void *arg)
{
    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = CONFIG_MQTT_BROKER_URI,
    };
    g_mqtt = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_register_event(g_mqtt, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(g_mqtt);

    while (1) {
        const char *power_str = g_power_on ? "on" : "off";
        const char *mode_str  = (const char *)g_mode;

        char payload[192];
        snprintf(payload, sizeof(payload),
                 "{\"power\":\"%s\",\"pm_2_5\":%.1f,\"pm_10\":%.1f,"
                 "\"aqi\":%d,\"mode\":\"%s\"}",
                 power_str, g_pm25, g_pm10, g_aq, mode_str);

        esp_mqtt_client_publish(g_mqtt, CONFIG_MQTT_TOPIC, payload, 0, 1, 0);
        ESP_LOGI("mqtt_tx", "PUB → %s", payload);

        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

// ===================== app_main =====================
void app_main(void)
{
    ESP_ERROR_CHECK(nvs_flash_init());
    start_wifi_sta();

    // PMS7003
    ESP_ERROR_CHECK(em_pms7003_init((uart_port_t)CONFIG_PMS_UART_PORT,
                                    CONFIG_PMS_UART_TX_GPIO,
                                    CONFIG_PMS_UART_RX_GPIO,
                                    CONFIG_PMS_UART_BAUD));
    xTaskCreate(task_pms_reader, "pms_reader", 3 * 1024,
                (void *)(intptr_t)CONFIG_PMS_UART_PORT, 5, NULL);

    // MQ135
    em_MQ135Ctx *mq = heap_caps_calloc(1, sizeof(em_MQ135Ctx), MALLOC_CAP_DEFAULT);
    ESP_ERROR_CHECK(em_mq135_init(mq,
                                  ADC_UNIT_1,
                                  (adc_channel_t)CONFIG_MQ135_ADC_CHANNEL,
                                  (adc_atten_t)CONFIG_MQ135_ADC_ATTEN,
                                  CONFIG_MQ135_SAMPLES,
                                  (float)CONFIG_MQ135_RL_KOHM,
                                  (float)CONFIG_MQ135_R0_KOHM,
                                  CONFIG_MQ135_VREF_MV));
    xTaskCreate(task_mq135_reader, "mq135_reader", 3 * 1024, mq, 5, NULL);

    // MQTT
    xTaskCreate(task_mqtt_publisher, "mqtt_pub", 4 * 1024, NULL, 4, NULL);
}
