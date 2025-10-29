cmake_minimum_required(VERSION 3.16)
set(EXTRA_COMPONENT_DIRS ${CMAKE_SOURCE_DIR}/components)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32_dht11_example)

idf_build_get_property(project_dir PROJECT_DIR)
set(KCONFIG_PROJBUILD ${project_dir}/Kconfig.projbuild)