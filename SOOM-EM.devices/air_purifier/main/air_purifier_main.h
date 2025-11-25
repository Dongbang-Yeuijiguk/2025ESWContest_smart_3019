#pragma once
#include "sdkconfig.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/uart.h"
#include "hal/adc_types.h"

/* Wi-Fi & MQTT */
#define WIFI_SSID               CONFIG_WIFI_SSID
#define WIFI_PASSWORD           CONFIG_WIFI_PASSWORD
#define MQTT_BROKER_URI         CONFIG_MQTT_BROKER_URI
#define MQTT_TOPIC_CMD          CONFIG_MQTT_TOPIC_CMD
#define MQTT_TOPIC_STATE        CONFIG_MQTT_TOPIC_STATE

/* 하드웨어 (L298N & Relay) */
#define FAN_PWM_GPIO            CONFIG_FAN_PWM_GPIO
#define AP_RELAY_GPIO           CONFIG_AP_RELAY_GPIO

// PWM 설정
#define FAN_LEDC_TIMER          LEDC_TIMER_0
#define FAN_LEDC_MODE           LEDC_LOW_SPEED_MODE
#define FAN_LEDC_CHANNEL        LEDC_CHANNEL_0
#define FAN_LEDC_DUTY_RES       LEDC_TIMER_10_BIT // 0~1023
#define FAN_LEDC_FREQ           5000 

/* 센서 설정 */
#define PMS_UART_PORT           CONFIG_PMS_UART_PORT
#define PMS_TX_GPIO             CONFIG_PMS_UART_TX_GPIO
#define PMS_RX_GPIO             CONFIG_PMS_UART_RX_GPIO
#define PMS_BAUD                CONFIG_PMS_UART_BAUD

#define MQ135_ADC_UNIT          ADC_UNIT_1
#define MQ135_ADC_CHANNEL       CONFIG_MQ135_ADC_CHANNEL
#define MQ135_ADC_ATTEN         CONFIG_MQ135_ADC_ATTEN
#define MQ135_SAMPLES           CONFIG_MQ135_SAMPLES