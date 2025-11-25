#include "curtain_stepper.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

static const char *TAG = "CURTAIN_STEPPER";

/* 설정 상수 */
#define STEPPER_QUEUE_LEN 4

/* * Watchdog Timer(WDT) 리셋 방지를 위한 배치 처리 상수.
 * 모터가 장시간 연속 동작할 경우 Task가 CPU를 독점하여 WDT가 트리거되는 것을 막기 위해,
 * 일정 스텝마다 vTaskDelay를 통해 문맥 전환(Context Switch)을 수행함.
 */
#define STEPS_PER_BATCH 50 

/* 내부 변수 */
static em_StepperConfig s_cfg;
static QueueHandle_t s_cmd_q = NULL;
static TaskHandle_t s_task = NULL;
static volatile bool s_busy = false;
static volatile bool s_stop = false;

typedef struct { int32_t steps; } step_cmd_t;

/* -------------------- 내부 함수 -------------------- */

/* 스텝 수의 부호에 따라 방향 핀 설정 */
static inline void set_dir_from_steps(int32_t steps)
{
    int dir = (steps > 0) ? 1 : 0;
    if (s_cfg.dir_inverted) dir = !dir;
    gpio_set_level(s_cfg.dir_gpio, dir);
}

/* 단일 스텝 펄스 생성 (High -> Delay -> Low -> Delay) */
static inline void pulse_once(void)
{
    gpio_set_level(s_cfg.step_gpio, 1);
    esp_rom_delay_us(s_cfg.pulse_us);
    gpio_set_level(s_cfg.step_gpio, 0);
    esp_rom_delay_us(s_cfg.step_gap_us);
}

/* 모터 드라이버 Enable/Disable 제어 */
static inline void en_write(bool enable)
{
    if (s_cfg.en_gpio < 0) return;
    // Active Low/High 설정에 따른 레벨 결정
    int level = enable ? (s_cfg.en_active_low ? 0 : 1)
                       : (s_cfg.en_active_low ? 1 : 0);
    gpio_set_level(s_cfg.en_gpio, level);
}

/* -------------------- 메인 태스크 -------------------- */

static void stepper_task(void *arg)
{
    step_cmd_t cmd;
    for (;;) {
        // 큐에서 명령 대기 (Blocking)
        if (xQueueReceive(s_cmd_q, &cmd, portMAX_DELAY) != pdTRUE) continue;
        
        s_stop = false;
        
        if (cmd.steps == 0) {
            s_busy = false;
            continue;
        }

        // 방향 설정 및 모터 활성화
        set_dir_from_steps(cmd.steps);
        en_write(true);

        int total_steps = (cmd.steps > 0) ? cmd.steps : -cmd.steps;
        int steps_done = 0;

        // WDT 방지를 위한 배치 루프
        while (steps_done < total_steps) {
            if (s_stop) break; // 강제 정지 플래그 확인

            int batch = total_steps - steps_done;
            if (batch > STEPS_PER_BATCH) batch = STEPS_PER_BATCH;

            // 배치만큼 펄스 출력
            for (int i = 0; i < batch; i++) {
                pulse_once();
            }
            steps_done += batch;

            // 다른 태스크(시스템 태스크 포함)에 실행 시간을 양보하여 WDT 리셋 방지
            if (steps_done < total_steps) {
                 vTaskDelay(1); 
            }
        }

        /* * [참고] Holding Torque 관련:
         * 동작 완료 후 모터 전원을 차단(Disable)하여 발열과 전력 소모를 줄임.
         * 만약 커튼 무게로 인해 모터가 꺼졌을 때 흘러내린다면 아래 줄을 주석 처리하여
         * 항상 Enable 상태(Holding Torque 유지)로 두어야 함.
         */
        en_write(false); 
        
        s_busy = false; // 동작 완료 상태로 변경
    }
}

/* -------------------- 공개 API -------------------- */

esp_err_t curtain_stepper_init(const em_StepperConfig *cfg)
{
    if (!cfg) return ESP_ERR_INVALID_ARG;
    s_cfg = *cfg;

    // GPIO 설정
    gpio_config_t io = {
        .mode = GPIO_MODE_OUTPUT,
        .pin_bit_mask = (1ULL << s_cfg.step_gpio) | (1ULL << s_cfg.dir_gpio),
    };
    if (s_cfg.en_gpio >= 0) io.pin_bit_mask |= (1ULL << s_cfg.en_gpio);
    ESP_ERROR_CHECK(gpio_config(&io));

    // 초기 상태 설정
    gpio_set_level(s_cfg.step_gpio, 0);
    gpio_set_level(s_cfg.dir_gpio, 0);
    if (s_cfg.en_gpio >= 0) en_write(false);

    // 명령 큐 생성
    s_cmd_q = xQueueCreate(STEPPER_QUEUE_LEN, sizeof(step_cmd_t));
    if (!s_cmd_q) return ESP_ERR_NO_MEM;

    // 모터 제어 태스크 생성 (우선순위 높음)
    xTaskCreate(stepper_task, "stepper_task", 4096, NULL, 10, &s_task);
    
    ESP_LOGI(TAG, "Initialized (STEP=%d, DIR=%d, EN=%d)", 
             s_cfg.step_gpio, s_cfg.dir_gpio, s_cfg.en_gpio);
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
    
    /* * Race Condition 방지:
     * 큐에 명령을 보내기 전에 미리 busy 상태로 설정함.
     * 만약 큐 전송 후 태스크가 깨어나기 전에 외부에서 상태를 확인하더라도
     * busy로 인식되게 하여 중복 명령을 방지함.
     */
    s_busy = true; 

    step_cmd_t cmd = {.steps = steps};
    if (xQueueSend(s_cmd_q, &cmd, 0) != pdTRUE) {
        s_busy = false; // 큐 전송 실패 시 busy 해제
        return ESP_ERR_INVALID_STATE;
    }
    return ESP_OK;
}

bool curtain_stepper_is_busy(void) { return s_busy; }

void curtain_stepper_stop(void) { s_stop = true; }