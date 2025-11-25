#pragma once

#include <stdint.h>
#include "esp_err.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float v_mv;      // 측정 전압 (mV)
    float rs_kohm;   // 센서 저항
    float co2eq_ppm; // CO2 환산 농도 (추정치)
    float aq_index;  // AQI 인덱스
} em_MQ135Data;

typedef struct {
    adc_oneshot_unit_handle_t unit;
    adc_cali_handle_t cali;
    adc_channel_t ch;
    int samples;
    float rl_kohm;
    float r0_kohm;
    int vref_mv;
} em_MQ135Ctx;

esp_err_t em_mq135_init(em_MQ135Ctx *ctx, adc_unit_t unit_id, adc_channel_t ch, 
                        adc_atten_t atten, int samples);

esp_err_t em_mq135_read(em_MQ135Ctx *ctx, em_MQ135Data *out);

#ifdef __cplusplus
}
#endif