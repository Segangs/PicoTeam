cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(save_my_refrigerator C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(save_my_refrigerator
    src/main.cpp
)

target_include_directories(save_my_refrigerator PRIVATE
    src
)

target_link_libraries(save_my_refrigerator
    pico_stdlib
    pico_rand
    pico_cyw43_arch_lwip_threadsafe_background
    pico_lwip_mbedtls
    pico_mbedtls
)

pico_enable_stdio_usb(save_my_refrigerator 1)
pico_enable_stdio_uart(save_my_refrigerator 1)

pico_add_extra_outputs(save_my_refrigerator)
