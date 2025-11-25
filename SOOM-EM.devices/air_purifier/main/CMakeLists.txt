idf_component_register(
    SRCS "air_purifier_main.c" "pms7003.c" "mq135.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_event esp_netif mqtt json driver esp_adc esp_timer
)
