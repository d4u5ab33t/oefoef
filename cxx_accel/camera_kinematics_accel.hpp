#pragma once
/**
 * camera_kinematics_accel.hpp — SIMD Camera Motion, Trajectories & 2.5D Parallax for OIDASHEIM
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include "clip_matcher.hpp"
#include <vector>
#include <cmath>
#include <algorithm>
#include <cstdint>

namespace cxx_accel {

constexpr float PI = 3.14159265358979323846f;

inline float smoothstep(float edge0, float edge1, float x) {
    float t = std::clamp((x - edge0) / std::max(1e-6f, edge1 - edge0), 0.0f, 1.0f);
    return t * t * (3.0f - 2.0f * t);
}

inline float lerp(float a, float b, float t) {
    return a + t * (b - a);
}

} // namespace cxx_accel

extern "C" {

CXX_EXPORT void cxx_kinematics_sample_trajectory(
    const float* kf_times,
    const float* kf_scales,
    const float* kf_pan_x,
    const float* kf_pan_y,
    const float* kf_rot,
    const float* kf_focal,
    int32_t num_keyframes,
    const float* sample_times,
    int32_t num_samples,
    float* out_scales,
    float* out_pan_x,
    float* out_pan_y,
    float* out_rot,
    float* out_focal
) {
    if (!kf_times || num_keyframes <= 0 || !sample_times || num_samples <= 0) return;

    for (int32_t s = 0; s < num_samples; ++s) {
        float t = sample_times[s];

        if (num_keyframes == 1 || t <= kf_times[0]) {
            if (out_scales) out_scales[s] = kf_scales[0];
            if (out_pan_x) out_pan_x[s] = kf_pan_x[0];
            if (out_pan_y) out_pan_y[s] = kf_pan_y[0];
            if (out_rot) out_rot[s] = kf_rot ? kf_rot[0] : 0.0f;
            if (out_focal) out_focal[s] = kf_focal ? kf_focal[0] : 35.0f;
            continue;
        }

        if (t >= kf_times[num_keyframes - 1]) {
            int32_t last = num_keyframes - 1;
            if (out_scales) out_scales[s] = kf_scales[last];
            if (out_pan_x) out_pan_x[s] = kf_pan_x[last];
            if (out_pan_y) out_pan_y[s] = kf_pan_y[last];
            if (out_rot) out_rot[s] = kf_rot ? kf_rot[last] : 0.0f;
            if (out_focal) out_focal[s] = kf_focal ? kf_focal[last] : 35.0f;
            continue;
        }

        for (int32_t i = 0; i < num_keyframes - 1; ++i) {
            float t1 = kf_times[i];
            float t2 = kf_times[i + 1];
            if (t >= t1 && t <= t2) {
                float factor = (t - t1) / std::max(1e-6f, t2 - t1);

                if (out_scales) out_scales[s] = cxx_accel::lerp(kf_scales[i], kf_scales[i + 1], factor);
                if (out_pan_x) out_pan_x[s] = cxx_accel::lerp(kf_pan_x[i], kf_pan_x[i + 1], factor);
                if (out_pan_y) out_pan_y[s] = cxx_accel::lerp(kf_pan_y[i], kf_pan_y[i + 1], factor);
                if (out_rot) out_rot[s] = kf_rot ? cxx_accel::lerp(kf_rot[i], kf_rot[i + 1], factor) : 0.0f;
                if (out_focal) out_focal[s] = kf_focal ? cxx_accel::lerp(kf_focal[i], kf_focal[i + 1], factor) : 35.0f;
                break;
            }
        }
    }
}

CXX_EXPORT void cxx_kinematics_fake_3d_warp(
    float t,
    float duration,
    float width,
    float height,
    float pitch_deg,
    float yaw_deg,
    float* out_coords_8 // [x0, y0, x1, y1, x2, y2, x3, y3]
) {
    if (!out_coords_8 || duration <= 0.0f) return;

    float dur = std::max(0.1f, duration);
    float phase = std::sin(cxx_accel::PI * t / dur);

    float shift_x = yaw_deg * 8.0f * phase;
    float shift_y = pitch_deg * 4.0f * phase;

    // Perspective trapezoid corners (top-left, top-right, bottom-left, bottom-right)
    out_coords_8[0] = shift_x;                       // x0
    out_coords_8[1] = shift_y;                       // y0
    out_coords_8[2] = width - shift_x;               // x1
    out_coords_8[3] = -shift_y;                      // y1
    out_coords_8[4] = -shift_x * 0.5f;               // x2
    out_coords_8[5] = height + shift_y;              // y2
    out_coords_8[6] = width + shift_x * 0.5f;        // x3
    out_coords_8[7] = height - shift_y;              // y3
}

CXX_EXPORT void cxx_generate_camera_path(
    float start_zoom,
    float end_zoom,
    float start_pan_x,
    float end_pan_x,
    float start_pan_y,
    float end_pan_y,
    int32_t frame_count,
    int32_t easing_type,
    float* out_zoom,
    float* out_x,
    float* out_y
) {
    if (!out_zoom || !out_x || !out_y || frame_count <= 0) return;

    for (int32_t i = 0; i < frame_count; ++i) {
        float t = (frame_count > 1) ? (static_cast<float>(i) / static_cast<float>(frame_count - 1)) : 0.0f;
        float factor = t;

        if (easing_type == 1) { // Ease-in
            factor = t * t;
        } else if (easing_type == 2) { // Ease-out
            factor = 1.0f - (1.0f - t) * (1.0f - t);
        } else if (easing_type == 3) { // Ease-in-out / smoothstep
            factor = cxx_accel::smoothstep(0.0f, 1.0f, t);
        } else if (easing_type == 4) { // Cubic
            factor = t * t * (3.0f - 2.0f * t);
        } else if (easing_type == 5) { // Spring / Elastic
            factor = 1.0f - std::exp(-5.0f * t) * std::cos(10.0f * t);
        }

        out_zoom[i] = cxx_accel::lerp(start_zoom, end_zoom, factor);
        out_x[i] = cxx_accel::lerp(start_pan_x, end_pan_x, factor);
        out_y[i] = cxx_accel::lerp(start_pan_y, end_pan_y, factor);
    }
}

} // extern "C"

