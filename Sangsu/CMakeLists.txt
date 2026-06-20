cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(save_my_refrigerator C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

# Read .env file if it exists and define compiler macros
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.env")
    file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/.env" ENV_LINES)
    foreach(line ${ENV_LINES})
        # Ignore comments and empty lines
        if(NOT line MATCHES "^#" AND line MATCHES "=")
            string(REPLACE "=" ";" line_split ${line})
            list(GET line_split 0 key)
            list(GET line_split 1 val)
            # Remove any wrapping quotes from val
            string(REGEX REPLACE "^\"|\"$" "" val "${val}")
            # Register the definition as a compiler preprocessor macro
            add_compile_definitions(${key}="${val}")
        endif()
    endforeach()
endif()

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
