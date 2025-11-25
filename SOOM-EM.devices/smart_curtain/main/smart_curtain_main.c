#include <stdio.h>
#include <string.h>
#include "smart_curtain_main.h"

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

#include "curtain_stepper.h"

static const char *TAG = "smart_curtain";

/* 전역 변수 */
static esp_mqtt_client_handle_t s_mqtt = NULL;
static QueueHandle_t s_curtain_queue = NULL; // <-- 밑에서 쓰는 이름으로 통일
static int32_t s_pos_steps = 0;

/* -------------------- Helper Functions -------------------- */

static bool topic_equals(const char *topic, int tlen, const char *literal) {
    size_t litlen = strlen(literal);
    return (tlen == (int)litlen) && (strncmp(topic, literal, litlen) == 0);
}

/* 상태 발행: {"power":"on|off"} */
static void publish_power(bool on) {
    if (!s_mqtt) return;

    char buf[64];
    snprintf(buf, sizeof(buf), "{\"power\":\"%s\"}", on ? "on" : "off");
    esp_mqtt_client_publish(s_mqtt, MQTT_TOPIC_STATE, buf, 0, 1, 0);
    ESP_LOGI(TAG, "Published State: %s", buf);
}

/* -------------------- Curtain Task (Motor Control) -------------------- */
/* 이 태스크는 큐에 명령이 들어올 때까지 대기하다가, 명령이 오면 모터를 움직입니다. */

static void curtain_task(void *pvParameters) {
    bool target_is_open;

    while(1) {
        // 큐에서 명령이 올 때까지 무한 대기 (Block)
        if (xQueueReceive(s_curtain_queue, &target_is_open, portMAX_DELAY)) {
            int32_t target_steps = target_is_open ? CURTAIN_TOTAL_STEPS : 0;
            int32_t delta = target_steps - s_pos_steps;
            
            ESP_LOGI(TAG, "Motor Task: Moving to %s (Delta: %ld)", 
                     target_is_open ? "OPEN" : "CLOSE", delta);

            if (delta != 0) {
                curtain_stepper_move_steps(delta);

                // 모터가 움직이는 동안 대기 (이제 별도 Task이므로 MQTT를 방해하지 않음)
                while (curtain_stepper_is_busy()) {
                    vTaskDelay(pdMS_TO_TICKS(50));
                }
                
                s_pos_steps = target_steps; // 위치 업데이트
            }

            // 동작 완료 후 상태 보고
            publish_power(target_is_open);
        }
    }
}

/* -------------------- Wi-Fi & Event Handler -------------------- */
/* Wi-Fi 재연결 로직이 포함된 핸들러 */
static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                               int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } 
    else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "Wi-Fi disconnected. Retrying...");
        esp_wifi_connect(); // 끊기면 재연결 시도
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

    wifi_config_t wifi_config = {0};
    strncpy((char *)wifi_config.sta.ssid, WIFI_SSID, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, WIFI_PASSWORD, sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
}

/* -------------------- MQTT -------------------- */

static void mqtt_on_data(esp_mqtt_event_handle_t event) {
    if (!event->topic || event->topic_len <= 0) return;

    // 토픽 확인
    if (!topic_equals(event->topic, event->topic_len, MQTT_TOPIC_CMD)) return;

    // cJSON을 위한 버퍼 복사 (cJSON_Parse는 null-terminated string 필요)
    char *payload_str = (char *)malloc(event->data_len + 1);
    if (!payload_str) return;
    memcpy(payload_str, event->data, event->data_len);
    payload_str[event->data_len] = '\0';

    // cJSON 파싱
    cJSON *root = cJSON_Parse(payload_str);
    if (root) {
        cJSON *item = cJSON_GetObjectItem(root, "curtain");
        if (cJSON_IsString(item) && (item->valuestring != NULL)) {
            bool cmd_open = false;
            bool valid = false;

            if (strcmp(item->valuestring, "on") == 0) {
                cmd_open = true;
                valid = true;
            } else if (strcmp(item->valuestring, "off") == 0) {
                cmd_open = false; // Close
                valid = true;
            }

            if (valid) {
                // 직접 모터를 돌리지 않고 큐에 명령만 전달 (Non-blocking)
                xQueueSend(s_curtain_queue, &cmd_open, 0);
            }
        }
        cJSON_Delete(root);
    } else {
        ESP_LOGW(TAG, "JSON Parse Error");
    }

    free(payload_str);
}

static void mqtt_event_handler(void *arg, esp_event_base_t base, int32_t eid, void *edata) {
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)edata;
    switch (event->event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "MQTT Connected");
            esp_mqtt_client_subscribe(s_mqtt, MQTT_TOPIC_CMD, 1);
            // 재부팅 시 현재 상태 한 번 보고
            publish_power(s_pos_steps > 0);
            break;
        case MQTT_EVENT_DATA:
            mqtt_on_data(event);
            break;
        default: break;
    }
}

/* -------------------- app_main -------------------- */
void app_main(void) {
    // 1. NVS 초기화
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 2. 큐 생성 (크기 5, bool 타입)
    s_curtain_queue = xQueueCreate(5, sizeof(bool));

    // 3. 모터 하드웨어 초기화
    em_StepperConfig scfg = {
        .step_gpio = CURTAIN_STEP_GPIO,
        .dir_gpio = CURTAIN_DIR_GPIO,
        .en_gpio = CURTAIN_EN_GPIO,
        .en_active_low = CURTAIN_EN_ACTIVE_LOW,
        .dir_inverted = CURTAIN_DIR_INVERTED,
        .pulse_us = CURTAIN_PULSE_US,
        .step_gap_us = CURTAIN_STEP_GAP_US,
    };
    ESP_ERROR_CHECK(curtain_stepper_init(&scfg));
    curtain_stepper_enable(false);

    // 4. 모터 제어 태스크 실행 (우선순위 5, 스택 4096)
    xTaskCreate(curtain_task, "curtain_task", 4096, NULL, 5, NULL);

    // 5. Wi-Fi 시작
    wifi_start();

    // 6. MQTT 시작
    esp_mqtt_client_config_t mcfg = {
        .broker.address.uri = MQTT_BROKER_URI,
    };
    s_mqtt = esp_mqtt_client_init(&mcfg);
    esp_mqtt_client_register_event(s_mqtt, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_mqtt));

    ESP_LOGI(TAG, "System Started. Waiting for MQTT commands...");
}