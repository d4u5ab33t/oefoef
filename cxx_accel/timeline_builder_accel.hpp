#pragma once
/**
 * timeline_builder_accel.hpp — Native High-Performance Clip Start Point & Boundary Snapping (C++20)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include <vector>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <random>
#include <cstring>

#ifdef _WIN32
  #define CXX_EXPORT __declspec(dllexport)
#else
  #define CXX_EXPORT __attribute__((visibility("default")))
#endif

namespace cxx_accel {

struct BlockedWindow {
    float start;
    float end;
};

/**
 * Checks if interval [start, start + seg_len] is completely free of blocked windows.
 */
inline bool is_interval_free(float start, float seg_len, const BlockedWindow* windows, size_t window_count) {
    float seg_end = start + seg_len;
    for (size_t i = 0; i < window_count; ++i) {
        if (start < windows[i].end && seg_end > windows[i].start) {
            return false;
        }
    }
    return true;
}

/**
 * High-speed C++ in-point finder for video clips with Anti-Repeat & bad-frame exclusion.
 */
inline float pick_start_point_native(
    float duration,
    float seg_len,
    const float* alt_starts,
    size_t alt_count,
    const BlockedWindow* windows,
    size_t window_count,
    uint32_t seed
) {
    constexpr float END_SAFETY_MARGIN = 0.30f;
    float max_start = duration - seg_len - END_SAFETY_MARGIN;
    if (max_start < 0.0f) {
        max_start = duration - seg_len;
        if (max_start < 0.0f) return -1.0f; // invalid duration
    }

    std::mt19937 rng(seed);

    // Fast path: no blocked windows
    if (!windows || window_count == 0) {
        if (alt_starts && alt_count > 0) {
            std::vector<float> free_alts;
            for (size_t i = 0; i < alt_count; ++i) {
                if (alt_starts[i] >= 0.0f && alt_starts[i] <= max_start) {
                    free_alts.push_back(alt_starts[i]);
                }
            }
            if (!free_alts.empty()) {
                std::uniform_int_distribution<size_t> dist(0, free_alts.size() - 1);
                return free_alts[dist(rng)];
            }
        }
        float step = std::max(seg_len * 0.75f, 0.50f);
        int32_t num_steps = static_cast<int32_t>(max_start / step);
        if (num_steps > 0) {
            std::uniform_int_distribution<int32_t> dist(0, num_steps);
            int32_t grid_idx = dist(rng);
            return std::min(static_cast<float>(grid_idx) * step, max_start);
        }
        return 0.0f;
    }

    // 1. Curated start points
    if (alt_starts && alt_count > 0) {
        std::vector<float> free_alts;
        for (size_t i = 0; i < alt_count; ++i) {
            float s = alt_starts[i];
            if (s >= 0.0f && s <= max_start && is_interval_free(s, seg_len, windows, window_count)) {
                free_alts.push_back(s);
            }
        }
        if (!free_alts.empty()) {
            std::uniform_int_distribution<size_t> dist(0, free_alts.size() - 1);
            return free_alts[dist(rng)];
        }
    }

    // 2. Candidate grid
    std::vector<float> candidates;
    candidates.reserve(window_count * 2 + 16);
    candidates.push_back(0.0f);
    candidates.push_back(max_start);

    for (size_t i = 0; i < window_count; ++i) {
        float b_start = windows[i].start;
        float b_end = windows[i].end;
        candidates.push_back(std::min(std::max(b_end, 0.0f), max_start));
        candidates.push_back(std::min(std::max(b_start - seg_len, 0.0f), max_start));
    }

    float step = std::max(seg_len * 0.75f, 0.50f);
    float grid = 0.0f;
    while (grid <= max_start) {
        candidates.push_back(grid);
        grid += step;
    }

    std::vector<float> free_candidates;
    for (float c : candidates) {
        if (c >= 0.0f && c <= max_start && is_interval_free(c, seg_len, windows, window_count)) {
            free_candidates.push_back(c);
        }
    }

    if (!free_candidates.empty()) {
        std::uniform_int_distribution<size_t> dist(0, free_candidates.size() - 1);
        return free_candidates[dist(rng)];
    }

    return -1.0f; // None found
}

/**
 * Fast batch beat, downbeat and transient snapping kernel.
 */
inline float snap_timeline_boundary_native(
    float t,
    float end,
    float seg_len,
    float target_duration,
    const float* drops,
    size_t drop_count,
    const float* downbeats,
    size_t downbeat_count,
    const float* beats,
    size_t beat_count,
    const float* drum_transients,
    size_t transient_count,
    float min_seg_sec,
    float transient_tolerance_sec,
    int32_t is_downbeat_preferred
) {
    float result = end;

    // 1. Check drops
    if (drops && drop_count > 0) {
        for (size_t i = 0; i < drop_count; ++i) {
            float drop = drops[i];
            if (drop >= t + 0.10f && drop <= t + seg_len + 0.40f) {
                if (std::abs(drop - end) < 0.50f) {
                    result = drop;
                    goto apply_transients;
                }
            }
        }
    }

    // 2. Downbeats / Beats
    if (is_downbeat_preferred && downbeats && downbeat_count > 0) {
        float closest = -1.0f;
        float min_diff = 1e9f;
        for (size_t i = 0; i < downbeat_count; ++i) {
            float db = downbeats[i];
            if (db >= t + min_seg_sec && db <= target_duration) {
                float diff = std::abs(db - end);
                if (diff < min_diff) {
                    min_diff = diff;
                    closest = db;
                }
            }
        }
        if (closest >= 0.0f && min_diff <= 0.28f) {
            result = closest;
            goto apply_transients;
        }
    }

    // Regular beats fallback
    if (beats && beat_count > 0) {
        float closest_b = -1.0f;
        float min_b_diff = 1e9f;
        for (size_t i = 0; i < beat_count; ++i) {
            float b = beats[i];
            if (b > t + 0.05f && b <= target_duration) {
                float diff = std::abs(b - end);
                if (diff < min_b_diff) {
                    min_b_diff = diff;
                    closest_b = b;
                }
            }
        }
        if (closest_b >= 0.0f) {
            result = std::max(closest_b, t + min_seg_sec);
        }
    }

apply_transients:
    // 3. Drum transient snap
    if (drum_transients && transient_count > 0) {
        float closest_tr = -1.0f;
        float min_tr_diff = 1e9f;
        for (size_t i = 0; i < transient_count; ++i) {
            float tr = drum_transients[i];
            if (tr >= t + min_seg_sec && tr <= target_duration) {
                float diff = std::abs(tr - result);
                if (diff < min_tr_diff) {
                    min_tr_diff = diff;
                    closest_tr = tr;
                }
            }
        }
        if (closest_tr >= 0.0f && min_tr_diff <= transient_tolerance_sec) {
            result = closest_tr;
        }
    }

    return result;
}

} // namespace cxx_accel

// C-ABI Exports
extern "C" {

CXX_EXPORT float cxx_pick_start_point(
    float duration,
    float seg_len,
    const float* alt_starts,
    int32_t alt_count,
    const cxx_accel::BlockedWindow* windows,
    int32_t window_count,
    uint32_t seed
) {
    return cxx_accel::pick_start_point_native(
        duration, seg_len,
        alt_starts, static_cast<size_t>(alt_count),
        windows, static_cast<size_t>(window_count),
        seed
    );
}

CXX_EXPORT float cxx_snap_timeline_boundary(
    float t,
    float end,
    float seg_len,
    float target_duration,
    const float* drops,
    int32_t drop_count,
    const float* downbeats,
    int32_t downbeat_count,
    const float* beats,
    int32_t beat_count,
    const float* drum_transients,
    int32_t transient_count,
    float min_seg_sec,
    float transient_tolerance_sec,
    int32_t is_downbeat_preferred
) {
    return cxx_accel::snap_timeline_boundary_native(
        t, end, seg_len, target_duration,
        drops, static_cast<size_t>(drop_count),
        downbeats, static_cast<size_t>(downbeat_count),
        beats, static_cast<size_t>(beat_count),
        drum_transients, static_cast<size_t>(transient_count),
        min_seg_sec, transient_tolerance_sec,
        is_downbeat_preferred
    );
}

}
