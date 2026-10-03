#pragma once
/**
 * candidate_ranker_accel.hpp — Native High-Speed Clip Pool Candidate Ranker & Top-K Selector (C++20 / AVX2)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include "clip_matcher.hpp"
#include <vector>
#include <queue>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <cstring>

#if defined(__AVX2__)
  #include <immintrin.h>
#endif

namespace cxx_accel {

struct ClipDenseMeta {
    float duration;
    float motion_score;
    float motion_direction;
    float face_score;
    float info_density;
    float learned_bonus;
    int32_t gender_code; // 0=neutral, 1=female, 2=male, 3=dual
    int32_t is_still;
    int32_t is_cooldown_locked;
};

struct RankerQueryContext {
    float target_energy;
    float target_duration;
    float motion_weight;
    float semantic_weight;
    float pref_weight;
    float density_weight;
    float prev_motion_dir;
    int32_t target_gender_code; // 0=any, 1=female, 2=male, 3=dual
    int32_t allow_still;
    int32_t check_motion_continuity;
};

/**
 * AVX2 dot product between query vector and candidate vector.
 */
inline float sim_dot(const float* a, const float* b, int32_t dim) {
    float sum = 0.0f;
    int32_t i = 0;
#if defined(__AVX2__)
    __m256 acc = _mm256_setzero_ps();
    for (; i + 7 < dim; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        acc = _mm256_fmadd_ps(va, vb, acc);
    }
    __m128 lo = _mm256_castps256_ps128(acc);
    __m128 hi = _mm256_extractf128_ps(acc, 1);
    __m128 sum128 = _mm_add_ps(lo, hi);
    sum128 = _mm_hadd_ps(sum128, sum128);
    sum128 = _mm_hadd_ps(sum128, sum128);
    sum = _mm_cvtss_f32(sum128);
#endif
    for (; i < dim; ++i) {
        sum += a[i] * b[i];
    }
    return sum;
}

/**
 * Evaluates, filters, and ranks all candidates in the clip pool in a single native pass.
 * Returns top-K candidates sorted by score descending.
 */
inline int32_t rank_topk_candidates_native(
    const float* query_vec,
    const float* vector_matrix,
    const ClipDenseMeta* metas,
    size_t count,
    int32_t dim,
    const RankerQueryContext& ctx,
    int32_t top_k,
    int32_t* out_indices,
    float* out_scores
) {
    if (!query_vec || !vector_matrix || !metas || !out_indices || !out_scores || count == 0 || top_k <= 0) {
        return 0;
    }

    // Min-heap to keep top-K candidates: pair<score, index>
    using ScorePair = std::pair<float, int32_t>;
    std::priority_queue<ScorePair, std::vector<ScorePair>, std::greater<ScorePair>> min_heap;

    float query_norm_sq = sim_dot(query_vec, query_vec, dim);
    float query_norm = std::sqrt(query_norm_sq);

    for (size_t i = 0; i < count; ++i) {
        const auto& m = metas[i];

        // Hard filters
        if (m.is_cooldown_locked) continue;
        if (m.duration < ctx.target_duration && m.duration > 0.01f) continue;
        if (m.is_still && !ctx.allow_still) continue;

        // Gender filter
        if (ctx.target_gender_code > 0 && m.gender_code > 0) {
            if (ctx.target_gender_code != 3 && m.gender_code != 3 && ctx.target_gender_code != m.gender_code) {
                // Gender mismatch
                continue;
            }
        }

        // Semantic Cosine
        const float* cand_vec = vector_matrix + (i * dim);
        float dot = sim_dot(query_vec, cand_vec, dim);
        float cand_norm_sq = sim_dot(cand_vec, cand_vec, dim);
        float cand_norm = std::sqrt(cand_norm_sq);
        float cosine = 0.0f;
        if (query_norm > 1e-6f && cand_norm > 1e-6f) {
            cosine = std::clamp(dot / (query_norm * cand_norm), 0.0f, 1.0f);
        }

        // Energy match
        float energy_delta = std::abs(m.motion_score - ctx.target_energy);
        float energy_score = 1.0f - std::min(1.0f, energy_delta * 1.5f);

        // Motion continuity
        float continuity = 0.0f;
        if (ctx.check_motion_continuity && std::abs(ctx.prev_motion_dir) > 0.1f) {
            if ((ctx.prev_motion_dir > 0.0f && m.motion_direction > 0.0f) ||
                (ctx.prev_motion_dir < 0.0f && m.motion_direction < 0.0f)) {
                continuity = 0.08f;
            }
        }

        float total_score = (ctx.semantic_weight * cosine)
                          + (ctx.motion_weight * energy_score)
                          + (ctx.density_weight * m.info_density)
                          + m.learned_bonus
                          + continuity;

        if (static_cast<int32_t>(min_heap.size()) < top_k) {
            min_heap.push({total_score, static_cast<int32_t>(i)});
        } else if (total_score > min_heap.top().first) {
            min_heap.pop();
            min_heap.push({total_score, static_cast<int32_t>(i)});
        }
    }

    int32_t result_count = static_cast<int32_t>(min_heap.size());
    std::vector<ScorePair> sorted_results(result_count);
    for (int32_t j = result_count - 1; j >= 0; --j) {
        sorted_results[j] = min_heap.top();
        min_heap.pop();
    }

    for (int32_t j = 0; j < result_count; ++j) {
        out_indices[j] = sorted_results[j].second;
        out_scores[j] = sorted_results[j].first;
    }

    return result_count;
}

/**
 * Fast native candidate matrix evaluation.
 * Evaluates candidate_matrix (N, 9) in place with zero allocation.
 */
inline void score_candidates_matrix_native(
    const float* candidate_matrix,
    int32_t count,
    float target_energy,
    float target_duration,
    float motion_weight,
    float semantic_weight,
    float pref_weight,
    float density_weight,
    float prev_motion_dir,
    int32_t check_continuity,
    float* out_scores
) {
    if (!candidate_matrix || !out_scores || count <= 0) return;

    for (int32_t i = 0; i < count; ++i) {
        const float* row = candidate_matrix + (i * 9);
        float dur = row[1];
        if (dur < target_duration && dur > 0.01f) {
            out_scores[i] = -1000.0f;
            continue;
        }

        float motion_score = row[2];
        float motion_dir = row[3];
        float sem_match = row[5];
        float pref_bonus = row[6];
        float info_density = row[7];
        float learned_bonus = row[8];

        float energy_delta = std::abs(motion_score - target_energy);
        float energy_score = 1.0f - std::min(1.0f, energy_delta * 1.5f);

        float cont_bonus = 0.0f;
        if (check_continuity && std::abs(prev_motion_dir) > 0.1f) {
            if ((prev_motion_dir > 0.0f && motion_dir > 0.0f) ||
                (prev_motion_dir < 0.0f && motion_dir < 0.0f)) {
                cont_bonus = 0.08f;
            }
        }

        out_scores[i] = (semantic_weight * sem_match)
                      + (motion_weight * energy_score)
                      + (pref_weight * pref_bonus)
                      + (density_weight * info_density)
                      + learned_bonus
                      + cont_bonus;
    }
}

} // namespace cxx_accel

extern "C" {

CXX_EXPORT int32_t cxx_rank_topk_candidates(
    const float* query_vec,
    const float* vector_matrix,
    const cxx_accel::ClipDenseMeta* metas,
    int32_t count,
    int32_t dim,
    const cxx_accel::RankerQueryContext* ctx,
    int32_t top_k,
    int32_t* out_indices,
    float* out_scores
) {
    if (!ctx) return 0;
    return cxx_accel::rank_topk_candidates_native(
        query_vec, vector_matrix, metas,
        static_cast<size_t>(count), dim, *ctx, top_k,
        out_indices, out_scores
    );
}

CXX_EXPORT void cxx_score_candidates_matrix(
    const float* candidate_matrix,
    int32_t count,
    float target_energy,
    float target_duration,
    float motion_weight,
    float semantic_weight,
    float pref_weight,
    float density_weight,
    float prev_motion_dir,
    int32_t check_continuity,
    float* out_scores
) {
    cxx_accel::score_candidates_matrix_native(
        candidate_matrix, count, target_energy, target_duration,
        motion_weight, semantic_weight, pref_weight, density_weight,
        prev_motion_dir, check_continuity, out_scores
    );
}

}
