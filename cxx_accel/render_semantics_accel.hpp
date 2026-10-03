#pragma once
/**
 * render_semantics_accel.hpp — Native Render Semantics, Visual Motif Grading & Lyrics Grounding (C++20)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include <vector>
#include <string>
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

// Motif Codes: 0=NONE, 1=BETON, 2=EISBACH, 3=OIDA_089, 4=CYBER_ROBOTER, 5=WEED_420, 6=GRAFFITI_ART
// Lighting Codes: 0=natural, 1=lowkey, 2=highkey, 3=dramatic, 4=neon_backlight, 5=strobe
// Color Codes: 0=neutral, 1=desaturated, 2=vivid, 3=neon, 4=warm, 5=cold_cyan, 6=matrix_green, 7=vintage_film, 8=noir

struct RenderStyleInput {
    int32_t motif_code;
    int32_t lighting_code;
    int32_t color_code;
    float target_energy;
    float information_density;
    int32_t has_fx_grain;
    int32_t has_fx_flicker;
    int32_t has_fx_chroma;
    int32_t has_fx_vignette;
    int32_t has_fx_scanlines;
};

struct RenderStyleOutput {
    float contrast_mult;
    float brightness_offset;
    float saturation_mult;
    float gamma_mult;
    float color_balance_r;
    float color_balance_g;
    float color_balance_b;
    int32_t recommended_fx_mask; // Bit 0: grain, 1: flicker, 2: chroma, 3: vignette, 4: scanlines, 5: halate
};

inline void compute_render_styles_native(
    const RenderStyleInput* inputs,
    size_t count,
    RenderStyleOutput* outputs
) {
    if (!inputs || !outputs || count == 0) return;

    for (size_t i = 0; i < count; ++i) {
        const auto& in = inputs[i];
        auto& out = outputs[i];

        out.contrast_mult = 1.0f;
        out.brightness_offset = 0.0f;
        out.saturation_mult = 1.0f;
        out.gamma_mult = 1.0f;
        out.color_balance_r = 0.0f;
        out.color_balance_g = 0.0f;
        out.color_balance_b = 0.0f;
        out.recommended_fx_mask = 0;

        // 1. Lighting Modulation
        if (in.lighting_code == 1) { // lowkey
            out.brightness_offset -= 0.07f;
            out.contrast_mult *= 1.20f;
            out.gamma_mult *= 0.92f;
        } else if (in.lighting_code == 2) { // highkey
            out.brightness_offset += 0.05f;
            out.contrast_mult *= 0.95f;
            out.gamma_mult *= 1.05f;
        } else if (in.lighting_code == 3) { // dramatic
            out.brightness_offset -= 0.04f;
            out.contrast_mult *= 1.25f;
            out.gamma_mult *= 0.90f;
        } else if (in.lighting_code == 4) { // neon_backlight
            out.brightness_offset -= 0.02f;
            out.contrast_mult *= 1.15f;
            out.gamma_mult *= 0.96f;
        } else if (in.lighting_code == 5) { // strobe
            out.contrast_mult *= 1.30f;
        }

        // 2. Color Palette Modulation
        if (in.color_code == 1) { // desaturated
            out.saturation_mult *= 0.35f;
        } else if (in.color_code == 2) { // vivid
            out.saturation_mult *= 1.35f;
        } else if (in.color_code == 3) { // neon / cyber
            out.saturation_mult *= 1.45f;
            out.color_balance_r += 0.06f;
            out.color_balance_g -= 0.02f;
            out.color_balance_b += 0.08f;
        } else if (in.color_code == 4) { // warm / golden_hour
            out.color_balance_r += 0.08f;
            out.color_balance_g += 0.02f;
            out.color_balance_b -= 0.10f;
        } else if (in.color_code == 5) { // cold_cyan / teal
            out.color_balance_r -= 0.06f;
            out.color_balance_g += 0.02f;
            out.color_balance_b += 0.08f;
        } else if (in.color_code == 6) { // matrix_green / emerald
            out.color_balance_r -= 0.04f;
            out.color_balance_g += 0.08f;
            out.color_balance_b -= 0.04f;
        } else if (in.color_code == 7) { // vintage_film
            out.contrast_mult *= 1.08f;
            out.saturation_mult *= 0.88f;
            out.gamma_mult *= 1.06f;
            out.color_balance_r += 0.05f;
            out.color_balance_b -= 0.04f;
        } else if (in.color_code == 8) { // noir
            out.contrast_mult *= 1.35f;
            out.saturation_mult *= 0.15f;
            out.brightness_offset -= 0.03f;
        }

        // 3. OIDA Semantic Motif Grading
        if (in.motif_code == 1) { // BETON
            out.color_balance_r -= 0.03f;
            out.color_balance_b += 0.04f;
            out.contrast_mult *= 1.05f;
        } else if (in.motif_code == 2) { // EISBACH
            out.color_balance_r -= 0.05f;
            out.color_balance_g += 0.03f;
            out.color_balance_b += 0.06f;
        } else if (in.motif_code == 3) { // OIDA_089
            out.contrast_mult *= 1.05f;
            out.brightness_offset -= 0.02f;
            out.saturation_mult *= 1.10f;
            out.color_balance_r += 0.04f;
            out.color_balance_b -= 0.03f;
        } else if (in.motif_code == 4) { // CYBER_ROBOTER
            out.contrast_mult *= 1.12f;
            out.saturation_mult *= 1.18f;
            out.color_balance_r += 0.05f;
            out.color_balance_b += 0.06f;
        } else if (in.motif_code == 5) { // WEED_420
            out.gamma_mult *= 1.04f;
            out.saturation_mult *= 1.12f;
            out.color_balance_g += 0.05f;
        } else if (in.motif_code == 6) { // GRAFFITI_ART
            out.contrast_mult *= 1.08f;
            out.saturation_mult *= 1.28f;
        }

        // 4. FX Mask Construction
        int32_t mask = 0;
        if (in.has_fx_grain) mask |= (1 << 0);
        if (in.has_fx_flicker) mask |= (1 << 1);
        if (in.has_fx_chroma) mask |= (1 << 2);
        if (in.has_fx_vignette) mask |= (1 << 3);
        if (in.has_fx_scanlines) mask |= (1 << 4);
        out.recommended_fx_mask = mask;
    }
}

inline float calculate_lyrics_grounding_native(
    const uint32_t* lyrics_word_hashes,
    size_t lyrics_len,
    const uint32_t* clip_word_hashes,
    size_t clip_len
) {
    if (!lyrics_word_hashes || !clip_word_hashes || lyrics_len == 0 || clip_len == 0) {
        return 0.0f;
    }

    size_t matches = 0;
    for (size_t i = 0; i < lyrics_len; ++i) {
        uint32_t l_hash = lyrics_word_hashes[i];
        for (size_t j = 0; j < clip_len; ++j) {
            if (l_hash == clip_word_hashes[j]) {
                matches++;
                break;
            }
        }
    }

    float precision = static_cast<float>(matches) / static_cast<float>(clip_len);
    float recall = static_cast<float>(matches) / static_cast<float>(lyrics_len);
    if (precision + recall < 1e-6f) return 0.0f;

    return (2.0f * precision * recall) / (precision + recall);
}

} // namespace cxx_accel

extern "C" {

CXX_EXPORT void cxx_compute_render_styles_batch(
    const cxx_accel::RenderStyleInput* inputs,
    int32_t count,
    cxx_accel::RenderStyleOutput* outputs
) {
    if (count > 0 && inputs && outputs) {
        cxx_accel::compute_render_styles_native(inputs, static_cast<size_t>(count), outputs);
    }
}

CXX_EXPORT float cxx_calculate_lyrics_grounding(
    const uint32_t* lyrics_word_hashes,
    int32_t lyrics_len,
    const uint32_t* clip_word_hashes,
    int32_t clip_len
) {
    if (lyrics_len <= 0 || clip_len <= 0) return 0.0f;
    return cxx_accel::calculate_lyrics_grounding_native(
        lyrics_word_hashes, static_cast<size_t>(lyrics_len),
        clip_word_hashes, static_cast<size_t>(clip_len)
    );
}

}
