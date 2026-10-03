cmake_minimum_required(VERSION 3.16)
project(cxx_accel VERSION 2.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(MSVC)
    add_compile_options(/O2 /Oi /Ot /Gy /arch:AVX2 /fp:fast /W3)
else()
    add_compile_options(-O3 -march=native -ffast-math -Wall -Wextra -fPIC)
endif()

add_library(cxx_accel SHARED
    cxx_engine.cpp
    clip_matcher.hpp
    audio_dsp.hpp
)

set_target_properties(cxx_accel PROPERTIES
    OUTPUT_NAME "cxx_accel"
    PREFIX ""
)
