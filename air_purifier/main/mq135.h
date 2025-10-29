#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "hal/adc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float v_mv;     // 측정 전압 (mV)
    float rs_kohm;  // 센서 저항 (kΩ)
    float ratio;    // Rs/R0
    float aq_index; // 간이 공기질 지표(0~500)
    float co2eq_ppm;// 매우 거친 CO2eq 추정(ppm)
} em_MQ135Data;

typedef struct {
    adc_oneshot_unit_handle_t unit;
    adc_cali_handle_t cali;       // NULL이면 비보정(raw 사용)
    adc_channel_t ch;
    adc_atten_t atten;
    int vref_mv;                  // 보정 실패 시 추정 Vref
    float rl_kohm;                // 로드저항(kΩ)
    float r0_kohm;                // 청정공기 기준 R0(kΩ)
    int samples;                  // 평균 샘플 수
} em_MQ135Ctx;

esp_err_t em_mq135_init(em_MQ135Ctx *ctx,
                        adc_unit_t unit_id,
                        adc_channel_t ch,
                        adc_atten_t atten,
                        int samples,
                        float rl_kohm,
                        float r0_kohm,
                        int fallback_vref_mv);

esp_err_t em_mq135_read(em_MQ135Ctx *ctx, em_MQ135Data *out);
void em_mq135_task(void *arg);

#ifdef __cplusplus
}
#endif
