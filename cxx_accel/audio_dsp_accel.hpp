#pragma once
/**
 * audio_dsp_accel.hpp — Native High-Speed Audio Signal Processing & Beatgrid DSP (C++20)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include <vector>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <cstring>

#ifdef _WIN32
  #define CXX_EXPORT __declspec(dllexport)
#else
  #define CXX_EXPORT __attribute__((visibility("default")))
#endif

namespace cxx_accel {

/**
 * Fast Moving Root Mean Square (RMS) energy calculation over PCM float32 samples.
 */
inline void compute_moving_rms_native(
    const float* pcm_samples,
    size_t sample_count,
    int32_t hop_size,
    int32_t frame_size,
    float* out_rms,
    size_t out_frames
) {
    if (!pcm_samples || !out_rms || sample_count == 0 || hop_size <= 0 || frame_size <= 0 || out_frames == 0) {
        return;
    }

    for (size_t f = 0; f < out_frames; ++f) {
        size_t start = f * hop_size;
        if (start >= sample_count) {
            out_rms[f] = 0.0f;
            continue;
        }
        size_t end = std::min(start + frame_size, sample_count);
        float sum_sq = 0.0f;
        for (size_t i = start; i < end; ++i) {
            sum_sq += pcm_samples[i] * pcm_samples[i];
        }
        size_t n = end - start;
        out_rms[f] = (n > 0) ? std::sqrt(sum_sq / static_cast<float>(n)) : 0.0f;
    }
}

/**
 * Vectorized Gaussian-like Moving Window Smooth on 1D Energy/Tension curves.
 */
inline void smooth_curve_native(
    const float* input,
    size_t length,
    int32_t window_size,
    float* out_smoothed
) {
    if (!input || !out_smoothed || length == 0) return;
    int32_t half_w = std::max(1, window_size / 2);

    for (size_t i = 0; i < length; ++i) {
        int64_t start = std::max<int64_t>(0, static_cast<int64_t>(i) - half_w);
        int64_t end = std::min<int64_t>(static_cast<int64_t>(length), static_cast<int64_t>(i) + half_w + 1);
        float sum = 0.0f;
        for (int64_t j = start; j < end; ++j) {
            sum += input[j];
        }
        out_smoothed[i] = sum / static_cast<float>(end - start);
    }
}

/**
 * Native Onset / Energy Peak Picker with Adaptive Thresholding and refractory window.
 */
inline int32_t detect_energy_peaks_native(
    const float* energy,
    size_t length,
    float threshold,
    int32_t min_distance,
    int32_t* out_peaks,
    int32_t max_peaks
) {
    if (!energy || !out_peaks || length < 3 || max_peaks <= 0) return 0;

    int32_t peak_count = 0;
    int32_t last_peak_idx = -min_distance;

    for (size_t i = 1; i < length - 1; ++i) {
        if (energy[i] > threshold &&
            energy[i] > energy[i - 1] &&
            energy[i] > energy[i + 1]) {
            if (static_cast<int32_t>(i) - last_peak_idx >= min_distance) {
                out_peaks[peak_count++] = static_cast<int32_t>(i);
                last_peak_idx = static_cast<int32_t>(i);
                if (peak_count >= max_peaks) break;
            }
        }
    }
    return peak_count;
}

/**
 * Dynamic Beatgrid Quantizer: snaps raw detected beat timestamps onto regular tempo grid intervals.
 */
inline void quantize_beatgrid_native(
    const float* raw_beats,
    size_t beat_count,
    float bpm,
    float tolerance_sec,
    float* out_quantized
) {
    if (!raw_beats || !out_quantized || beat_count == 0 || bpm <= 0.0f) return;
    float beat_interval = 60.0f / bpm;

    for (size_t i = 0; i < beat_count; ++i) {
        float t = raw_beats[i];
        float nearest_grid_idx = std::round(t / beat_interval);
        float grid_time = nearest_grid_idx * beat_interval;
        if (std::abs(t - grid_time) <= tolerance_sec) {
            out_quantized[i] = grid_time;
        } else {
            out_quantized[i] = t;
        }
    }
}

} // namespace cxx_accel

extern "C" {

CXX_EXPORT void cxx_compute_moving_rms(
    const float* pcm_samples,
    int32_t sample_count,
    int32_t hop_size,
    int32_t frame_size,
    float* out_rms,
    int32_t out_frames
) {
    cxx_accel::compute_moving_rms_native(
        pcm_samples, static_cast<size_t>(sample_count),
        hop_size, frame_size, out_rms, static_cast<size_t>(out_frames)
    );
}

CXX_EXPORT void cxx_smooth_energy_curve(
    const float* input,
    int32_t length,
    int32_t window_size,
    float* out_smoothed
) {
    cxx_accel::smooth_curve_native(input, static_cast<size_t>(length), window_size, out_smoothed);
}

CXX_EXPORT int32_t cxx_detect_energy_peaks(
    const float* energy,
    int32_t length,
    float threshold,
    int32_t min_distance,
    int32_t* out_peaks,
    int32_t max_peaks
) {
    return cxx_accel::detect_energy_peaks_native(
        energy, static_cast<size_t>(length),
        threshold, min_distance, out_peaks, max_peaks
    );
}

CXX_EXPORT void cxx_quantize_beatgrid(
    const float* raw_beats,
    int32_t beat_count,
    float bpm,
    float tolerance_sec,
    float* out_quantized
) {
    cxx_accel::quantize_beatgrid_native(
        raw_beats, static_cast<size_t>(beat_count),
        bpm, tolerance_sec, out_quantized
    );
}

}
