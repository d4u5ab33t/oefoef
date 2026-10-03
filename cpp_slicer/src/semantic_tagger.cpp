#include "semantic_tagger.hpp"
#include <algorithm>
#include <sstream>
#include <cctype>
#include <iomanip>
#include <cmath>

namespace Oidasheim {

static std::string toLower(const std::string& str) {
    std::string result = str;
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c){ return static_cast<char>(std::tolower(c)); });
    return result;
}

SemanticTagger::SemanticTagger() {
    initVocabularies();
}

void SemanticTagger::initVocabularies() {
    vocab_ = {
        "oida", "rap", "hiphop", "weed", "420", "smoke", "joint", "blunt", "haze", "kush",
        "swag", "trap", "bass", "drill", "boombap", "turntable", "scratch", "dj", "vinyl",
        "club", "party", "rave", "street", "hood", "bavaria", "munich", "vibe", "chill",
        "dark", "neon", "sunset", "golden", "cyberpunk", "retro", "vhs", "glitch", "performance",
        "mic", "microphone", "singer", "rapper", "flow", "bars", "spit", "studio", "session",
        "stage", "lights", "night", "city", "bmw", "mercedes", "car", "drift", "speed",
        "money", "cash", "gold", "chains", "flex", "gang", "crew", "posse", "underground"
    };

    femaleTerms_ = {
        "female", "woman", "women", "girl", "girls", "lady", "ladies", "chick", "chicks",
        "queen", "queens", "singer_f", "model_f", "bitch", "frau", "frauen", "rapperin",
        "saengerin", "sängerin", "weiblich", "maedchen", "mädchen", "dirndl", "braut", "chaya",
        "chica", "mujer", "femme", "fille", "donna", "ragazza"
    };

    maleTerms_ = {
        "male", "man", "men", "boy", "boys", "guy", "guys", "dude", "dudes", "bro", "bros",
        "king", "kings", "singer_m", "model_m", "mann", "männer", "maenner", "bruder", "brueder",
        "rapper", "saenger", "sänger", "maennlich", "männlich", "kerl", "haberer", "bazi", "oida",
        "hombre", "chico", "homme", "frere", "uomo", "fratello"
    };

    spittingTerms_ = {
        "spit", "spitting", "rapper", "rapping", "bars", "flow", "rhyme", "rhymes",
        "freestyle", "mic", "microphone", "mc", "vocal", "vocals", "singer", "singing",
        "lip_sync", "lipsync", "performance", "rap", "stage", "close_up", "portrait",
        "headshot", "mouth", "facetime", "rapstar", "session", "studio"
    };

    djTerms_ = {
        "dj", "turntable", "turntables", "vinyl", "mixer", "crossfader", "jogwheel", "deck",
        "decks", "pioneer", "technics", "club_dj", "headphones", "scratch", "scratching",
        "hands_on_vinyl", "drop_the_beat", "slipmat", "serato", "traktor", "plattenspieler",
        "soundclash", "club", "party", "rave", "stage"
    };

    weedTerms_ = {
        "weed", "420", "smoke", "smoking", "joint", "blunt", "haze", "kush", "ott", "herb",
        "spliff", "bong", "ganja", "maryjane", "cannabis", "thc", "rolling", "toker", "high",
        "stoned", "puff", "cloud", "baked"
    };
}

std::vector<std::string> SemanticTagger::extractTagsFromPath(const std::string& path) {
    std::set<std::string> tags;
    std::string lower = toLower(path);
    
    std::string token;
    for (char ch : lower) {
        if (std::isalnum(static_cast<unsigned char>(ch))) {
            token += ch;
        } else {
            if (token.length() >= 3) {
                tags.insert(token);
            }
            token.clear();
        }
    }
    if (token.length() >= 3) {
        tags.insert(token);
    }

    for (const auto& kw : vocab_) {
        if (lower.find(kw) != std::string::npos) {
            tags.insert(kw);
        }
    }

    for (const auto& kw : weedTerms_) {
        if (lower.find(kw) != std::string::npos) {
            tags.insert(kw);
        }
    }

    return std::vector<std::string>(tags.begin(), tags.end());
}

std::string SemanticTagger::determineGender(const std::vector<std::string>& tags, const std::string& path) {
    std::string lowerPath = toLower(path);
    bool hasFemale = false;
    bool hasMale = false;

    for (const auto& tag : tags) {
        if (femaleTerms_.count(tag)) hasFemale = true;
        if (maleTerms_.count(tag)) hasMale = true;
    }

    if (!hasFemale) {
        for (const auto& term : femaleTerms_) {
            if (lowerPath.find(term) != std::string::npos) {
                hasFemale = true;
                break;
            }
        }
    }

    if (!hasMale) {
        for (const auto& term : maleTerms_) {
            if (lowerPath.find(term) != std::string::npos) {
                hasMale = true;
                break;
            }
        }
    }

    if (hasFemale && hasMale) return "dual";
    if (hasFemale) return "female";
    if (hasMale) return "male";
    return "neutral";
}

double SemanticTagger::calculateSpittingScore(const std::vector<std::string>& tags, double faceScore, double motionScore) {
    int hits = 0;
    for (const auto& t : tags) {
        if (spittingTerms_.count(t)) hits++;
    }
    double tagFactor = std::min(1.0, hits * 0.35);
    double faceFactor = (faceScore > 0.0) ? std::min(1.0, faceScore * 1.2) : 0.0;
    double motionFactor = 1.0 - std::abs(0.5 - motionScore);

    if (tagFactor > 0.0 && faceFactor > 0.0) {
        double base = 0.45 * tagFactor + 0.40 * faceFactor + 0.15 * motionFactor;
        return std::min(1.0, base + 0.20);
    } else if (faceFactor > 0.4) {
        return 0.30 * tagFactor + 0.50 * faceFactor + 0.20 * motionFactor;
    } else if (tagFactor > 0.0) {
        return 0.50 * tagFactor + 0.25 * motionFactor;
    }
    return 0.0;
}

double SemanticTagger::calculateDjScore(const std::vector<std::string>& tags, double motionScore, double faceScore) {
    int hits = 0;
    for (const auto& t : tags) {
        if (djTerms_.count(t)) hits++;
    }
    double tagFactor = std::min(1.0, hits * 0.35);
    double motionFactor = 1.0 - std::abs(0.5 - motionScore);

    if (tagFactor > 0.0) {
        double base = 0.60 * tagFactor + 0.25 * motionFactor + 0.15 * std::min(1.0, faceScore * 1.5);
        return std::min(1.0, base + 0.20);
    }
    return 0.0;
}

std::string SemanticTagger::determineContentGroup(const std::vector<std::string>& tags, double faceScore, double spittingScore, double djScore) {
    // 1. Spitting MC / Vocal Performance
    if (spittingScore >= 0.40 || (faceScore >= 0.60 && spittingScore >= 0.25)) {
        return "performance_mc";
    }
    // 2. DJ / Turntable / Party
    if (djScore >= 0.40) {
        return "party_club";
    }
    // 3. Weed / 420
    for (const auto& t : tags) {
        if (weedTerms_.count(t)) return "weed_420";
    }
    // 4. Cars & Speed
    for (const auto& t : tags) {
        if (t == "car" || t == "cars" || t == "drift" || t == "speed" || t == "race" || t == "bmw" || t == "mercedes" || t == "audi") {
            return "speed_cars";
        }
    }
    // 5. Urban Street / Graffiti
    for (const auto& t : tags) {
        if (t == "street" || t == "hood" || t == "gang" || t == "crew" || t == "graffiti" || t == "underground" || t == "subway") {
            return "urban_street";
        }
    }
    // 6. Bavarian Culture / 089
    for (const auto& t : tags) {
        if (t == "oida" || t == "minga" || t == "089" || t == "bavaria" || t == "bayern" || t == "wiesn" || t == "stadelheim") {
            return "bavaria_089";
        }
    }
    // 7. Cyber / Glitch / Tech
    for (const auto& t : tags) {
        if (t == "cyber" || t == "glitch" || t == "tech" || t == "synth" || t == "matrix" || t == "robot" || t == "future") {
            return "cyber_tech";
        }
    }
    // 8. Nature & Ambient Chill
    for (const auto& t : tags) {
        if (t == "nature" || t == "sky" || t == "sunset" || t == "forest" || t == "cloud" || t == "sea" || t == "mountain" || t == "chill") {
            return "nature_chill";
        }
    }
    return "general_loops";
}

double SemanticTagger::calculateSvoScore(const std::vector<std::string>& tags, const std::string& caption) {
    // SVO Density proxy: number of subject-verb-object keywords / tokens
    double tokenCount = static_cast<double>(tags.size());
    if (!caption.empty()) {
        tokenCount += 2.0;
    }
    return std::min(1.0, tokenCount / 6.0);
}

double SemanticTagger::calculateEmotionScore(double valence, double arousal, const std::vector<std::string>& tags) {
    // S_emotion = (|valence| + arousal) / 2
    double rawEmotion = (std::abs(valence) + arousal) / 2.0;

    for (const auto& t : tags) {
        if (t == "hype" || t == "fire" || t == "drop" || t == "aggressive" || t == "epic") {
            rawEmotion = std::min(1.0, rawEmotion + 0.25);
            break;
        }
    }
    return std::min(1.0, std::max(0.1, rawEmotion));
}

double SemanticTagger::calculateTechnicalScore(double motionScore, const std::string& cameraMovement, const std::string& shotType) {
    double camScore = (cameraMovement == "dolly" || cameraMovement == "zoom" || cameraMovement == "tracking") ? 0.85 :
                      (cameraMovement == "fast" || cameraMovement == "pan") ? 0.75 : 0.40;
    
    double shotScore = (shotType == "CU" || shotType == "MS") ? 0.80 : 0.60;

    return 0.40 * motionScore + 0.35 * camScore + 0.25 * shotScore;
}

double SemanticTagger::calculateSemanticHighlight(double svoScore, double emotionScore, double motionScore, double faceScore, double cameraScore) {
    // S_semantic = w_1 * S_svo + w_2 * S_emotion + w_3 * S_motion + w_4 * S_face + w_5 * S_camera
    // w1=0.25, w2=0.25, w3=0.20, w4=0.15, w5=0.15
    return 0.25 * svoScore + 0.25 * emotionScore + 0.20 * motionScore + 0.15 * faceScore + 0.15 * cameraScore;
}

double SemanticTagger::calculateTotalHighlight(double hSemantic, double hTechnical, double hEmotional,
                                               double alpha, double beta, double gamma) {
    // H_total = alpha * H_semantic + beta * H_technical + gamma * H_emotional
    double total = alpha * hSemantic + beta * hTechnical + gamma * hEmotional;
    return std::min(1.0, std::max(0.0, total));
}

std::string SemanticTagger::determineRecommendation(double hTotal) {
    if (hTotal >= 0.80) return "USE";
    if (hTotal >= 0.60) return "MAYBE";
    return "SKIP";
}

double SemanticTagger::determineBarsForScore(double hTotal) {
    // 140 BPM Beat-Sync Duration Decision:
    // > 0.8 -> 4 Bars (6.857s)
    // 0.6..0.8 -> 3.5 Bars (6.000s)
    // < 0.6 -> 3 Bars (5.143s)
    if (hTotal >= 0.80) return 4.0;
    if (hTotal >= 0.60) return 3.5;
    return 3.0;
}

std::string SemanticTagger::buildDescription(const std::vector<std::string>& tags,
                                            const std::string& cameraMovement,
                                            const std::string& objectFlow,
                                            double highlightScore,
                                            double motionScore,
                                            double faceScore,
                                            const std::string& recommendation) {
    std::stringstream ss;
    ss << "Content: ";
    int count = 0;
    for (const auto& t : tags) {
        if (vocab_.count(t) || weedTerms_.count(t)) {
            if (count > 0) ss << ", ";
            ss << t;
            count++;
            if (count >= 6) break;
        }
    }
    if (count == 0) {
        ss << "loop footage";
    }

    ss << " | " << cameraMovement << " camera; "
       << "object flow " << objectFlow << "; "
       << "highlight " << recommendation << " (" << std::fixed << std::setprecision(2) << highlightScore << "); "
       << "motion " << std::fixed << std::setprecision(2) << motionScore;
    
    if (faceScore > 0.3) {
        ss << "; face focus (" << std::fixed << std::setprecision(2) << faceScore << ")";
    }

    // Determine concept clusters
    std::vector<std::string> activeClusters;
    bool hasWeed = false, hasUrban = false, hasSpeed = false, hasParty = false, hasBavaria = false;
    for (const auto& t : tags) {
        if (!hasWeed && weedTerms_.count(t)) { activeClusters.push_back("🌿 Weed/420"); hasWeed = true; }
        if (!hasUrban && (t == "street" || t == "hood" || t == "gang" || t == "crew" || t == "graffiti" || t == "underground")) {
            activeClusters.push_back("🏙️ Urban/Street"); hasUrban = true;
        }
        if (!hasSpeed && (t == "car" || t == "drift" || t == "speed" || t == "bmw" || t == "mercedes" || t == "race")) {
            activeClusters.push_back("🏎️ Speed/Cars"); hasSpeed = true;
        }
        if (!hasParty && (t == "party" || t == "club" || t == "dj" || t == "rave" || t == "lights" || t == "turntable")) {
            activeClusters.push_back("🎉 Party/Club"); hasParty = true;
        }
        if (!hasBavaria && (t == "oida" || t == "minga" || t == "089" || t == "bavaria" || t == "bayern" || t == "wiesn")) {
            activeClusters.push_back("🥨 Bavaria/089"); hasBavaria = true;
        }
    }

    if (!activeClusters.empty()) {
        ss << " | ";
        for (size_t i = 0; i < activeClusters.size(); ++i) {
            ss << activeClusters[i];
            if (i + 1 < activeClusters.size()) ss << " | ";
        }
    }

    return ss.str();
}

} // namespace Oidasheim
