#include "curtain_stepper.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#define STEPPER_QUEUE_LEN 4

static const char *TAG = "CURTAIN_STEPPER";
static em_StepperConfig s_cfg;
static QueueHandle_t s_cmd_q = NULL;
static TaskHandle_t s_task = NULL;
static volatile bool s_busy = false;
static volatile bool s_stop = false;

typedef struct { int32_t steps; } step_cmd_t;

static inline void set_dir_from_steps(int32_t steps)
{
    int dir = (steps > 0) ? 1 : 0;
    if (s_cfg.dir_inverted) dir = !dir;
    gpio_set_level(s_cfg.dir_gpio, dir);
}

static inline void pulse_once(void)
{
    gpio_set_level(s_cfg.step_gpio, 1);
    esp_rom_delay_us(s_cfg.pulse_us);
    gpio_set_level(s_cfg.step_gpio, 0);
    esp_rom_delay_us(s_cfg.step_gap_us);
}

static inline void en_write(bool enable)
{
    if (s_cfg.en_gpio < 0) return;
    int level = enable ? (s_cfg.en_active_low ? 0 : 1)
                       : (s_cfg.en_active_low ? 1 : 0);
    gpio_set_level(s_cfg.en_gpio, level);
}

static void stepper_task(void *arg)
{
    step_cmd_t cmd;
    for (;;) {
        if (xQueueReceive(s_cmd_q, &cmd, portMAX_DELAY) != pdTRUE) continue;
        if (cmd.steps == 0) continue;
        s_busy = true;
        s_stop = false;

        set_dir_from_steps(cmd.steps);
        en_write(true);
        int n = (cmd.steps > 0) ? cmd.steps : -cmd.steps;
        for (int i = 0; i < n; i++) {
            if (s_stop) break;
            pulse_once();
        }
        en_write(false);
        s_busy = false;
    }
}

esp_err_t curtain_stepper_init(const em_StepperConfig *cfg)
{
    if (!cfg) return ESP_ERR_INVALID_ARG;
    s_cfg = *cfg;

    gpio_config_t io = {
        .mode = GPIO_MODE_OUTPUT,
        .pin_bit_mask = (1ULL << s_cfg.step_gpio) | (1ULL << s_cfg.dir_gpio),
    };
    if (s_cfg.en_gpio >= 0) io.pin_bit_mask |= (1ULL << s_cfg.en_gpio);
    ESP_ERROR_CHECK(gpio_config(&io));

    gpio_set_level(s_cfg.step_gpio, 0);
    gpio_set_level(s_cfg.dir_gpio, 0);
    if (s_cfg.en_gpio >= 0) en_write(false);

    s_cmd_q = xQueueCreate(STEPPER_QUEUE_LEN, sizeof(step_cmd_t));
    if (!s_cmd_q) return ESP_ERR_NO_MEM;

    xTaskCreate(stepper_task, "stepper_task", 2048, NULL, 5, &s_task);
    ESP_LOGI(TAG, "init done (STEP=%d DIR=%d EN=%d)", s_cfg.step_gpio, s_cfg.dir_gpio, s_cfg.en_gpio);
    return ESP_OK;
}

esp_err_t curtain_stepper_enable(bool enable)
{
    en_write(enable);
    return ESP_OK;
}

esp_err_t curtain_stepper_move_steps(int32_t steps)
{
    if (s_busy) return ESP_ERR_INVALID_STATE;
    step_cmd_t cmd = {.steps = steps};
    if (xQueueSend(s_cmd_q, &cmd, 0) != pdTRUE) return ESP_ERR_INVALID_STATE;
    return ESP_OK;
}

bool curtain_stepper_is_busy(void) { return s_busy; }
void curtain_stepper_stop(void) { s_stop = true; }
