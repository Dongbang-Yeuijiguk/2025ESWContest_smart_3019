#pragma once

#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

// 반환 코드
#define DHT_OK              (0)
#define DHT_TIMEOUT_ERROR   (-1)
#define DHT_CHECKSUM_ERROR  (-2)
#define DHT_BUS_HUNG        (-3)

// DHT 사용 GPIO 지정
void  setDHTgpio(gpio_num_t gpio);

// 센서 1회 읽기 (성공: DHT_OK, 실패: 음수)
int   readDHT(void);

// 마지막으로 읽은 값 반환
float getHumidity(void);
float getTemperature(void);

// 에러코드 로그 출력용(선택 사용)
void  errorHandler(int response);

#ifdef __cplusplus
}
#endif
