#pragma once

#include "types.hpp"
#include <string>
#include <vector>

namespace Oidasheim {

class DbSync {
public:
    explicit DbSync(const SlicerConfig& config);

    bool recordClipsInDb(const std::vector<CutCandidate>& clips, const VideoSourceInfo& source);
    
    bool updateFlatGlobeJson(const std::vector<CutCandidate>& clips, const VideoSourceInfo& source);

    bool isSourceAlreadyProcessed(const std::string& sourcePath, const std::string& fileName);

private:
    SlicerConfig config_;

    std::string buildJsonEntry(const CutCandidate& clip, const VideoSourceInfo& source);
    bool executeSql(const std::string& sql);
};

} // namespace Oidasheim
