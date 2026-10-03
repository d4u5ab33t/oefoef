cmake_minimum_required(VERSION 3.15)
project(oidasheim_slicer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}")

include_directories(include)

file(GLOB SOURCES
    "src/*.cpp"
)

add_executable(oidasheim_slicer ${SOURCES})

if(MSVC)
    target_compile_options(oidasheim_slicer PRIVATE /W4 /O2 /EHsc /utf-8)
else()
    target_compile_options(oidasheim_slicer PRIVATE -Wall -Wextra -O3)
endif()
