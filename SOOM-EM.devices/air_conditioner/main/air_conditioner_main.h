#pragma once
#include "driver/gpio.h"
#include "driver/ledc.h"

/* =========================
 * Wi-Fi & MQTT 설정
 * ========================= */
#define WIFI_SSID               CONFIG_WIFI_SSID
#define WIFI_PASSWORD           CONFIG_WIFI_PASSWORD
#define MQTT_BROKER_URI         CONFIG_MQTT_BROKER_URI

#define MQTT_TOPIC_CMD          CONFIG_MQTT_TOPIC_CMD
#define MQTT_TOPIC_SENSOR       CONFIG_MQTT_TOPIC_SENSOR // 센서+상태 리포트 토픽

/* =========================
 * 하드웨어 설정 (Motor & Relay & Sensor)
 * ========================= */
// 모터 (L298N 등) 제어 핀
#define MOTOR_A1A_GPIO          CONFIG_MOTOR_A1A
#define MOTOR_A1B_GPIO          CONFIG_MOTOR_A1B

// 냉방기(펠티어 등) 릴레이
#define RELAY_GPIO              CONFIG_RELAY_GPIO

// 온습도 센서 (DHT22)
#define DHT_GPIO                CONFIG_DHT_GPIO

/* PWM 설정 (LEDC) */
#define FAN_LEDC_TIMER          LEDC_TIMER_0
#define FAN_LEDC_MODE           LEDC_LOW_SPEED_MODE
#define FAN_LEDC_OUTPUT_IO      MOTOR_A1A_GPIO // 속도 제어 핀
#define FAN_LEDC_CHANNEL        LEDC_CHANNEL_0
#define FAN_LEDC_DUTY_RES       LEDC_TIMER_8_BIT  // 0~255
#define FAN_LEDC_FREQUENCY      5000              // 5kHz

/* 기본값 */
#define DEFAULT_TARGET_TEMP     24.0f
#define DEFAULT_TARGET_HUM      50.0f