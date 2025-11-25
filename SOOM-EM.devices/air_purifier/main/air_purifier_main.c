#include "air_purifier_main.h"

#include <stdio.h>
#include <string.h>
#include <math.h>

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

#include "pms7003.h"
#include "mq135.h"

static const char *TAG = "air_purifier";

// --- 자료형 ---
typedef enum { MODE_MANUAL = 0, MODE_AUTO } air_mode_t;

typedef struct {
    bool power_on;
    air_mode_t mode;
    int fan_level;
    float pm25;
    float co2;
} purifier_state_t;

typedef struct {
    bool update_power; bool power_val;
    bool update_mode;  air_mode_t mode_val;
    bool update_level; int level_val;
    bool update_sensor; float pm25; float co2;
} purifier_cmd_t;

static purifier_state_t s_state = { .power_on = false, .mode = MODE_AUTO, .fan_level = 1 };
static QueueHandle_t s_queue = NULL;
static esp_mqtt_client_handle_t s_mqtt = NULL;

// --- 하드웨어 제어 (L298N) ---
static void hw_init_fan(void) {
    // PWM (ENA)
    ledc_timer_config_t timer = {
        .speed_mode = FAN_LEDC_MODE, .timer_num = FAN_LEDC_TIMER,
        .duty_resolution = FAN_LEDC_DUTY_RES, .freq_hz = FAN_LEDC_FREQ, .clk_cfg = LEDC_AUTO_CLK
    };
    ledc_timer_config(&timer);
    ledc_channel_config_t chan = {
        .speed_mode = FAN_LEDC_MODE, .channel = FAN_LEDC_CHANNEL,
        .timer_sel = FAN_LEDC_TIMER, .intr_type = LEDC_INTR_DISABLE,
        .gpio_num = FAN_PWM_GPIO, .duty = 0, .hpoint = 0
    };
    ledc_channel_config(&chan);

    // Relay (IN1)
    gpio_config_t io = { .pin_bit_mask = (1ULL << AP_RELAY_GPIO), .mode = GPIO_MODE_OUTPUT };
    gpio_config(&io);
    gpio_set_level(AP_RELAY_GPIO, 0);
}

static void apply_hardware(const purifier_state_t *s) {
    if (s->power_on) {
        gpio_set_level(AP_RELAY_GPIO, 1); // IN1 HIGH
        uint32_t duty = 0;
        // PWM 10bit(1023)
        if (s->fan_level == 1) duty = 400;       // Low
        else if (s->fan_level == 2) duty = 700;  // Mid
        else duty = 1023;                        // High
        
        ledc_set_duty(FAN_LEDC_MODE, FAN_LEDC_CHANNEL, duty);
        ledc_update_duty(FAN_LEDC_MODE, FAN_LEDC_CHANNEL);
    } else {
        gpio_set_level(AP_RELAY_GPIO, 0); // IN1 LOW
        ledc_set_duty(FAN_LEDC_MODE, FAN_LEDC_CHANNEL, 0);
        ledc_update_duty(FAN_LEDC_MODE, FAN_LEDC_CHANNEL);
    }
}

static void publish_state(void) {
    if (!s_mqtt) return;
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "power", s_state.power_on ? "on" : "off");
    cJSON_AddStringToObject(root, "mode", s_state.mode == MODE_AUTO ? "auto" : "manual");
    cJSON_AddNumberToObject(root, "level", s_state.fan_level);
    cJSON_AddNumberToObject(root, "pm25", (int)s_state.pm25);
    cJSON_AddNumberToObject(root, "co2", (int)s_state.co2);
    char *out = cJSON_PrintUnformatted(root);
    esp_mqtt_client_publish(s_mqtt, MQTT_TOPIC_STATE, out, 0, 1, 0);
    cJSON_free(out);
    cJSON_Delete(root);
}

// --- Tasks ---
static void control_task(void *arg) {
    purifier_cmd_t cmd;
    while (1) {
        if (xQueueReceive(s_queue, &cmd, portMAX_DELAY)) {
            bool changed = false;
            if (cmd.update_power && s_state.power_on != cmd.power_val) {
                s_state.power_on = cmd.power_val; changed = true;
            }
            if (cmd.update_mode && s_state.mode != cmd.mode_val) {
                s_state.mode = cmd.mode_val; changed = true;
            }
            if (cmd.update_level && s_state.mode == MODE_MANUAL) {
                s_state.fan_level = cmd.level_val; changed = true;
            }
            if (cmd.update_sensor) {
                s_state.pm25 = cmd.pm25; s_state.co2 = cmd.co2;
                // Auto Mode Logic
                if (s_state.power_on && s_state.mode == MODE_AUTO) {
                    int target = 1;
                    if (s_state.pm25 > 50) target = 3;
                    else if (s_state.pm25 > 25) target = 2;
                    
                    if (s_state.fan_level != target) {
                        s_state.fan_level = target; changed = true;
                    }
                }
                publish_state(); // 주기적 리포트
            }

            if (changed) {
                apply_hardware(&s_state);
                publish_state();
            }
        }
    }
}

static void sensor_task(void *arg) {
    em_pms7003_init(PMS_UART_PORT, PMS_TX_GPIO, PMS_RX_GPIO, PMS_BAUD);
    
    em_MQ135Ctx mq_ctx;
    em_mq135_init(&mq_ctx, MQ135_ADC_UNIT, MQ135_ADC_CHANNEL, MQ135_ADC_ATTEN, MQ135_SAMPLES);

    em_PmsData pms;
    em_MQ135Data mq;

    while (1) {
        bool pms_ok = (em_pms7003_read(PMS_UART_PORT, &pms, 1000) == ESP_OK);
        bool mq_ok = (em_mq135_read(&mq_ctx, &mq) == ESP_OK);

        if (pms_ok || mq_ok) {
            purifier_cmd_t cmd = {0};
            cmd.update_sensor = true;
            cmd.pm25 = pms_ok ? pms.pm2_5_atm : s_state.pm25;
            cmd.co2 = mq_ok ? mq.co2eq_ppm : s_state.co2;
            xQueueSend(s_queue, &cmd, 0);
        }
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

// --- MQTT & Wi-Fi ---
static void mqtt_handler(void *arg, esp_event_base_t b, int32_t id, void *data) {
    esp_mqtt_event_handle_t e = data;
    if (id == MQTT_EVENT_CONNECTED) {
        esp_mqtt_client_subscribe(s_mqtt, MQTT_TOPIC_CMD, 1);
        publish_state();
    } else if (id == MQTT_EVENT_DATA) {
        if (strncmp(e->topic, MQTT_TOPIC_CMD, e->topic_len) == 0) {
            cJSON *root = cJSON_ParseWithLength(e->data, e->data_len);
            if (root) {
                purifier_cmd_t cmd = {0};
                cJSON *p = cJSON_GetObjectItem(root, "ap_power");
                if (cJSON_IsString(p)) {
                    cmd.update_power = true;
                    cmd.power_val = (strcmp(p->valuestring, "on") == 0);
                }
                cJSON *m = cJSON_GetObjectItem(root, "target_ap_mode");
                if (cJSON_IsString(m)) {
                    cmd.update_mode = true;
                    cmd.mode_val = (strcmp(m->valuestring, "auto") == 0) ? MODE_AUTO : MODE_MANUAL;
                }
                cJSON *l = cJSON_GetObjectItem(root, "target_ap_level");
                if (cJSON_IsNumber(l)) {
                    cmd.update_level = true;
                    cmd.level_val = (int)l->valuedouble;
                }
                xQueueSend(s_queue, &cmd, 0);
                cJSON_Delete(root);
            }
        }
    }
}

static void wifi_handler(void* arg, esp_event_base_t b, int32_t id, void* data) {
    if (id == WIFI_EVENT_STA_START || id == WIFI_EVENT_STA_DISCONNECTED) esp_wifi_connect();
}

void app_main(void) {
    nvs_flash_init();
    esp_netif_init();
    esp_event_loop_create_default();
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t wcfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&wcfg);
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_handler, NULL);
    
    wifi_config_t wifi_conf = {0};
    strcpy((char*)wifi_conf.sta.ssid, WIFI_SSID);
    strcpy((char*)wifi_conf.sta.password, WIFI_PASSWORD);
    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_set_config(WIFI_IF_STA, &wifi_conf);
    esp_wifi_start();

    s_queue = xQueueCreate(5, sizeof(purifier_cmd_t));
    hw_init_fan();
    xTaskCreate(control_task, "ctrl", 4096, NULL, 5, NULL);
    xTaskCreate(sensor_task, "sens", 4096, NULL, 3, NULL);

    esp_mqtt_client_config_t mcfg = { .broker.address.uri = MQTT_BROKER_URI };
    s_mqtt = esp_mqtt_client_init(&mcfg);
    esp_mqtt_client_register_event(s_mqtt, ESP_EVENT_ANY_ID, mqtt_handler, NULL);
    esp_mqtt_client_start(s_mqtt);
}