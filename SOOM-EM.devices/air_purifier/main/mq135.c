#include "sdkconfig.h"
#include "mq135.h"

#include <math.h>
#include <string.h>
#include "esp_log.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "driver/gpio.h"
#include "hal/gpio_types.h"

#define RELAY_GPIO     CONFIG_AP_RELAY_GPIO
#define AQ_THRESHOLD   CONFIG_AQ_THRESHOLD


static const char *TAG = "mq135";

static bool s_try_create_cali(adc_unit_t unit_id, adc_atten_t atten, adc_cali_handle_t *out)
{
    *out = NULL;
#if ADC_CALI_SCHEME_CURVE_FITTING_SUPPORTED
    adc_cali_handle_t handle = NULL;
    adc_cali_curve_fitting_config_t c = {
        .unit_id = unit_id,
        .atten = atten,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    if (adc_cali_create_scheme_curve_fitting(&c, &handle) == ESP_OK) {
        *out = handle;
        ESP_LOGI(TAG, "ADC calibration: curve fitting");
        return true;
    }
#endif
#if ADC_CALI_SCHEME_LINE_FITTING_SUPPORTED
    adc_cali_handle_t handle = NULL;
    adc_cali_line_fitting_config_t c = {
        .unit_id = unit_id,
        .atten = atten,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .default_vref = 1100,
    };
    if (adc_cali_create_scheme_line_fitting(&c, &handle) == ESP_OK) {
        *out = handle;
        ESP_LOGI(TAG, "ADC calibration: line fitting");
        return true;
    }
#endif
    ESP_LOGW(TAG, "ADC calibration not available (fallback to raw)");
    return false;
}

static float s_calc_rs_kohm(float vout_mv, float vs_mv, float rl_kohm)
{
    if (vout_mv < 1.0f) vout_mv = 1.0f;
    float ratio = vs_mv / vout_mv - 1.0f;
    if (ratio < 0.001f) ratio = 0.001f;
    return rl_kohm * ratio;
}

static float s_estimate_co2eq_ppm(float rs_r0)
{
    const float a = -1.45f;
    const float b = 1.90f;
    float logppm = a * log10f(rs_r0) + b;
    float ppm = powf(10.0f, logppm);
    if (ppm < 350.0f) ppm = 350.0f;   // 바닥 제한
    if (ppm > 5000.0f) ppm = 5000.0f; // 상한 제한
    return ppm;
}

static float s_aq_index_from_rs(float rs_r0)
{
    float x = rs_r0;
    if (x <= 0.3f) return 500.0f;
    if (x >= 3.6f) return 0.0f;
    float t = (3.6f - x) / (3.6f - 0.3f);
    return 500.0f * t;
}

esp_err_t em_mq135_init(em_MQ135Ctx *ctx,
                        adc_unit_t unit_id,
                        adc_channel_t ch,
                        adc_atten_t atten,
                        int samples,
                        float rl_kohm,
                        float r0_kohm,
                        int fallback_vref_mv)
{
    if (!ctx) return ESP_ERR_INVALID_ARG;
    memset(ctx, 0, sizeof(*ctx));

    adc_oneshot_unit_init_cfg_t ucfg = {
        .unit_id = unit_id,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &ctx->unit));

    adc_oneshot_chan_cfg_t ccfg = {
        .atten = atten,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(ctx->unit, ch, &ccfg));

    ctx->ch = ch;
    ctx->atten = atten;
    ctx->samples = (samples < 1) ? 1 : samples;
    ctx->rl_kohm = rl_kohm;
    ctx->r0_kohm = (r0_kohm <= 0.1f) ? 10.0f : r0_kohm;
    ctx->vref_mv = (fallback_vref_mv >= 900 && fallback_vref_mv <= 1300) ? fallback_vref_mv : 1100;

    if (!s_try_create_cali(unit_id, atten, &ctx->cali)) {
        ctx->cali = NULL; // fallback: raw 사용
    }
    return ESP_OK;
}

esp_err_t em_mq135_read(em_MQ135Ctx *ctx, em_MQ135Data *out)
{
    if (!ctx || !out) return ESP_ERR_INVALID_ARG;

    int acc_mv = 0;
    for (int i = 0; i < ctx->samples; ++i) {
        int raw = 0;
        ESP_ERROR_CHECK(adc_oneshot_read(ctx->unit, ctx->ch, &raw));
        int mv = 0;
        if (ctx->cali) {
            ESP_ERROR_CHECK(adc_cali_raw_to_voltage(ctx->cali, raw, &mv));
        } else {
            /* 매우 거친 추정: Vref*raw/4095 (C6 12bit) */
            mv = (ctx->vref_mv * raw) / 4095;
        }
        acc_mv += mv;
    }
    float v_mv = (float)acc_mv / (float)ctx->samples;

    float vs_mv = 5000.0f;

    float rs_kohm = s_calc_rs_kohm(v_mv, vs_mv, ctx->rl_kohm);
    float ratio = rs_kohm / ctx->r0_kohm;
    float co2eq = s_estimate_co2eq_ppm(ratio);
    float aqi = s_aq_index_from_rs(ratio);

    out->v_mv = v_mv;
    out->rs_kohm = rs_kohm;
    out->ratio = ratio;
    out->co2eq_ppm = co2eq;
    out->aq_index = aqi;
    return ESP_OK;
}

void em_mq135_task(void *arg)
{
    em_MQ135Ctx *ctx = (em_MQ135Ctx *)arg;
    em_MQ135Data d;
    float ema_ppm = -1.0f;
    const float alpha = 0.4f;
    bool relay_on = false;

    // --- 릴레이 핀 설정 ---
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << RELAY_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);
    gpio_set_level(RELAY_GPIO, 0);

    while (1) {
        if (em_mq135_read(ctx, &d) == ESP_OK) {
            if (ema_ppm < 0) ema_ppm = d.co2eq_ppm;
            else ema_ppm = alpha * d.co2eq_ppm + (1.0f - alpha) * ema_ppm;

            int aq = (int)(d.aq_index + 0.5f);

            ESP_LOGI("mq135",
                     "MQ135: V=%.0fmV Rs=%.1fkΩ ratio=%.2f AQ=%d CO2eq~%.0f (EMA %.0f)",
                     d.v_mv, d.rs_kohm, d.ratio, aq, d.co2eq_ppm, ema_ppm);

            // 히스테리시스(깜빡임 방지): 60 이상 ON, 45 이하 OFF
            const int on_th  = AQ_THRESHOLD + 10;
            const int off_th = AQ_THRESHOLD - 5;

            if (!relay_on && aq >= on_th) {
                gpio_set_level(RELAY_GPIO, 1);
                relay_on = true;
                ESP_LOGW("mq135", "Air Quality High! (AQ=%d) → Relay ON", aq);
            } else if (relay_on && aq <= off_th) {
                gpio_set_level(RELAY_GPIO, 0);
                relay_on = false;
                ESP_LOGI("mq135", "Air Quality Normal (AQ=%d) → Relay OFF", aq);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1500));
    }
}
