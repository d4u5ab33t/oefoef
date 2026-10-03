#pragma once
/**
 * audio_dsp.hpp — Native High-Performance Audio DSP & Beat Alignment (C++20)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include <vector>
#include <cmath>
#include <algorithm>
#include <cstdint>

#ifdef _WIN32
  #define CXX_EXPORT __declspec(dllexport)
#else
  #define CXX_EXPORT __attribute__((visibility("default")))
#endif

namespace cxx_accel {

/**
 * Binary search for closest beat timestamp in an ascending beat array.
 */
inline float snap_to_beat(float target_time, const float* beat_times, size_t count, float tolerance_sec = 0.12f) {
    if (!beat_times || count == 0) return target_time;
    
    // std::lower_bound
    auto it = std::lower_bound(beat_times, beat_times + count, target_time);
    if (it == beat_times + count) {
        float last = beat_times[count - 1];
        return (std::abs(target_time - last) <= tolerance_sec) ? last : target_time;
    }
    if (it == beat_times) {
        return (std::abs(target_time - *it) <= tolerance_sec) ? *it : target_time;
    }

    float b_after = *it;
    float b_before = *(it - 1);
    float d_after = std::abs(target_time - b_after);
    float d_before = std::abs(target_time - b_before);

    if (d_before <= d_after && d_before <= tolerance_sec) return b_before;
    if (d_after <= tolerance_sec) return b_after;
    return target_time;
}

/**
 * Fast batch beat quantization for timeline boundaries.
 */
inline void batch_snap_boundaries(
    const float* cut_times,
    size_t cut_count,
    const float* beat_times,
    size_t beat_count,
    float tolerance_sec,
    float* out_snapped
) {
    if (!cut_times || !out_snapped || cut_count == 0) return;
    for (size_t i = 0; i < cut_count; ++i) {
        out_snapped[i] = snap_to_beat(cut_times[i], beat_times, beat_count, tolerance_sec);
    }
}

/**
 * Fast matrix self-similarity repetition detector for audio onset vectors.
 */
inline int32_t detect_repetition_windows(
    const float* onsets,
    size_t onset_count,
    float window_sec,
    float rate_threshold,
    float* out_rep_starts,
    float* out_rep_ends,
    int32_t max_windows
) {
    if (!onsets || onset_count < 2 || !out_rep_starts || !out_rep_ends || max_windows <= 0) return 0;

    int32_t found = 0;
    size_t left = 0;

    for (size_t right = 0; right < onset_count; ++right) {
        while (left < right && (onsets[right] - onsets[left]) > window_sec) {
            left++;
        }
        size_t count_in_win = right - left + 1;
        float rate = static_cast<float>(count_in_win) / std::max(0.01f, window_sec);

        if (rate >= rate_threshold && found < max_windows) {
            float start = onsets[left];
            float end = onsets[right];
            // Merge with previous window if overlapping
            if (found > 0 && start <= out_rep_ends[found - 1] + 0.1f) {
                out_rep_ends[found - 1] = std::max(out_rep_ends[found - 1], end);
            } else {
                out_rep_starts[found] = start;
                out_rep_ends[found] = end;
                found++;
            }
        }
    }
    return found;
}

/**
 * High-density drum accent and roll burst detector with peak density scoring.
 */
inline int32_t detect_accent_repetitions(
    const float* onsets,
    size_t onset_count,
    float window_sec,
    float rate_threshold,
    float* out_starts,
    float* out_ends,
    float* out_densities,
    int32_t max_windows
) {
    if (!onsets || onset_count < 2 || !out_starts || !out_ends || !out_densities || max_windows <= 0) return 0;

    int32_t found = 0;
    size_t left = 0;

    for (size_t right = 0; right < onset_count; ++right) {
        while (left < right && (onsets[right] - onsets[left]) > window_sec) {
            left++;
        }
        size_t count_in_win = right - left + 1;
        float rate = static_cast<float>(count_in_win) / std::max(0.01f, window_sec);

        if (rate >= rate_threshold && found < max_windows) {
            float start = onsets[left];
            float end = onsets[right];
            if (found > 0 && start <= out_ends[found - 1] + 0.12f) {
                out_ends[found - 1] = std::max(out_ends[found - 1], end);
                out_densities[found - 1] = std::max(out_densities[found - 1], rate);
            } else {
                out_starts[found] = start;
                out_ends[found] = end;
                out_densities[found] = rate;
                found++;
            }
        }
    }
    return found;
}

/**
 * Micro-cut slicer for drum roll stutter/burst zones.
 * Slices a segment into rapid rhythmically-synced sub-intervals at drum onset points.
 */
inline int32_t slice_drum_roll(
    float seg_start,
    float seg_end,
    const float* onsets,
    size_t onset_count,
    float min_slice_sec,
    int32_t max_slices,
    float* out_slice_cuts
) {
    if (!onsets || onset_count == 0 || !out_slice_cuts || max_slices <= 1) return 0;
    if (seg_end <= seg_start + min_slice_sec * 1.5f) return 0;

    // Find all onsets strictly inside (seg_start + min_slice_sec, seg_end - min_slice_sec)
    auto it_begin = std::lower_bound(onsets, onsets + onset_count, seg_start + min_slice_sec);
    auto it_end = std::lower_bound(onsets, onsets + onset_count, seg_end - min_slice_sec);

    int32_t slice_count = 0;
    float last_cut = seg_start;

    for (auto it = it_begin; it != it_end && slice_count < (max_slices - 1); ++it) {
        float candidate = *it;
        if ((candidate - last_cut) >= min_slice_sec && (seg_end - candidate) >= min_slice_sec) {
            out_slice_cuts[slice_count++] = candidate;
            last_cut = candidate;
        }
    }
    return slice_count;
}

} // namespace cxx_accel

// C-ABI Exports for Python ctypes/cffi
extern "C" {

CXX_EXPORT void cxx_batch_snap_beats(
    const float* cut_times,
    int32_t cut_count,
    const float* beat_times,
    int32_t beat_count,
    float tolerance_sec,
    float* out_snapped
) {
    cxx_accel::batch_snap_boundaries(
        cut_times, static_cast<size_t>(cut_count),
        beat_times, static_cast<size_t>(beat_count),
        tolerance_sec, out_snapped
    );
}

CXX_EXPORT void cxx_batch_snap_transients(
    const float* cut_times,
    int32_t cut_count,
    const float* transient_times,
    int32_t transient_count,
    float tolerance_sec,
    float* out_snapped
) {
    cxx_accel::batch_snap_boundaries(
        cut_times, static_cast<size_t>(cut_count),
        transient_times, static_cast<size_t>(transient_count),
        tolerance_sec, out_snapped
    );
}

CXX_EXPORT int32_t cxx_detect_repetition_zones(
    const float* onsets,
    int32_t onset_count,
    float window_sec,
    float rate_threshold,
    float* out_rep_starts,
    float* out_rep_ends,
    int32_t max_windows
) {
    return cxx_accel::detect_repetition_windows(
        onsets, static_cast<size_t>(onset_count),
        window_sec, rate_threshold,
        out_rep_starts, out_rep_ends, max_windows
    );
}

CXX_EXPORT int32_t cxx_detect_accent_repetitions(
    const float* onsets,
    int32_t onset_count,
    float window_sec,
    float rate_threshold,
    float* out_starts,
    float* out_ends,
    float* out_densities,
    int32_t max_windows
) {
    return cxx_accel::detect_accent_repetitions(
        onsets, static_cast<size_t>(onset_count),
        window_sec, rate_threshold,
        out_starts, out_ends, out_densities, max_windows
    );
}

CXX_EXPORT int32_t cxx_slice_drum_roll(
    float seg_start,
    float seg_end,
    const float* onsets,
    int32_t onset_count,
    float min_slice_sec,
    int32_t max_slices,
    float* out_slice_cuts
) {
    return cxx_accel::slice_drum_roll(
        seg_start, seg_end,
        onsets, static_cast<size_t>(onset_count),
        min_slice_sec, max_slices,
        out_slice_cuts
    );
}

}

