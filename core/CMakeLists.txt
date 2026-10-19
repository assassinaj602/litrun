cmake_minimum_required(VERSION 3.16)
project(litrun_core VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include_directories(include)

add_library(litrun_core SHARED
    fingerprint/fingerprint.c
    governor/governor.c
)

set_target_properties(litrun_core PROPERTIES
    OUTPUT_NAME "litrun_core"
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
)

add_executable(litrun-probe
    tools/probe_main.c
)
target_link_libraries(litrun-probe PRIVATE litrun_core)

enable_testing()

add_executable(test_fingerprint ../tests/core/test_fingerprint.c)
target_link_libraries(test_fingerprint PRIVATE litrun_core)
add_test(NAME test_fingerprint COMMAND test_fingerprint)

add_executable(test_governor ../tests/core/test_governor.c)
target_link_libraries(test_governor PRIVATE litrun_core)
add_test(NAME test_governor COMMAND test_governor)

