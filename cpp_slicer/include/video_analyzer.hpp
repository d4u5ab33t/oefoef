#pragma once

#include "types.hpp"
#include "semantic_tagger.hpp"
#include <string>
#include <vector>

namespace Oidasheim {

struct FrameSample {
    double timestamp = 0.0;
    double brightness = 0.0;
    double diffFromPrev = 0.0;
    bool isBlack = false;
    bool isFrozen = false;
};

class VideoAnalyzer {
public:
    explicit VideoAnalyzer(const SlicerConfig& config);

    VideoSourceInfo probeVideo(const std::string& videoPath);
    
    std::vector<double> detectSceneChanges(const std::string& videoPath);
    
    std::vector<FrameSample> scanVideoDynamics(const std::string& videoPath, double duration);
    
    std::vector<CutCandidate> generateSemanticCuts(const VideoSourceInfo& info,
                                                   const std::vector<double>& sceneChanges,
                                                   const std::vector<FrameSample>& samples);

private:
    SlicerConfig config_;
    SemanticTagger tagger_;

    std::string execCommand(const std::string& cmd);
    bool checkClipQuality(const std::vector<FrameSample>& samples, double start, double end);
    double estimateMotion(const std::vector<FrameSample>& samples, double start, double end);
};

} // namespace Oidasheim
