#pragma once
/**
 * fast_scene_optimizer.hpp — Native C++ Scene Optimization & Harmony Scoring
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

struct ShotMetric {
    int32_t index;
    float duration;
    float energy;
    float sync_score;
    float flow_score;
    int32_t clip_hash;
};

struct SceneEvaluation {
    float overall_quality;
    float average_flow;
    float average_sync;
    float duplicate_penalty;
    float cuts_per_minute;
    int32_t unique_clips;
    int32_t rating_code; // 2=EXCELLENT, 1=BALANCED, 0=SUBOPTIMAL
};

inline SceneEvaluation evaluate_scene_timeline(
    const ShotMetric* shots,
    size_t shot_count,
    float total_duration_sec,
    float target_energy_avg
) {
    if (!shots || shot_count == 0 || total_duration_sec <= 0.0f) {
        return { 0.5f, 0.5f, 0.5f, 0.0f, 0.0f, 0, 1 };
    }

    float cuts_per_min = static_cast<float>(shot_count) / (total_duration_sec / 60.0f);
    
    // Check duplicates
    std::vector<int32_t> hashes;
    hashes.reserve(shot_count);
    float sum_flow = 0.0f;
    float sum_sync = 0.0f;

    for (size_t i = 0; i < shot_count; ++i) {
        hashes.push_back(shots[i].clip_hash);
        sum_flow += shots[i].flow_score;
        sum_sync += shots[i].sync_score;
    }

    std::sort(hashes.begin(), hashes.end());
    auto last = std::unique(hashes.begin(), hashes.end());
    size_t unique_count = std::distance(hashes.begin(), last);

    float duplicate_ratio = 1.0f - (static_cast<float>(unique_count) / static_cast<float>(shot_count));
    float duplicate_penalty = duplicate_ratio * 0.40f;

    float avg_flow = sum_flow / static_cast<float>(shot_count);
    float avg_sync = sum_sync / static_cast<float>(shot_count);

    // Flow heuristic: hectic cutting during quiet passages
    if (cuts_per_min > 42.0f && target_energy_avg < 0.45f) {
        avg_flow = std::max(0.1f, avg_flow - 0.30f);
    }

    // Weighted multi-reward calculation
    float quality = (0.50f * avg_sync) + (0.35f * avg_flow) - (0.15f * duplicate_penalty);
    quality = std::max(0.0f, std::min(1.0f, quality));

    int32_t rating = (quality >= 0.80f) ? 2 : ((quality >= 0.60f) ? 1 : 0);

    return {
        quality,
        avg_flow,
        avg_sync,
        duplicate_penalty,
        cuts_per_min,
        static_cast<int32_t>(unique_count),
        rating
    };
}

} // namespace cxx_accel

extern "C" {

CXX_EXPORT void cxx_evaluate_scene(
    const cxx_accel::ShotMetric* shots,
    int32_t shot_count,
    float total_duration_sec,
    float target_energy_avg,
    cxx_accel::SceneEvaluation* out_eval
) {
    if (shots && out_eval && shot_count > 0) {
        *out_eval = cxx_accel::evaluate_scene_timeline(
            shots, static_cast<size_t>(shot_count), total_duration_sec, target_energy_avg
        );
    }
}

}
