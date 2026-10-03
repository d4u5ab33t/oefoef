#pragma once
/**
 * vector_tree_accel.hpp — SIMD Accelerated Vector Tree & K-Means for OIDASHEIM
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include "clip_matcher.hpp"
#include <vector>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <random>
#include <queue>
#include <cstdint>
#include <cstring>

namespace cxx_accel {

// Fast Dot Product & SIMD Euclidean / Cosine Distance
inline float dot_product(const float* a, const float* b, int32_t dim) {
    float sum = 0.0f;
    int32_t i = 0;
#if defined(__AVX2__)
    __m256 acc = _mm256_setzero_ps();
    for (; i + 7 < dim; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        acc = _mm256_fmadd_ps(va, vb, acc);
    }
    // Horizontal sum
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

inline float vector_norm(const float* a, int32_t dim) {
    float dot = dot_product(a, a, dim);
    return std::sqrt(std::max(1e-12f, dot));
}

inline float cosine_distance(const float* a, const float* b, int32_t dim) {
    if (!a || !b || dim <= 0) return 1.0f;
    float dot = dot_product(a, b, dim);
    float na = vector_norm(a, dim);
    float nb = vector_norm(b, dim);
    if (na < 1e-6f || nb < 1e-6f) return 1.0f;
    float sim = dot / (na * nb);
    sim = std::clamp(sim, -1.0f, 1.0f);
    return 1.0f - sim;
}

// Fast SIMD K-Means++ Clustering on Normalized Spherical Vectors
inline void spherical_kmeans(
    const float* data,
    int32_t n_samples,
    int32_t dim,
    int32_t k,
    int32_t max_iter,
    float* out_centroids,
    int32_t* out_labels
) {
    if (n_samples <= 0 || dim <= 0 || k <= 0) return;
    if (n_samples <= k) {
        for (int32_t i = 0; i < n_samples; ++i) {
            std::memcpy(out_centroids + i * dim, data + i * dim, sizeof(float) * dim);
            if (out_labels) out_labels[i] = i;
        }
        return;
    }

    // Step 1: K-Means++ Initialization
    std::vector<int32_t> center_indices;
    center_indices.reserve(k);
    center_indices.push_back(0);

    std::vector<float> min_dists(n_samples, 2.0f);

    for (int32_t step = 1; step < k; ++step) {
        const float* last_center = data + center_indices.back() * dim;
        float max_d = -1.0f;
        int32_t best_cand = 0;

        for (int32_t i = 0; i < n_samples; ++i) {
            float dist = cosine_distance(data + i * dim, last_center, dim);
            if (dist < min_dists[i]) {
                min_dists[i] = dist;
            }
            if (min_dists[i] > max_d) {
                max_d = min_dists[i];
                best_cand = i;
            }
        }
        center_indices.push_back(best_cand);
    }

    // Copy initial centroids
    for (int32_t c = 0; c < k; ++c) {
        std::memcpy(out_centroids + c * dim, data + center_indices[c] * dim, sizeof(float) * dim);
    }

    std::vector<int32_t> labels(n_samples, 0);
    std::vector<int32_t> cluster_counts(k, 0);
    std::vector<float> accum_centroids(k * dim, 0.0f);

    // Iterative refinement
    for (int32_t iter = 0; iter < max_iter; ++iter) {
        std::fill(cluster_counts.begin(), cluster_counts.end(), 0);
        std::fill(accum_centroids.begin(), accum_centroids.end(), 0.0f);

        // Assign to nearest centroid
        for (int32_t i = 0; i < n_samples; ++i) {
            const float* vec = data + i * dim;
            float min_dist = 999.0f;
            int32_t best_c = 0;

            for (int32_t c = 0; c < k; ++c) {
                const float* center = out_centroids + c * dim;
                float dist = cosine_distance(vec, center, dim);
                if (dist < min_dist) {
                    min_dist = dist;
                    best_c = c;
                }
            }
            labels[i] = best_c;
            cluster_counts[best_c]++;

            float* acc = accum_centroids.data() + best_c * dim;
            for (int32_t d = 0; d < dim; ++d) {
                acc[d] += vec[d];
            }
        }

        // Recompute centroids & normalize
        for (int32_t c = 0; c < k; ++c) {
            if (cluster_counts[c] > 0) {
                float* center = out_centroids + c * dim;
                const float* acc = accum_centroids.data() + c * dim;
                for (int32_t d = 0; d < dim; ++d) {
                    center[d] = acc[d] / static_cast<float>(cluster_counts[c]);
                }
                float norm = vector_norm(center, dim);
                if (norm > 1e-6f) {
                    for (int32_t d = 0; d < dim; ++d) {
                        center[d] /= norm;
                    }
                }
            }
        }
    }

    if (out_labels) {
        for (int32_t i = 0; i < n_samples; ++i) {
            out_labels[i] = labels[i];
        }
    }
}

} // namespace cxx_accel

// ── C-ABI Exported Functions ─────────────────────────────────────────────────
extern "C" {

CXX_EXPORT float cxx_vtree_cosine_distance(const float* a, const float* b, int32_t dim) {
    return cxx_accel::cosine_distance(a, b, dim);
}

CXX_EXPORT void cxx_vtree_batch_cosine_dist(
    const float* query_vec,
    const float* matrix,
    int32_t num_vectors,
    int32_t dim,
    float* out_dists
) {
    if (!query_vec || !matrix || !out_dists || num_vectors <= 0 || dim <= 0) return;
    for (int32_t i = 0; i < num_vectors; ++i) {
        out_dists[i] = cxx_accel::cosine_distance(query_vec, matrix + i * dim, dim);
    }
}

CXX_EXPORT void cxx_vtree_kmeans_cluster(
    const float* data,
    int32_t num_samples,
    int32_t dim,
    int32_t k,
    int32_t max_iter,
    float* out_centroids,
    int32_t* out_labels
) {
    cxx_accel::spherical_kmeans(data, num_samples, dim, k, max_iter, out_centroids, out_labels);
}

CXX_EXPORT int32_t cxx_vtree_query_candidates(
    const float* query_vec,
    int32_t dim,
    const float* leaf_vectors,
    const float* leaf_motions,
    const int32_t* leaf_genders, // 0=neutral, 1=male, 2=female, 3=dual
    const float* leaf_rewards,
    int32_t num_leaves,
    float target_motion,
    int32_t target_gender,
    int32_t use_learned_priors,
    int32_t top_k,
    int32_t* out_indices,
    float* out_scores
) {
    if (!query_vec || !leaf_vectors || num_leaves <= 0 || dim <= 0 || top_k <= 0) return 0;

    struct ScoredLeaf {
        int32_t index;
        float score;
        bool operator>(const ScoredLeaf& other) const {
            return score > other.score;
        }
    };

    // Min-heap for Top-K
    std::priority_queue<ScoredLeaf, std::vector<ScoredLeaf>, std::greater<ScoredLeaf>> min_heap;

    for (int32_t i = 0; i < num_leaves; ++i) {
        const float* lvec = leaf_vectors + i * dim;
        float dist = cxx_accel::cosine_distance(query_vec, lvec, dim);
        float sim_score = std::max(0.0f, 1.0f - dist);

        // Motion bonus
        float motion_bonus = 0.0f;
        if (target_motion >= 0.0f && leaf_motions) {
            float diff = std::abs(leaf_motions[i] - target_motion);
            motion_bonus = std::max(0.0f, 1.0f - diff) * 0.15f;
        }

        // Gender bonus
        float gender_bonus = 0.0f;
        if (leaf_genders && target_gender > 0) {
            int32_t g = leaf_genders[i];
            if (g == target_gender || target_gender == 3) {
                gender_bonus = 0.10f;
            } else if (g == 0) {
                gender_bonus = 0.04f;
            }
        }

        // Learned reward bonus
        float learned_bonus = 0.0f;
        if (use_learned_priors && leaf_rewards) {
            learned_bonus = (leaf_rewards[i] - 0.5f) * 0.12f;
        }

        float final_score = sim_score * 0.65f + motion_bonus + gender_bonus + learned_bonus;

        if (static_cast<int32_t>(min_heap.size()) < top_k) {
            min_heap.push({i, final_score});
        } else if (final_score > min_heap.top().score) {
            min_heap.pop();
            min_heap.push({i, final_score});
        }
    }

    // Extract sorted results
    int32_t count = static_cast<int32_t>(min_heap.size());
    std::vector<ScoredLeaf> sorted_items(count);
    for (int32_t i = count - 1; i >= 0; --i) {
        sorted_items[i] = min_heap.top();
        min_heap.pop();
    }

    for (int32_t i = 0; i < count; ++i) {
        if (out_indices) out_indices[i] = sorted_items[i].index;
        if (out_scores) out_scores[i] = sorted_items[i].score;
    }

    return count;
}

} // extern "C"
