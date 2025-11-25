idf_component_register(
    SRCS "curtain_stepper.c"
    INCLUDE_DIRS "include"
    REQUIRES driver esp_timer freertos
)
