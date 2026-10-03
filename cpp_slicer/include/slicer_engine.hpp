#pragma once

#include "types.hpp"
#include "video_analyzer.hpp"
#include "db_sync.hpp"
#include <string>
#include <vector>

namespace Oidasheim {

class SlicerEngine {
public:
    explicit SlicerEngine(const SlicerConfig& config);

    void runPipeline();
    
    std::vector<std::string> scanInputVideos();
    
    void processVideoFile(const std::string& filePath);

    bool exportClip(const std::string& srcFile, double startSec, double durationSec, const std::string& destFile);

private:
    SlicerConfig config_;
    VideoAnalyzer analyzer_;
    DbSync dbSync_;

    std::string generateOutputClipPath(const std::string& srcFile, const std::string& contentGroup, int sliceIndex, double startSec);
};

} // namespace Oidasheim
