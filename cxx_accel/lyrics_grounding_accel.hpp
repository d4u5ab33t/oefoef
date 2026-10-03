#pragma once
/**
 * lyrics_grounding_accel.hpp — Native High-Speed Lyrics Semantics & Tension Dynamics (C++20)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include <vector>
#include <string>
#include <string_view>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <unordered_set>

#ifdef _WIN32
  #define CXX_EXPORT __declspec(dllexport)
#else
  #define CXX_EXPORT __attribute__((visibility("default")))
#endif

namespace cxx_accel {

inline const char* const OIDA_SLANG_TERMS[] = {
    "oida", "haberer", "spezi", "gspusi", "watschn", "haderlump", "servus",
    "bazi", "zamkemma", "hockn", "gaudi", "griawig", "oachkatzl", "schmarrn",
    "fesch", "gschaftlhuber", "pfiate", "semmel", "wiesn", "eisbach", "089",
    "beton", "weed", "420", "blunt", "joint", "ganja", "chaya", "brudi", "digga"
};

/**
 * Fast slang density calculation from word tokens.
 */
inline float calculate_slang_density_native(
    const char** tokens,
    size_t token_count
) {
    if (!tokens || token_count == 0) return 0.0f;
    static const std::unordered_set<std::string> slang_set(
        std::begin(OIDA_SLANG_TERMS), std::end(OIDA_SLANG_TERMS)
    );

    int32_t hits = 0;
    for (size_t i = 0; i < token_count; ++i) {
        if (tokens[i]) {
            std::string t = tokens[i];
            std::transform(t.begin(), t.end(), t.begin(), ::tolower);
            if (slang_set.find(t) != slang_set.end()) {
                hits++;
            }
        }
    }
    return static_cast<float>(hits) / static_cast<float>(token_count);
}

/**
 * Tension curve synthesis combining energy gradient, lyric punchlines, and movement drops.
 */
inline void synthesize_tension_curve_native(
    const float* energy_curve,
    const float* punchline_weights,
    size_t length,
    float* out_tension
) {
    if (!energy_curve || !punchline_weights || !out_tension || length == 0) return;

    for (size_t i = 0; i < length; ++i) {
        float energy = energy_curve[i];
        float punch = punchline_weights[i];
        float prev_energy = (i > 0) ? energy_curve[i - 1] : energy;
        float energy_delta = std::max(0.0f, energy - prev_energy);

        float raw_tension = (0.50f * energy) + (0.30f * punch) + (0.20f * (energy_delta * 2.0f));
        out_tension[i] = std::clamp(raw_tension, 0.0f, 1.0f);
    }
}

} // namespace cxx_accel

extern "C" {

CXX_EXPORT float cxx_calculate_slang_density(const char** tokens, int32_t token_count) {
    return cxx_accel::calculate_slang_density_native(tokens, static_cast<size_t>(token_count));
}

CXX_EXPORT void cxx_synthesize_tension_curve(
    const float* energy_curve,
    const float* punchline_weights,
    int32_t length,
    float* out_tension
) {
    cxx_accel::synthesize_tension_curve_native(
        energy_curve, punchline_weights, static_cast<size_t>(length), out_tension
    );
}

}
