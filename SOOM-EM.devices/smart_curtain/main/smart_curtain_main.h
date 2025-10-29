#pragma once
#include "driver/gpio.h"

/* =========================
 * Wi-Fi & MQTT 설정
 * ========================= */
#define WIFI_SSID           CONFIG_WIFI_SSID
#define WIFI_PASSWORD       CONFIG_WIFI_PASSWORD
#define MQTT_BROKER_URI     CONFIG_MQTT_BROKER_URI

#define MQTT_TOPIC_CMD      CONFIG_MQTT_TOPIC_CMD
#define MQTT_TOPIC_STATE    CONFIG_MQTT_TOPIC_STATE

/* =========================
 * 하드웨어 설정
 * ========================= */
#define CURTAIN_STEP_GPIO        CONFIG_CURTAIN_STEP_GPIO
#define CURTAIN_DIR_GPIO         CONFIG_CURTAIN_DIR_GPIO
#define CURTAIN_EN_GPIO          CONFIG_CURTAIN_EN_GPIO
#define CURTAIN_EN_ACTIVE_LOW    CONFIG_CURTAIN_EN_ACTIVE_LOW
#define CURTAIN_DIR_INVERTED     CONFIG_CURTAIN_DIR_INVERTED
#define CURTAIN_PULSE_US         CONFIG_CURTAIN_PULSE_US
#define CURTAIN_STEP_GAP_US      CONFIG_CURTAIN_STEP_GAP_US
#define CURTAIN_TOTAL_STEPS      CONFIG_CURTAIN_TOTAL_STEPS