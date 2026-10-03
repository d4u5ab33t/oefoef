#pragma once

#include "types.hpp"
#include <string>
#include <vector>
#include <set>
#include <unordered_set>

namespace Oidasheim {

class SemanticTagger {
public:
    SemanticTagger();

    std::vector<std::string> extractTagsFromPath(const std::string& path);
    
    std::string determineGender(const std::vector<std::string>& tags, const std::string& path);
    
    double calculateSpittingScore(const std::vector<std::string>& tags, double faceScore, double motionScore);
    
    double calculateDjScore(const std::vector<std::string>& tags, double motionScore, double faceScore);

    std::string determineContentGroup(const std::vector<std::string>& tags, double faceScore, double spittingScore, double djScore);
    
    // Multi-factor highlight scoring
    double calculateSvoScore(const std::vector<std::string>& tags, const std::string& caption);
    double calculateEmotionScore(double valence, double arousal, const std::vector<std::string>& tags);
    double calculateTechnicalScore(double motionScore, const std::string& cameraMovement, const std::string& shotType);
    double calculateSemanticHighlight(double svoScore, double emotionScore, double motionScore, double faceScore, double cameraScore);
    
    double calculateTotalHighlight(double hSemantic, double hTechnical, double hEmotional,
                                   double alpha = 0.40, double beta = 0.30, double gamma = 0.30);
    
    std::string determineRecommendation(double hTotal);
    double determineBarsForScore(double hTotal);
    
    std::string buildDescription(const std::vector<std::string>& tags,
                                 const std::string& cameraMovement,
                                 const std::string& objectFlow,
                                 double highlightScore,
                                 double motionScore,
                                 double faceScore,
                                 const std::string& recommendation);

private:
    std::unordered_set<std::string> vocab_;
    std::unordered_set<std::string> femaleTerms_;
    std::unordered_set<std::string> maleTerms_;
    std::unordered_set<std::string> spittingTerms_;
    std::unordered_set<std::string> djTerms_;
    std::unordered_set<std::string> weedTerms_;

    void initVocabularies();
};

} // namespace Oidasheim
