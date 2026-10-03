#pragma once
/**
 * self_learning_accel.hpp — Reinforcement Learning & Bandit Acceleration for OIDASHEIM
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include "clip_matcher.hpp"
#include <vector>
#include <cmath>
#include <random>
#include <algorithm>
#include <cstdint>

namespace cxx_accel {

// Fast Gamma Distribution generator (Marsaglia & Tsang method)
inline double sample_gamma(double shape, double scale, std::mt19937_64& rng) {
    if (shape < 1.0) {
        std::uniform_real_distribution<double> u_dist(0.0, 1.0);
        return sample_gamma(1.0 + shape, scale, rng) * std::pow(u_dist(rng), 1.0 / shape);
    }

    double d = shape - 1.0 / 3.0;
    double c = 1.0 / std::sqrt(9.0 * d);
    std::normal_distribution<double> n_dist(0.0, 1.0);
    std::uniform_real_distribution<double> u_dist(0.0, 1.0);

    while (true) {
        double z = n_dist(rng);
        double v = 1.0 + c * z;
        if (v <= 0.0) continue;
        v = v * v * v;
        double u = u_dist(rng);
        if (u < 1.0 - 0.0331 * z * z * z * z) {
            return d * v * scale;
        }
        if (std::log(u) < 0.5 * z * z + d * (1.0 - v + std::log(v))) {
            return d * v * scale;
        }
    }
}

// Fast Beta Distribution generator via Gamma ratio
inline float sample_beta(float alpha, float beta, uint64_t seed = 0) {
    static thread_local std::mt19937_64 rng(seed ? seed : std::random_device{}());
    if (seed != 0) {
        rng.seed(seed);
    }

    double a = std::max(0.01, static_cast<double>(alpha));
    double b = std::max(0.01, static_cast<double>(beta));

    double ga = sample_gamma(a, 1.0, rng);
    double gb = sample_gamma(b, 1.0, rng);

    if (ga + gb <= 0.0) return 0.5f;
    return static_cast<float>(ga / (ga + gb));
}

// UCB1 Score Calculation
inline float compute_ucb1(float total_reward, int32_t pulls, int32_t total_pulls, float c = 1.414f) {
    if (pulls <= 0) return 999.0f; // Explore unvisited arms first
    float mean_reward = total_reward / static_cast<float>(pulls);
    float bonus = c * std::sqrt(std::log(static_cast<float>(std::max(1, total_pulls))) / static_cast<float>(pulls));
    return mean_reward + bonus;
}

} // namespace cxx_accel

// ── C-ABI Exported Functions ─────────────────────────────────────────────────
extern "C" {

CXX_EXPORT float cxx_bandit_sample_thompson(float total_reward, int32_t pulls, uint64_t seed) {
    float alpha = 1.0f + std::max(0.0f, total_reward);
    float beta = 1.0f + std::max(0.0f, static_cast<float>(pulls) - total_reward);
    return cxx_accel::sample_beta(alpha, beta, seed);
}

CXX_EXPORT int32_t cxx_bandit_select_best_arm(
    const float* total_rewards,
    const int32_t* pulls,
    int32_t num_arms,
    int32_t strategy, // 0 = Thompson Sampling, 1 = UCB1, 2 = Greedy
    float ucb_c,
    uint64_t seed
) {
    if (!total_rewards || !pulls || num_arms <= 0) return 0;

    int32_t total_pulls = 0;
    for (int32_t i = 0; i < num_arms; ++i) {
        total_pulls += pulls[i];
    }
    total_pulls += 1;

    int32_t best_idx = 0;
    float best_score = -999999.0f;

    for (int32_t i = 0; i < num_arms; ++i) {
        float score = 0.0f;
        if (strategy == 1) {
            // UCB1
            score = cxx_accel::compute_ucb1(total_rewards[i], pulls[i], total_pulls, ucb_c);
        } else if (strategy == 2) {
            // Pure Greedy
            score = (pulls[i] > 0) ? (total_rewards[i] / static_cast<float>(pulls[i])) : 0.5f;
        } else {
            // Thompson Sampling (Default)
            float alpha = 1.0f + std::max(0.0f, total_rewards[i]);
            float beta = 1.0f + std::max(0.0f, static_cast<float>(pulls[i]) - total_rewards[i]);
            score = cxx_accel::sample_beta(alpha, beta, seed + i);
        }

        if (score > best_score) {
            best_score = score;
            best_idx = i;
        }
    }

    return best_idx;
}

CXX_EXPORT float cxx_markov_transition_bonus(float reward_sum, int32_t count, int32_t same_motion_direction) {
    float mean_r = (count > 0) ? (reward_sum / static_cast<float>(count)) : 0.5f;
    float bonus = (mean_r - 0.5f) * 0.15f;
    if (same_motion_direction) {
        bonus += 0.05f;
    }
    return bonus;
}

CXX_EXPORT float cxx_ema_update(float current_val, float target_val, float learning_rate) {
    float lr = std::clamp(learning_rate, 0.0f, 1.0f);
    return (1.0f - lr) * current_val + lr * target_val;
}

} // extern "C"
