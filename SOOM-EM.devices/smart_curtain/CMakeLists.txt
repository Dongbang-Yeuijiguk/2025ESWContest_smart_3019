cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(smart_curtain)

idf_build_get_property(project_dir PROJECT_DIR)
set(KCONFIG_PROJBUILD ${project_dir}/Kconfig.projbuild)