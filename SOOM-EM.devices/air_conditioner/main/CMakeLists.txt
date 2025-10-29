idf_component_register(
    SRCS "air_conditioner_main.c"
    INCLUDE_DIRS "."
    REQUIRES
        dht22
        json
        mqtt
        nvs_flash
        esp_event
        esp_netif
        esp_wifi
        driver
        esp_timer
        log
)
