#include <stdio.h>
#include <string.h>
#include "smart_curtain_main.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "mqtt_client.h"

#include "curtain_stepper.h"

static const char *TAG = "APP";
static esp_mqtt_client_handle_t s_mqtt = NULL;
static int32_t s_pos_steps = 0;     // 현재 위치(스텝)
static int32_t s_target_steps = 0;  // 목표 위치(스텝)

/* -------------------- utils -------------------- */
static bool topic_equals(const char *topic, int tlen, const char *literal)
{
    size_t litlen = strlen(literal);
    return (tlen == (int)litlen) && (strncmp(topic, literal, litlen) == 0);
}

/* {"<key>":"on|off"} 파서 (경량) */
static bool parse_on_with_key(const char *payload, int len, const char *key, bool *out_on)
{
    char buf[64];
    if (len >= (int)sizeof(buf)) len = (int)sizeof(buf) - 1;
    memcpy(buf, payload, len);
    buf[len] = '\0';

    char needle[24];
    snprintf(needle, sizeof(needle), "\"%s\"", key);

    const char *p = strstr(buf, needle);
    if (!p) return false;
    p = strchr(p, ':');
    if (!p) return false;

    while (*p == ':' || *p == ' ' || *p == '\t') p++;
    if (*p == '\"') p++;

    if (strncmp(p, "on", 2) == 0)       { *out_on = true;  return true; }
    else if (strncmp(p, "off", 3) == 0) { *out_on = false; return true; }

    return false;
}

/* 신규 API 수신: {"curtain":"on|off"} */
static bool parse_curtain_on(const char *payload, int len, bool *out_on)
{
    return parse_on_with_key(payload, len, "curtain", out_on);
}

/* 상태 발행: main topic(sensor/smart_curtain)으로 {"power":"on|off"} */
static void publish_power(bool on)
{
    char buf[32];
    snprintf(buf, sizeof(buf), "{\"power\":\"%s\"}", on ? "on" : "off");
    (void)esp_mqtt_client_publish(s_mqtt, MQTT_TOPIC_STATE, buf, 0, 1, 0);
}

/* 스텝 모션 수행 */
static void move_to_target(void)
{
    int32_t delta = s_target_steps - s_pos_steps;
    if (delta == 0) {
        publish_power(s_pos_steps > 0);
        return;
    }

    (void)curtain_stepper_enable(true);
    (void)curtain_stepper_move_steps(delta);

    while (curtain_stepper_is_busy()) {
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    s_pos_steps = s_target_steps;
    (void)curtain_stepper_enable(false);

    // publish_power(s_pos_steps > 0);
}

/* --- on → open, off → close --- */
static void handle_open(void)
{
    s_target_steps = CURTAIN_TOTAL_STEPS;  // 완전 개방
    publish_power(true);
    ESP_LOGI(TAG, "CMD: OPEN (curtain:on)");
    move_to_target();
}

static void handle_close(void)
{
    s_target_steps = 0;  // 완전 닫힘
    publish_power(false);
    ESP_LOGI(TAG, "CMD: CLOSE (curtain:off)");
    move_to_target();
}

/* -------------------- Wi-Fi -------------------- */
static void wifi_start(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    (void)esp_netif_create_default_wifi_sta();

    wifi_init_config_t wcfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wcfg));

    wifi_config_t sta = {0};
    strncpy((char *)sta.sta.ssid, WIFI_SSID, sizeof(sta.sta.ssid) - 1);
    strncpy((char *)sta.sta.password, WIFI_PASSWORD, sizeof(sta.sta.password) - 1);

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta));
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());
}

/* -------------------- MQTT -------------------- */
static void mqtt_on_connected(void)
{
    ESP_LOGI(TAG, "MQTT connected");
    // 명령 토픽만 구독(QoS1) → 자기발행 루프 방지
    (void)esp_mqtt_client_subscribe(s_mqtt, MQTT_TOPIC_CMD, 1);

    // 부팅/재연결 시 현재 상태 1회 보고(상태 토픽으로만)
    publish_power(s_pos_steps > 0);
}

static void mqtt_on_data(esp_mqtt_event_handle_t event)
{
    if (!event->topic || event->topic_len <= 0) return;

    // 오직 명령 토픽만 처리 (sensor/curtain/cmd)
    if (!topic_equals(event->topic, event->topic_len, MQTT_TOPIC_CMD)) return;

    bool on = false;
    if (!parse_curtain_on(event->data, event->data_len, &on)) {
        ESP_LOGW(TAG, "Bad payload. Expect: {\"curtain\":\"on|off\"}");
        return;
    }
    if (on)  handle_open();   // == power:on
    else     handle_close();  // == power:off
}

static void mqtt_event_handler(void *arg,
                               esp_event_base_t base,
                               int32_t eid,
                               void *edata)
{
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)edata;
    switch (event->event_id) {
        case MQTT_EVENT_CONNECTED:
            mqtt_on_connected();
            break;
        case MQTT_EVENT_DATA:
            mqtt_on_data(event);
            break;
        default:
            break;
    }
}

/* -------------------- app_main -------------------- */
void app_main(void)
{
    ESP_ERROR_CHECK(nvs_flash_init());
    wifi_start();

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
    (void)curtain_stepper_enable(false);

    esp_mqtt_client_config_t mcfg = {
        .broker.address.uri = MQTT_BROKER_URI,
    };
    s_mqtt = esp_mqtt_client_init(&mcfg);
    esp_mqtt_client_register_event(s_mqtt, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_mqtt));

    ESP_LOGI(TAG, "Curtain ready. CMD: %s  STATE: %s  Payloads: {\"curtain\":\"on|off\"} -> {\"power\":\"on|off\"}",
             MQTT_TOPIC_CMD, MQTT_TOPIC_STATE);
}
