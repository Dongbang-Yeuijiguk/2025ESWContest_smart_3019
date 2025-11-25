#include <stdio.h>
#include <string.h>
#include <math.h>
#include "smart_light_main.h"

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
#include "led_strip.h"

static const char *TAG = "SMART_LIGHT";

/* -------------------- 구조체 및 전역 변수 -------------------- */

// 조명 상태 구조체
typedef struct {
    bool power_on;
    int cct_k;      // 색온도 (Kelvin)
    int level_pct;  // 밝기 (0~100%)
} light_state_t;

// Queue 명령 메시지 구조체
typedef struct {
    bool update_power;
    bool power_val;
    
    bool update_cct;
    int cct_val;

    bool update_level;
    int level_val;
} light_cmd_t;

static led_strip_handle_t s_strip;
static esp_mqtt_client_handle_t s_mqtt = NULL;
static QueueHandle_t s_light_queue = NULL;

// 현재 상태 저장
static light_state_t s_state = {
    .power_on = false,
    .cct_k = DEFAULT_CCT_K,
    .level_pct = DEFAULT_LEVEL_PCT,
};

// 밝기 단계 프리셋
static const int k_levels[] = {25, 50, 75, 100};

/* -------------------- Utils (Math & Color) -------------------- */

static int snap_level(int pct) {
    if (pct <= 0) return 25;
    if (pct >= 100) return 100;
    int best = k_levels[0], diff = abs(pct - best);
    for (size_t i = 1; i < sizeof(k_levels)/sizeof(k_levels[0]); i++) {
        int d = abs(pct - k_levels[i]);
        if (d < diff) { best = k_levels[i]; diff = d; }
    }
    return best;
}

static bool preset_to_cct(const char* s, int* out_k) {
    if (!s || !out_k) return false;
    if (!strcasecmp(s, "휴식") || !strcasecmp(s, "rest"))   { *out_k = CCT_REST_K; return true; }
    if (!strcasecmp(s, "독서") || !strcasecmp(s, "reading")){ *out_k = CCT_READING_K; return true; }
    if (!strcasecmp(s, "공부") || !strcasecmp(s, "study"))  { *out_k = CCT_STUDY_K; return true; }
    if (!strcasecmp(s, "생활") || !strcasecmp(s, "living")) { *out_k = CCT_LIVING_K; return true; }
    return false;
}

// Kelvin -> RGB 변환 알고리즘
static void cct_to_rgb(float kelvin, uint8_t* r, uint8_t* g, uint8_t* b) {
    float t = kelvin / 100.0f;
    float rf, gf, bf;

    if (t <= 66.0f) {
        rf = 255.0f;
        gf = 99.4708025861f * logf(t) - 161.1195681661f;
        if (t <= 19.0f) bf = 0.0f;
        else bf = 138.5177312231f * logf(t - 10.0f) - 305.0447927307f;
    } else {
        rf = 329.698727446f * powf(t - 60.0f, -0.1332047592f);
        gf = 288.1221695283f * powf(t - 60.0f, -0.0755148492f);
        bf = 255.0f;
    }

    *r = (uint8_t)fminf(fmaxf(rf, 0), 255);
    *g = (uint8_t)fminf(fmaxf(gf, 0), 255);
    *b = (uint8_t)fminf(fmaxf(bf, 0), 255);
}

static inline uint8_t scale8(uint8_t v, uint8_t brightness) {
    return (uint8_t)((uint16_t)v * brightness / 255);
}

static int estimate_lux(const light_state_t* s) {
    if (!s->power_on) return 0;
    return (800 * s->level_pct) / 100;
}

/* -------------------- Hardware Control -------------------- */

static void apply_light_hardware(const light_state_t* s) {
    if (!s_strip) return;

    if (!s->power_on) {
        led_strip_clear(s_strip); // 끄기
        return;
    }

    uint8_t r, g, b;
    cct_to_rgb((float)s->cct_k, &r, &g, &b);
    
    // 전체 밝기 비율 적용
    uint8_t br = (uint8_t)((s->level_pct * 255) / 100);
    r = scale8(r, br);
    g = scale8(g, br);
    b = scale8(b, br);

    for (int i = 0; i < LED_STRIP_LED_COUNT; i++) {
        led_strip_set_pixel(s_strip, i, r, g, b);
    }
    led_strip_refresh(s_strip);
}

/* -------------------- MQTT Publish -------------------- */

static void publish_state(void) {
    if (!s_mqtt) return;

    cJSON* root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "power", s_state.power_on ? "on" : "off");
    cJSON_AddNumberToObject(root, "illuminance", estimate_lux(&s_state));
    cJSON_AddNumberToObject(root, "light_level", s_state.level_pct);
    cJSON_AddNumberToObject(root, "temperature", s_state.cct_k); // 현재 색온도도 추가

    char* out = cJSON_PrintUnformatted(root);
    if (out) {
        esp_mqtt_client_publish(s_mqtt, MQTT_TOPIC_STATE, out, 0, 1, 0);
        ESP_LOGI(TAG, "Published State: %s", out);
        cJSON_free(out);
    }
    cJSON_Delete(root);
}

/* -------------------- Light Control Task -------------------- */
/* 커튼의 curtain_task와 동일한 역할: Queue를 받아 하드웨어를 제어 */

static void light_control_task(void *pvParameters) {
    light_cmd_t cmd;

    while (1) {
        if (xQueueReceive(s_light_queue, &cmd, portMAX_DELAY)) {
            bool changed = false;

            // 1. 파워 업데이트
            if (cmd.update_power) {
                if (s_state.power_on != cmd.power_val) {
                    s_state.power_on = cmd.power_val;
                    changed = true;
                }
            }

            // 2. 색온도 업데이트
            if (cmd.update_cct) {
                if (s_state.cct_k != cmd.cct_val) {
                    s_state.cct_k = cmd.cct_val;
                    changed = true;
                }
            }

            // 3. 밝기 업데이트
            if (cmd.update_level) {
                int new_level = snap_level(cmd.level_val);
                if (s_state.level_pct != new_level) {
                    s_state.level_pct = new_level;
                    changed = true;
                }
            }

            // 변경 사항이 있으면 하드웨어 적용 및 상태 보고
            if (changed) {
                ESP_LOGI(TAG, "Light Update -> Power:%d, CCT:%d, Level:%d", 
                         s_state.power_on, s_state.cct_k, s_state.level_pct);
                apply_light_hardware(&s_state);
                publish_state();
            }
        }
    }
}

/* -------------------- MQTT Handler -------------------- */

static void mqtt_on_data(esp_mqtt_event_handle_t event) {
    if (!event->topic || event->topic_len <= 0) return;
    
    // 토픽 검사 (문자열 비교 함수는 smart_curtain과 동일하게 유지해도 됨)
    if (strncmp(event->topic, MQTT_TOPIC_CMD, event->topic_len) != 0) return;

    char *payload = (char *)malloc(event->data_len + 1);
    if (!payload) return;
    memcpy(payload, event->data, event->data_len);
    payload[event->data_len] = '\0';

    cJSON *root = cJSON_Parse(payload);
    if (root) {
        light_cmd_t cmd = {0};
        bool valid_cmd = false;

        // 1. Power Parsing
        cJSON *j_power = cJSON_GetObjectItemCaseSensitive(root, "light_power");
        if (cJSON_IsString(j_power) && j_power->valuestring) {
            cmd.update_power = true;
            cmd.power_val = (strcasecmp(j_power->valuestring, "on") == 0);
            valid_cmd = true;
        }

        // 2. CCT Parsing
        cJSON *j_temp = cJSON_GetObjectItemCaseSensitive(root, "light_temperature");
        if (j_temp) {
            cmd.update_cct = true;
            valid_cmd = true;
            if (cJSON_IsNumber(j_temp)) {
                cmd.cct_val = (int)j_temp->valuedouble;
            } else if (cJSON_IsString(j_temp) && j_temp->valuestring) {
                preset_to_cct(j_temp->valuestring, &cmd.cct_val);
            }
            // 범위 제한
            if (cmd.cct_val < 1000) cmd.cct_val = 1000;
            if (cmd.cct_val > 12000) cmd.cct_val = 12000;
        }

        // 3. Level Parsing
        cJSON *j_level = cJSON_GetObjectItemCaseSensitive(root, "target_light_level");
        if (cJSON_IsNumber(j_level)) {
            cmd.update_level = true;
            cmd.level_val = (int)j_level->valuedouble;
            valid_cmd = true;
        }

        if (valid_cmd) {
            // Blocking 방지를 위해 Queue로 전송
            xQueueSend(s_light_queue, &cmd, 0);
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
            publish_state(); // 초기 상태 보고
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
    // 1. NVS 초기화
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 2. 큐 생성 (명령 버퍼)
    s_light_queue = xQueueCreate(5, sizeof(light_cmd_t));

    // 3. LED Strip 초기화
    led_strip_config_t scfg = {
        .strip_gpio_num = LED_STRIP_GPIO,
        .max_leds = LED_STRIP_LED_COUNT,
        .led_model = LED_MODEL_WS2812,
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB,
        .flags = {.invert_out = false},
    };
    led_strip_rmt_config_t rcfg = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,
        .flags = {.with_dma = false},
    };
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&scfg, &rcfg, &s_strip));
    ESP_ERROR_CHECK(led_strip_clear(s_strip));
    
    // 초기 상태 적용
    apply_light_hardware(&s_state);

    // 4. Light Control Task 실행
    xTaskCreate(light_control_task, "light_task", 4096, NULL, 5, NULL);

    // 5. Wi-Fi 시작
    wifi_start();

    // 6. MQTT 시작
    esp_mqtt_client_config_t mcfg = {
        .broker.address.uri = MQTT_BROKER_URI,
    };
    s_mqtt = esp_mqtt_client_init(&mcfg);
    esp_mqtt_client_register_event(s_mqtt, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_mqtt));
    
    ESP_LOGI(TAG, "Smart Light System Started.");
}