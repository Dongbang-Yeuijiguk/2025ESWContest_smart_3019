idf_component_register(
    SRCS "air_conditioner_main.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_event esp_netif mqtt json driver esp_timer dht22
)
