idf_component_register(
    SRCS "smart_curtain_main.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_event esp_netif mqtt json stepper
)