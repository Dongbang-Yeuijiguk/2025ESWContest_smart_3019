#pragma once
#include "driver/gpio.h"

/* =========================
 * Wi-Fi & MQTT 설정
 * ========================= */
#define WIFI_SSID               CONFIG_WIFI_SSID
#define WIFI_PASSWORD           CONFIG_WIFI_PASSWORD
#define MQTT_BROKER_URI         CONFIG_MQTT_BROKER_URI

#define MQTT_TOPIC_CMD          CONFIG_MQTT_TOPIC_CMD
#define MQTT_TOPIC_STATE        CONFIG_MQTT_TOPIC_STATE

/* =========================
 * LED 하드웨어 설정
 * ========================= */
#define LED_STRIP_GPIO          CONFIG_LED_STRIP_GPIO
#define LED_STRIP_LED_COUNT     CONFIG_LED_STRIP_LED_COUNT

/* 기본값 설정 */
#define DEFAULT_CCT_K           2700  // 기본 색온도 (휴식)
#define DEFAULT_LEVEL_PCT       50    // 기본 밝기 (%)

/* 색온도 프리셋 */
#define CCT_REST_K              2700
#define CCT_READING_K           4000
#define CCT_STUDY_K             5000
#define CCT_LIVING_K            6500