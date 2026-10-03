#pragma once
/**
 * clip_matcher.hpp — Native High-Performance Clip Scoring & Vector Search (C++20)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <cstdint>

#ifdef _WIN32
  #define CXX_EXPORT __declspec(dllexport)
#else
  #define CXX_EXPORT __attribute__((visibility("default")))
#endif

namespace cxx_accel {

struct ClipCandidate {
    int32_t id;
    float duration;
    float motion_score;
    float motion_direction;
    float face_score;
    float semantic_match;
    float pref_bonus;
    float info_density;
    float learned_bonus;
    int32_t is_still;
};

struct ScoringContext {
    float target_energy;
    float target_duration;
    float motion_weight;
    float semantic_weight;
    float pref_weight;
    float density_weight;
    float prev_motion_dir;
    int32_t allow_still;
    int32_t check_motion_continuity;
};

struct MatchResult {
    int32_t clip_id;
    float final_score;
    float semantic_component;
    float energy_component;
    float continuity_bonus;
};

/**
 * High-performance vectorized Cosine Similarity between two float vectors.
 */
inline float cosine_similarity(const float* a, const float* b, size_t dim) {
    if (!a || !b || dim == 0) return 0.0f;
    float dot = 0.0f, norm_a = 0.0f, norm_b = 0.0f;
    for (size_t i = 0; i < dim; ++i) {
        dot += a[i] * b[i];
        norm_a += a[i] * a[i];
        norm_b += b[i] * b[i];
    }
    float denom = std::sqrt(norm_a) * std::sqrt(norm_b);
    return (denom > 1e-7f) ? (dot / denom) : 0.0f;
}

/**
 * Score a batch of candidates in native C++ with SIMD/cache-friendly layout.
 */
inline void score_clip_batch(
    const ClipCandidate* candidates,
    size_t count,
    const ScoringContext& ctx,
    MatchResult* results
) {
    if (!candidates || !results || count == 0) return;

    for (size_t i = 0; i < count; ++i) {
        const auto& c = candidates[i];
        
        // Filter out duration mismatch
        if (c.duration < ctx.target_duration && c.duration > 0.01f) {
            results[i] = { c.id, -1000.0f, 0.0f, 0.0f, 0.0f };
            continue;
        }

        // Filter still frames if not allowed
        if (c.is_still && !ctx.allow_still) {
            results[i] = { c.id, -999.0f, 0.0f, 0.0f, 0.0f };
            continue;
        }

        // Energy distance
        float energy_delta = std::abs(c.motion_score - ctx.target_energy);
        float energy_score = 1.0f - std::min(1.0f, energy_delta * 1.5f);

        // Motion flow continuity
        float continuity_bonus = 0.0f;
        if (ctx.check_motion_continuity && std::abs(ctx.prev_motion_dir) > 0.1f) {
            if ((ctx.prev_motion_dir > 0.0f && c.motion_direction > 0.0f) ||
                (ctx.prev_motion_dir < 0.0f && c.motion_direction < 0.0f)) {
                continuity_bonus = 0.08f;
            }
        }

        float total = (ctx.semantic_weight * c.semantic_match)
                    + (ctx.motion_weight * energy_score)
                    + (ctx.pref_weight * c.pref_bonus)
                    + (ctx.density_weight * c.info_density)
                    + c.learned_bonus
                    + continuity_bonus;

        results[i] = {
            c.id,
            total,
            c.semantic_match,
            energy_score,
            continuity_bonus
        };
    }
}

/**
 * High-performance batch cosine similarity calculation across multiple vectors.
 */
inline void batch_cosine_similarity(
    const float* query_vec,
    const float* matrix,
    size_t num_vectors,
    size_t dim,
    float* out_similarities
) {
    if (!query_vec || !matrix || !out_similarities || num_vectors == 0 || dim == 0) return;

    float query_norm_sq = 0.0f;
    for (size_t d = 0; d < dim; ++d) {
        query_norm_sq += query_vec[d] * query_vec[d];
    }
    float query_norm = std::sqrt(query_norm_sq);
    if (query_norm <= 1e-7f) {
        std::fill(out_similarities, out_similarities + num_vectors, 0.0f);
        return;
    }

    for (size_t i = 0; i < num_vectors; ++i) {
        const float* row = matrix + (i * dim);
        float dot = 0.0f;
        float row_norm_sq = 0.0f;
        for (size_t d = 0; d < dim; ++d) {
            dot += query_vec[d] * row[d];
            row_norm_sq += row[d] * row[d];
        }
        float row_norm = std::sqrt(row_norm_sq);
        float denom = query_norm * row_norm;
        out_similarities[i] = (denom > 1e-7f) ? std::clamp(dot / denom, -1.0f, 1.0f) : 0.0f;
    }
}

/**
 * Fast string sanitizer for song stem file naming.
 */
inline void clean_stem(const char* input, char* output, size_t max_len) {
    if (!input || !output || max_len == 0) return;
    std::string s(input);
    std::string cleaned;
    cleaned.reserve(s.size());
    for (char c : s) {
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == ' ' || c == '_' || c == '-') {
            cleaned.push_back(c);
        } else {
            cleaned.push_back('_');
        }
    }
    size_t pos;
    while ((pos = cleaned.find("  ")) != std::string::npos) {
        cleaned.replace(pos, 2, " ");
    }
    while ((pos = cleaned.find("__")) != std::string::npos) {
        cleaned.replace(pos, 2, "_");
    }
    size_t first = cleaned.find_first_not_of(" _-");
    size_t last = cleaned.find_last_not_of(" _-");
    if (first == std::string::npos || last == std::string::npos) {
        cleaned = "untitled";
    } else {
        cleaned = cleaned.substr(first, last - first + 1);
    }
    if (cleaned.empty()) cleaned = "untitled";
    size_t copy_len = std::min(cleaned.size(), max_len - 1);
    std::memcpy(output, cleaned.c_str(), copy_len);
    output[copy_len] = '\0';
}

// ── Semantic Concept Clusters ───────────────────────────────────────────────
constexpr uint32_t CLUSTER_WEED_420      = (1u << 0);
constexpr uint32_t CLUSTER_URBAN_STREET  = (1u << 1);
constexpr uint32_t CLUSTER_SPEED_MOTION  = (1u << 2);
constexpr uint32_t CLUSTER_PARTY_NIGHT   = (1u << 3);
constexpr uint32_t CLUSTER_BAVARIAN      = (1u << 4);
constexpr uint32_t CLUSTER_LUXURY_WEALTH = (1u << 5);
constexpr uint32_t CLUSTER_CYBER_TECH    = (1u << 6);
constexpr uint32_t CLUSTER_NATURE_CHILL  = (1u << 7);
constexpr uint32_t CLUSTER_COMBAT_ACTION = (1u << 8);

struct SemanticCandidateInput {
    int32_t id;
    float vector_similarity;
    float mood_score;
    float gender_score;
    uint32_t cluster_mask;
    float object_grounding_score;
};

/**
 * Fuses vector embedding cosine, lyric mood tag overlap, cluster bitmask affinity,
 * object detection grounding, and MC gender alignment into a single high-precision score.
 */
inline float compute_semantic_score(
    float vector_similarity,
    float mood_score,
    float gender_score,
    uint32_t clip_cluster_mask,
    uint32_t song_cluster_mask,
    float object_grounding_score
) {
    float vec_match = (vector_similarity >= -1.0f && vector_similarity <= 1.0f)
                      ? std::clamp((vector_similarity + 1.0f) * 0.5f, 0.0f, 1.0f)
                      : -1.0f;

    // Cluster overlap bonus
    float cluster_bonus = 0.0f;
    uint32_t shared = clip_cluster_mask & song_cluster_mask;
    if (shared != 0) {
        int bits = 0;
        uint32_t v = shared;
        while (v) { bits += (v & 1u); v >>= 1u; }
        cluster_bonus = std::min(1.0f, 0.5f + 0.2f * static_cast<float>(bits));
    }

    float total_val = 0.0f;
    float total_weight = 0.0f;

    if (vec_match >= 0.0f) {
        total_val += vec_match * 0.40f;
        total_weight += 0.40f;
    }
    if (mood_score >= 0.0f) {
        total_val += mood_score * 0.25f;
        total_weight += 0.25f;
    }
    if (cluster_bonus > 0.0f) {
        total_val += cluster_bonus * 0.15f;
        total_weight += 0.15f;
    }
    if (object_grounding_score >= 0.0f) {
        total_val += object_grounding_score * 0.10f;
        total_weight += 0.10f;
    }
    if (gender_score >= 0.0f) {
        total_val += gender_score * 0.20f;
        total_weight += 0.20f;
    }

    if (total_weight <= 1e-5f) return 0.5f;
    return std::clamp(total_val / total_weight, 0.0f, 1.0f);
}

inline void batch_compute_semantic_scores(
    const SemanticCandidateInput* inputs,
    size_t count,
    uint32_t song_cluster_mask,
    float* out_scores
) {
    if (!inputs || !out_scores || count == 0) return;
    for (size_t i = 0; i < count; ++i) {
        const auto& in = inputs[i];
        out_scores[i] = compute_semantic_score(
            in.vector_similarity,
            in.mood_score,
            in.gender_score,
            in.cluster_mask,
            song_cluster_mask,
            in.object_grounding_score
        );
    }
}

} // namespace cxx_accel

// C-ABI Exports for Python ctypes/cffi
extern "C" {

CXX_EXPORT void cxx_score_candidates(
    const cxx_accel::ClipCandidate* candidates,
    int32_t count,
    const cxx_accel::ScoringContext* ctx,
    cxx_accel::MatchResult* out_results
) {
    if (candidates && ctx && out_results && count > 0) {
        cxx_accel::score_clip_batch(candidates, static_cast<size_t>(count), *ctx, out_results);
    }
}

CXX_EXPORT float cxx_fast_cosine(const float* a, const float* b, int32_t dim) {
    return cxx_accel::cosine_similarity(a, b, static_cast<size_t>(dim));
}

CXX_EXPORT void cxx_batch_cosine(
    const float* query_vec,
    const float* matrix,
    int32_t num_vectors,
    int32_t dim,
    float* out_similarities
) {
    cxx_accel::batch_cosine_similarity(
        query_vec, matrix,
        static_cast<size_t>(num_vectors),
        static_cast<size_t>(dim),
        out_similarities
    );
}

CXX_EXPORT void cxx_clean_stem(const char* input, char* output, int32_t max_len) {
    cxx_accel::clean_stem(input, output, static_cast<size_t>(max_len));
}

CXX_EXPORT float cxx_compute_semantic_score(
    float vector_similarity,
    float mood_score,
    float gender_score,
    uint32_t clip_cluster_mask,
    uint32_t song_cluster_mask,
    float object_grounding_score
) {
    return cxx_accel::compute_semantic_score(
        vector_similarity,
        mood_score,
        gender_score,
        clip_cluster_mask,
        song_cluster_mask,
        object_grounding_score
    );
}

CXX_EXPORT void cxx_batch_semantic_scores(
    const cxx_accel::SemanticCandidateInput* inputs,
    int32_t count,
    uint32_t song_cluster_mask,
    float* out_scores
) {
    if (inputs && out_scores && count > 0) {
        cxx_accel::batch_compute_semantic_scores(
            inputs,
            static_cast<size_t>(count),
            song_cluster_mask,
            out_scores
        );
    }
}

}
