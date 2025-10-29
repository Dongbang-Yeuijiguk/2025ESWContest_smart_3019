#include <math.h>
#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_sntp.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "led_strip.h"
#include "mqtt_client.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#define LED_STRIP_GPIO              CONFIG_LED_STRIP_GPIO
#define LED_STRIP_LED_COUNT         CONFIG_LED_STRIP_LED_COUNT
#define LED_STRIP_MODEL             LED_MODEL_WS2812
#define LED_COLOR_ORDER             LED_STRIP_COLOR_COMPONENT_FMT_GRB

#define MQTT_TOPIC_CMD              CONFIG_MQTT_TOPIC_CMD
#define MQTT_TOPIC_STATE            CONFIG_MQTT_TOPIC_STATE

#define WIFI_SSID                   CONFIG_WIFI_SSID
#define WIFI_PASS                   CONFIG_WIFI_PASS
#define MQTT_BROKER_URI             CONFIG_MQTT_BROKER_URI

#define STATE_PUB_PERIOD_MS         CONFIG_STATE_PUB_PERIOD_MS

// 밝기 허용 단계
static const int k_levels[] = {25, 50, 75, 100};

// 프리셋 색온도(휴식/독서/공부/생활)
#define CCT_REST_K                  2700
#define CCT_READING_K               4000
#define CCT_STUDY_K                 5000
#define CCT_LIVING_K                6500

// ------------------------- 전역 -------------------------

static const char* TAG = "SMART_LIGHT";
static led_strip_handle_t g_strip;
static esp_mqtt_client_handle_t g_mqtt = NULL;

typedef struct {
    bool power_on;
    int cct_k;
    int level_pct;
} light_state_t;

static light_state_t g_state = {
    .power_on = false,
    .cct_k = CCT_REST_K,
    .level_pct = 50,
};

static EventGroupHandle_t g_net_evt;
#define NET_GOT_IP_BIT (1 << 0)

// ------------------------- 유틸 -------------------------

static inline uint8_t scale8(uint8_t v, uint8_t brightness) {
    return (uint8_t)((uint16_t)v * brightness / 255);
}

static void cct_to_rgb(float kelvin, uint8_t* r, uint8_t* g, uint8_t* b)
{
    float t = kelvin / 100.0f;
    float rf, gf, bf;

    if (t <= 66.0f) rf = 255.0f;
    else {
        rf = 329.698727446f * powf(t - 60.0f, -0.1332047592f);
        rf = fminf(fmaxf(rf, 0), 255);
    }

    if (t <= 66.0f)
        gf = 99.4708025861f * logf(t) - 161.1195681661f;
    else
        gf = 288.1221695283f * powf(t - 60.0f, -0.0755148492f);
    gf = fminf(fmaxf(gf, 0), 255);

    if (t >= 66.0f) bf = 255.0f;
    else if (t <= 19.0f) bf = 0.0f;
    else {
        bf = 138.5177312231f * logf(t - 10.0f) - 305.0447927307f;
        bf = fminf(fmaxf(bf, 0), 255);
    }

    *r = (uint8_t)rf;
    *g = (uint8_t)gf;
    *b = (uint8_t)bf;
}

static void set_all_pixels_rgb(uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < LED_STRIP_LED_COUNT; i++)
        led_strip_set_pixel(g_strip, i, r, g, b);
    led_strip_refresh(g_strip);
}

static void apply_state_to_strip(const light_state_t* s) {
    if (!s->power_on) {
        set_all_pixels_rgb(0, 0, 0);
        return;
    }

    uint8_t r, g, b;
    cct_to_rgb((float)s->cct_k, &r, &g, &b);
    uint8_t br = (uint8_t)((s->level_pct * 255) / 100);
    r = scale8(r, br);
    g = scale8(g, br);
    b = scale8(b, br);
    set_all_pixels_rgb(r, g, b);
}

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

static int estimate_lux(const light_state_t* s) {
    if (!s->power_on) return 0;
    return (800 * s->level_pct) / 100;
}

// ------------------------- MQTT 퍼블리시 -------------------------

static void publish_state(bool retain) {
    if (!g_mqtt) return;

    cJSON* root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "power", g_state.power_on ? "on" : "off");
    cJSON_AddNumberToObject(root, "illuminance", estimate_lux(&g_state));
    cJSON_AddNumberToObject(root, "light_level", g_state.level_pct);

    char* out = cJSON_PrintUnformatted(root);
    if (out) {
        esp_mqtt_client_publish(g_mqtt, MQTT_TOPIC_STATE, out, 0, 1, retain ? 1 : 0);
        cJSON_free(out);
    }
    cJSON_Delete(root);
}

// ------------------------- MQTT 핸들링 -------------------------

static void handle_cmd_json(const char* json, size_t len) {
    cJSON* root = cJSON_ParseWithLength(json, len);
    if (!root) return;

    light_state_t new_state = g_state;
    bool changed = false;

    const cJSON* j_power = cJSON_GetObjectItemCaseSensitive(root, "light_power");
    if (cJSON_IsString(j_power))
        new_state.power_on = !strcasecmp(j_power->valuestring, "on"), changed = true;

    const cJSON* j_temp = cJSON_GetObjectItemCaseSensitive(root, "light_temperature");
    if (j_temp) {
        if (cJSON_IsNumber(j_temp)) {
            int k = (int)j_temp->valuedouble;
            new_state.cct_k = fmin(fmax(k, 1000), 12000);
            changed = true;
        } else if (cJSON_IsString(j_temp)) {
            int k = 0;
            if (preset_to_cct(j_temp->valuestring, &k))
                new_state.cct_k = k, changed = true;
        }
    }

    const cJSON* j_level = cJSON_GetObjectItemCaseSensitive(root, "target_light_level");
    if (cJSON_IsNumber(j_level)) {
        new_state.level_pct = snap_level((int)j_level->valuedouble);
        changed = true;
    }

    if (changed) {
        g_state = new_state;
        apply_state_to_strip(&g_state);
        publish_state(false);
    }
    cJSON_Delete(root);
}

static void mqtt_event_handler(void* arg, esp_event_base_t base, int32_t eid, void* edata) {
    esp_mqtt_event_handle_t e = (esp_mqtt_event_handle_t)edata;
    switch (eid) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "MQTT connected");
        esp_mqtt_client_subscribe(g_mqtt, MQTT_TOPIC_CMD, 1);
        publish_state(false);
        break;
    case MQTT_EVENT_DATA:
        if (e->topic && e->topic_len == strlen(MQTT_TOPIC_CMD) &&
            strncmp(e->topic, MQTT_TOPIC_CMD, e->topic_len) == 0)
            handle_cmd_json(e->data, e->data_len);
        break;
    default:
        break;
    }
}

// ------------------------- 네트워크 -------------------------

static void wifi_event_handler(void* arg, esp_event_base_t base, int32_t id, void* data) {
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) esp_wifi_connect();
    else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "Wi-Fi disconnected, reconnecting...");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP)
        xEventGroupSetBits(g_net_evt, NET_GOT_IP_BIT);
}

static void start_wifi(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event_handler, NULL);

    wifi_config_t wifi_config = {0};
    strlcpy((char*)wifi_config.sta.ssid, WIFI_SSID, sizeof(wifi_config.sta.ssid));
    strlcpy((char*)wifi_config.sta.password, WIFI_PASS, sizeof(wifi_config.sta.password));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
}

// ------------------------- 태스크 -------------------------

static void state_publish_task(void* arg) {
    const TickType_t period = pdMS_TO_TICKS(STATE_PUB_PERIOD_MS);
    while (1) {
        publish_state(true);
        vTaskDelay(period);
    }
}

// ------------------------- 앱 진입 -------------------------

void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init());

    // LED Strip
    led_strip_config_t scfg = {
        .strip_gpio_num = LED_STRIP_GPIO,
        .max_leds = LED_STRIP_LED_COUNT,
        .led_model = LED_STRIP_MODEL,
        .color_component_format = LED_COLOR_ORDER,
        .flags = {.invert_out = false},
    };
    led_strip_rmt_config_t rcfg = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,
        .mem_block_symbols = 0,
        .flags = {.with_dma = false},
    };
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&scfg, &rcfg, &g_strip));
    ESP_ERROR_CHECK(led_strip_clear(g_strip));
    ESP_ERROR_CHECK(led_strip_refresh(g_strip));
    apply_state_to_strip(&g_state);

    // Wi-Fi
    g_net_evt = xEventGroupCreate();
    start_wifi();
    xEventGroupWaitBits(g_net_evt, NET_GOT_IP_BIT, pdFALSE, pdTRUE, portMAX_DELAY);

    // MQTT
    esp_mqtt_client_config_t mcfg = {
        .broker.address.uri = MQTT_BROKER_URI,
    };
    g_mqtt = esp_mqtt_client_init(&mcfg);
    esp_mqtt_client_register_event(g_mqtt, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(g_mqtt);

    xTaskCreate(state_publish_task, "state_pub", 4096, NULL, 5, NULL);
}
