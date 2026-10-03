#pragma once
/**
 * timeline_director.hpp — High-Performance Native Timeline Directing & Rhythm Classification (C++20)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <unordered_set>

#ifdef _WIN32
  #define CXX_EXPORT __declspec(dllexport)
#else
  #define CXX_EXPORT __attribute__((visibility("default")))
#endif

namespace cxx_accel {

// Section label codes: 0=other, 1=low, 2=mid, 3=high
// Structure label codes: 0=other, 1=hook, 2=drop, 3=intro, 4=outro, 5=verse, 6=bridge

// Rhythm Pattern codes:
// 0=steady, 1=intro, 2=beat_drop, 3=expansion, 4=compression, 5=energy_surge,
// 6=buildup, 7=stutter_repeat, 8=peak, 9=dense_motion

// Sync Type codes:
// 0=polyrhythm, 1=snap_drop, 2=energy_peak, 3=breath, 4=on_beat, 5=syncopated

// Cut Style codes:
// 0=hard_cut, 1=fade_out, 2=jump_cut, 3=break, 4=push, 5=whip, 6=dissolve

struct TimelineSegmentInput {
    float start_sec;
    float end_sec;
    float target_energy;
    float information_density;
    float motion_direction;
    int32_t on_structure_boundary;
    int32_t repetition;
    int32_t section_code;    // 1=low, 2=mid, 3=high, 0=other
    int32_t structure_code;  // 1=hook, 2=drop, 0=other
    int64_t clip_hash;       // 64-bit hash for clip duplicate tracking
};

struct TimelineClassificationOutput {
    int32_t rhythm_pattern_code;
    int32_t sync_type_code;
    int32_t cut_style_code;
};

struct TimelineRewardOutput {
    float total_reward;
    float sync_score;
    float diversity_score;
    float semantic_score;
    float cuts_per_min;
    float avg_energy;
    int32_t is_hectic;
    int32_t unique_clips;
    int32_t consecutive_repeats;
};

inline void classify_timeline_native(
    const TimelineSegmentInput* segments,
    size_t count,
    TimelineClassificationOutput* out_results
) {
    if (!segments || !out_results || count == 0) return;

    // Constants matching main.py
    constexpr float RHYTHM_EXPANSION_RATIO = 1.8f;
    constexpr float RHYTHM_COMPRESSION_RATIO = 0.6f;
    constexpr float RHYTHM_ENERGY_SURGE = 0.8f;
    constexpr float RHYTHM_BUILDUP_ENERGY = 0.3f;
    constexpr float RHYTHM_DENSE_MOTION_DENSITY = 0.7f;

    constexpr float SYNC_SNAP_DROP_ENERGY = 0.85f;
    constexpr float SYNC_ON_BEAT_ENERGY = 0.75f;
    constexpr float SYNC_SYNCOPATED_ENERGY = 0.50f;

    constexpr size_t CUT_INTRO_SEGMENTS = 2;
    constexpr size_t CUT_OUTRO_SEGMENTS = 2;
    constexpr float CUT_JUMP_ENERGY_DELTA = 0.40f;
    constexpr float CUT_PUSH_ENERGY_DELTA = 0.20f;
    constexpr float CUT_WHIP_DENSITY = 0.60f;

    // First pass: Rhythm Pattern & Sync Type
    for (size_t i = 0; i < count; ++i) {
        const auto& seg = segments[i];

        // 1. Rhythm Pattern
        int32_t rhythm = 0; // steady
        if (i == 0) {
            rhythm = 1; // intro
        } else if (seg.on_structure_boundary) {
            rhythm = 2; // beat_drop
        } else {
            const auto& prev = segments[i - 1];
            float curr_dur = seg.end_sec - seg.start_sec;
            float prev_dur = prev.end_sec - prev.start_sec;
            float duration_ratio = curr_dur / (prev_dur + 0.001f);

            if (duration_ratio > RHYTHM_EXPANSION_RATIO) {
                rhythm = 3; // expansion
            } else if (duration_ratio < RHYTHM_COMPRESSION_RATIO) {
                rhythm = 4; // compression
            } else if (seg.target_energy > RHYTHM_ENERGY_SURGE) {
                rhythm = 5; // energy_surge
            } else if (seg.target_energy < RHYTHM_BUILDUP_ENERGY) {
                rhythm = 6; // buildup
            } else if (seg.repetition) {
                rhythm = 7; // stutter_repeat
            } else if ((seg.structure_code == 1 || seg.structure_code == 2) && seg.target_energy > 0.7f) {
                rhythm = 2; // beat_drop
            } else if (seg.section_code == 3) { // high
                rhythm = 8; // peak
            } else if (seg.information_density > RHYTHM_DENSE_MOTION_DENSITY) {
                rhythm = 9; // dense_motion
            } else {
                rhythm = 0; // steady
            }
        }

        // 2. Sync Type
        int32_t sync = 0; // polyrhythm
        float energy = seg.target_energy;
        if (seg.on_structure_boundary) {
            sync = 1; // snap_drop
        } else if (seg.section_code == 3) { // high
            sync = (energy > SYNC_SNAP_DROP_ENERGY) ? 1 : 2; // snap_drop : energy_peak
        } else if (seg.section_code == 1) { // low
            sync = 3; // breath
        } else if (energy > SYNC_ON_BEAT_ENERGY) {
            sync = 4; // on_beat
        } else if (energy > SYNC_SYNCOPATED_ENERGY) {
            sync = 5; // syncopated
        } else {
            sync = 0; // polyrhythm
        }

        out_results[i].rhythm_pattern_code = rhythm;
        out_results[i].sync_type_code = sync;
    }

    // Second pass: Cut Style (may depend on sync_type and next segment)
    for (size_t i = 0; i < count; ++i) {
        const auto& seg = segments[i];
        int32_t sync = out_results[i].sync_type_code;
        int32_t cut = 0; // hard_cut

        if (i < CUT_INTRO_SEGMENTS) {
            cut = 0; // hard_cut
        } else if (i >= (count > CUT_OUTRO_SEGMENTS ? count - CUT_OUTRO_SEGMENTS : 0)) {
            cut = 1; // fade_out
        } else if (seg.on_structure_boundary) {
            cut = 2; // jump_cut
        } else if (seg.repetition) {
            cut = 2; // jump_cut
        } else if (i + 1 >= count) {
            cut = 0; // hard_cut
        } else {
            const auto& next_seg = segments[i + 1];
            float energy_delta = next_seg.target_energy - seg.target_energy;
            if (energy_delta < -CUT_PUSH_ENERGY_DELTA) {
                cut = 3; // break
            } else if (energy_delta > CUT_JUMP_ENERGY_DELTA) {
                cut = 2; // jump_cut
            } else if (energy_delta > CUT_PUSH_ENERGY_DELTA) {
                cut = 4; // push
            } else if (next_seg.information_density > CUT_WHIP_DENSITY || std::abs(seg.motion_direction) >= 0.4f) {
                cut = 5; // whip
            } else if (seg.section_code == 1 && sync == 3) { // low & breath
                cut = 6; // dissolve
            } else {
                cut = 0; // hard_cut
            }
        }

        out_results[i].cut_style_code = cut;
    }
}

inline TimelineRewardOutput compute_reward_native(
    const TimelineSegmentInput* segments,
    size_t count,
    float semantic_score
) {
    if (!segments || count == 0) {
        return { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0 };
    }

    float total_duration = 0.0f;
    float sum_energy = 0.0f;
    int32_t consecutive_repeats = 0;

    std::vector<int64_t> hashes;
    hashes.reserve(count);

    for (size_t i = 0; i < count; ++i) {
        float dur = segments[i].end_sec - segments[i].start_sec;
        total_duration += dur;
        sum_energy += segments[i].target_energy;
        hashes.push_back(segments[i].clip_hash);

        if (i > 0 && segments[i].clip_hash == segments[i - 1].clip_hash) {
            consecutive_repeats++;
        }
    }

    if (total_duration <= 0.0f) {
        return { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0 };
    }

    float cut_density = static_cast<float>(count) / (total_duration / 60.0f);
    float avg_energy = sum_energy / static_cast<float>(count);

    bool is_hectic = (cut_density > 120.0f && avg_energy < 0.40f);
    float sync_score = is_hectic ? 0.40f : 0.90f;

    std::sort(hashes.begin(), hashes.end());
    auto last = std::unique(hashes.begin(), hashes.end());
    size_t unique_count = std::distance(hashes.begin(), last);

    float unique_ratio = static_cast<float>(unique_count) / static_cast<float>(count);
    float repeat_penalty = (static_cast<float>(consecutive_repeats) / static_cast<float>(count)) * 0.50f;
    float diversity_score = std::max(0.0f, unique_ratio - repeat_penalty);

    float reward = (0.35f * sync_score) + (0.35f * diversity_score) + (0.30f * semantic_score);
    reward = std::max(0.0f, std::min(1.0f, reward));

    return {
        reward,
        sync_score,
        diversity_score,
        semantic_score,
        cut_density,
        avg_energy,
        is_hectic ? 1 : 0,
        static_cast<int32_t>(unique_count),
        consecutive_repeats
    };
}

} // namespace cxx_accel

// C-ABI Exports
extern "C" {

CXX_EXPORT void cxx_classify_timeline(
    const cxx_accel::TimelineSegmentInput* segments,
    int32_t count,
    cxx_accel::TimelineClassificationOutput* out_results
) {
    if (segments && out_results && count > 0) {
        cxx_accel::classify_timeline_native(segments, static_cast<size_t>(count), out_results);
    }
}

CXX_EXPORT void cxx_compute_timeline_reward(
    const cxx_accel::TimelineSegmentInput* segments,
    int32_t count,
    float semantic_score,
    cxx_accel::TimelineRewardOutput* out_reward
) {
    if (segments && out_reward && count > 0) {
        *out_reward = cxx_accel::compute_reward_native(segments, static_cast<size_t>(count), semantic_score);
    }
}

}
