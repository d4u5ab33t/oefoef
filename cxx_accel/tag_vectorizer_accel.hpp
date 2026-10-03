#pragma once
/**
 * tag_vectorizer_accel.hpp — Native High-Speed Tokenizer & Vocabulary Tag Vectorizer (C++20)
 * Part of OIDASHEIM BeatSync Native Acceleration Engine (cxx_accel)
 */

#include <vector>
#include <string>
#include <string_view>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <unordered_set>
#include <cctype>

#ifdef _WIN32
  #define CXX_EXPORT __declspec(dllexport)
#else
  #define CXX_EXPORT __attribute__((visibility("default")))
#endif

namespace cxx_accel {

// Predefined 85-dimensional OIDAHEIM Vocabulary matching config.py TAG_VOCAB
inline const char* const DEFAULT_TAG_VOCAB[85] = {
    "action", "slow", "fast", "drone", "night", "dark", "light", "neon", "sunset",
    "nature", "city", "street", "urban", "car", "drift", "smoke", "fire", "water",
    "ocean", "forest", "mountain", "cloud", "rain", "abstract", "glitch", "vfx",
    "dance", "crowd", "party", "club", "rave", "dj", "stage", "laser", "strobe",
    "face", "portrait", "eyes", "motion", "cinematic", "film", "vintage", "retro",
    "future", "cyber", "cyberpunk", "space", "stars", "speed", "fight", "jump",
    "fall", "fly", "running", "walking", "chill", "relax", "energy", "intense",
    "dramatic", "moody", "sad", "happy", "love", "texture", "pattern", "color",
    "oida", "oidaheim", "bavaria", "munich", "089", "eisbach", "beton", "weed", "420",
    "joint", "blunt", "high", "stoned", "psychedelic", "cloud", "trip", "cannabis", "ganja"
};

/**
 * Fast ASCII lowercase tokenizer: extracts alphanumeric tokens without regex overhead.
 */
inline void fast_tokenize(std::string_view text, std::vector<std::string>& out_tokens) {
    out_tokens.clear();
    std::string current;
    current.reserve(32);

    for (char ch : text) {
        if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '_') {
            current.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
        } else {
            if (!current.empty()) {
                out_tokens.push_back(std::move(current));
                current.clear();
                current.reserve(32);
            }
        }
    }
    if (!current.empty()) {
        out_tokens.push_back(std::move(current));
    }
}

/**
 * Build a dense 85-dimensional float vector from text using precompiled vocabulary.
 */
inline void build_tag_vector_native(
    std::string_view text,
    float* out_vec,
    int32_t dim = 85
) {
    if (!out_vec || dim <= 0) return;
    std::fill(out_vec, out_vec + dim, 0.0f);

    std::vector<std::string> tokens;
    fast_tokenize(text, tokens);
    if (tokens.empty()) return;

    std::unordered_set<std::string> token_set(tokens.begin(), tokens.end());

    int32_t vocab_size = std::min(dim, 85);
    for (int32_t i = 0; i < vocab_size; ++i) {
        if (token_set.find(DEFAULT_TAG_VOCAB[i]) != token_set.end()) {
            out_vec[i] = 1.0f;
        }
    }
}

/**
 * Batch tokenization and vectorization for multiple text items.
 */
inline void batch_build_tag_vectors_native(
    const char** text_array,
    size_t count,
    float* out_matrix,
    int32_t dim = 85
) {
    if (!text_array || !out_matrix || count == 0 || dim <= 0) return;

    for (size_t i = 0; i < count; ++i) {
        const char* str = text_array[i];
        float* row = out_matrix + (i * dim);
        if (str) {
            build_tag_vector_native(std::string_view(str), row, dim);
        } else {
            std::fill(row, row + dim, 0.0f);
        }
    }
}

} // namespace cxx_accel

extern "C" {

CXX_EXPORT void cxx_vectorize_text(const char* text, float* out_vec, int32_t dim) {
    if (!text || !out_vec) return;
    cxx_accel::build_tag_vector_native(std::string_view(text), out_vec, dim);
}

CXX_EXPORT void cxx_batch_vectorize_texts(const char** texts, int32_t count, float* out_matrix, int32_t dim) {
    cxx_accel::batch_build_tag_vectors_native(texts, static_cast<size_t>(count), out_matrix, dim);
}

}
