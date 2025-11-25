#include "mq135.h"
#include <math.h>
#include <string.h>
#include "esp_log.h"
#include "esp_adc/adc_cali_scheme.h"

static const char *TAG = "MQ135";

esp_err_t em_mq135_init(em_MQ135Ctx *ctx, adc_unit_t unit_id, adc_channel_t ch, 
                        adc_atten_t atten, int samples)
{
    if (!ctx) return ESP_ERR_INVALID_ARG;
    memset(ctx, 0, sizeof(*ctx));

    // ADC Unit Init
    adc_oneshot_unit_init_cfg_t ucfg = { .unit_id = unit_id };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &ctx->unit));

    // Channel Config
    adc_oneshot_chan_cfg_t ccfg = { .atten = atten, .bitwidth = ADC_BITWIDTH_DEFAULT };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(ctx->unit, ch, &ccfg));

    ctx->ch = ch;
    ctx->samples = samples;
    ctx->rl_kohm = 10.0f; // 기본값
    ctx->r0_kohm = 10.0f; // 기본값
    ctx->vref_mv = 1100;

    // Calibration (Curve Fitting)
    #if ADC_CALI_SCHEME_CURVE_FITTING_SUPPORTED
    adc_cali_curve_fitting_config_t cali_cfg = {
        .unit_id = unit_id,
        .atten = atten,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    if (adc_cali_create_scheme_curve_fitting(&cali_cfg, &ctx->cali) == ESP_OK) {
        ESP_LOGI(TAG, "Calibration Success (Curve Fitting)");
    }
    #endif

    return ESP_OK;
}

esp_err_t em_mq135_read(em_MQ135Ctx *ctx, em_MQ135Data *out)
{
    if (!ctx || !out) return ESP_ERR_INVALID_ARG;

    int total_raw = 0;
    for (int i = 0; i < ctx->samples; i++) {
        int raw = 0;
        adc_oneshot_read(ctx->unit, ctx->ch, &raw);
        total_raw += raw;
    }
    int avg_raw = total_raw / ctx->samples;

    int voltage_mv = 0;
    if (ctx->cali) {
        adc_cali_raw_to_voltage(ctx->cali, avg_raw, &voltage_mv);
    } else {
        voltage_mv = avg_raw * ctx->vref_mv / 4095; 
    }

    // 계산 로직
    float v_v = voltage_mv / 1000.0f;
    float rs = 0;
    if (voltage_mv > 0 && voltage_mv < 3300) { // 3.3V 기준
         rs = ctx->rl_kohm * (3.3f - v_v) / v_v;
    }
    
    // 단순 CO2 추정 (비정확할 수 있음, 참고용)
    float ratio = rs / ctx->r0_kohm;
    float ppm = 116.6020682f * pow(ratio, -2.769034857f);

    out->v_mv = (float)voltage_mv;
    out->rs_kohm = rs;
    out->co2eq_ppm = ppm;
    out->aq_index = (ppm > 1000) ? 200 : (ppm / 5.0f); // 임의 매핑

    return ESP_OK;
}