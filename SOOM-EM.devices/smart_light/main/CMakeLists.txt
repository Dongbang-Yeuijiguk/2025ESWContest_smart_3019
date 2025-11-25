idf_component_register(
    SRCS "smart_light_main.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_event esp_netif mqtt json led_strip driver esp_timer
)