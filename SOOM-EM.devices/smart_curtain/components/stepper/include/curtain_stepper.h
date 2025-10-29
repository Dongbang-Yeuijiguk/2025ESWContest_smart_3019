#pragma once
#include <stdbool.h>
#include "esp_err.h"

/**
 * 커튼 스테퍼 드라이버 (A4988/TMC 계열)
 * WHY: 모터 구동 로직을 앱과 분리, 재사용 및 유지보수 용이
 */
typedef struct {
    int step_gpio;
    int dir_gpio;
    int en_gpio;
    int en_active_low;   // 1=LOW가 활성, 0=HIGH가 활성
    int dir_inverted;    // 방향 반전 필요 시 1
    int pulse_us;        // STEP 하이 펄스폭(us)
    int step_gap_us;     // 스텝 간 간격(us)
} em_StepperConfig;

esp_err_t curtain_stepper_init(const em_StepperConfig *cfg);
esp_err_t curtain_stepper_enable(bool enable);
esp_err_t curtain_stepper_move_steps(int32_t steps);
bool curtain_stepper_is_busy(void);
void curtain_stepper_stop(void);
