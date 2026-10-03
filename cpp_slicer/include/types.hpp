#pragma once

#include <string>
#include <vector>
#include <map>
#include <chrono>

namespace Oidasheim {

struct CutCandidate {
    double startTime = 0.0;
    double endTime = 0.0;
    double duration = 0.0;
    int64_t startFrame = 0;
    int64_t endFrame = 0;
    double bars = 3.5;

    // Multi-factor highlight scoring
    double hSemantic = 0.0;   // SVO density, narrative relevance
    double hTechnical = 0.0;  // Motion dynamics, camera motion, framing
    double hEmotional = 0.0;  // Valence-Arousal & visual vibrancy
    double highlightScore = 0.0; // H_total = alpha * H_sem + beta * H_tech + gamma * H_emo
    std::string recommendation = "MAYBE"; // "USE" (>0.8), "MAYBE" (0.6..0.8), "SKIP" (<0.6)

    // Detailed metrics
    double motionScore = 0.0;
    double motionDirection = 0.0; // -1.0 (left) .. +1.0 (right)
    double faceScore = 0.0;
    double spittingScore = 0.0;
    double djActionScore = 0.0;
    double valence = 0.0;
    double arousal = 0.5;
    
    std::string cameraMovement = "tracking"; // static, pan, dolly, zoom, tracking, fast
    std::string shotType = "MS"; // ELS, LS, MS, CU, ECU
    std::string objectFlow = "continuous";
    std::string dominantColorHex = "#202020";
    
    std::vector<std::string> tags;
    std::string contentGroup = "general_loops";
    std::string caption;
    std::string description;
    std::string outputPath;
};

struct VideoSourceInfo {
    std::string filePath;
    std::string fileName;
    double duration = 0.0;
    int width = 0;
    int height = 0;
    double fps = 24.0;
    int64_t fileSize = 0;
    std::string codec;
};

struct SlicerConfig {
    std::string inputDir = "D:\\Oidasheim\\NFOs\\longloops";
    std::string clipPoolDir = "J:\\raw_vidz\\_raw_reorga__";
    std::string dbPath = "J:\\Oidasheim\\mo.gen\\beat_sync.db";
    std::string flatGlobeJson = "J:\\Oidasheim\\mo.gen\\libsync-flat-globe.db.json";
    
    double bpm = 140.0;
    double minDurationSec = 1.8;
    double maxDurationSec = 8.5;
    double targetFps = 24.0;
    int targetWidth = 1920;
    int targetHeight = 1080;
    double sceneThreshold = 0.28;
    int maxThreads = 4;
    bool fastCopyMode = false;
    bool skipProcessed = true; // Avoid re-using/re-slicing duplicate source files
    bool force = false;         // Overwrite/reprocess even if already exists
    bool verbose = true;

    // Weights for H_total = alpha * H_semantic + beta * H_technical + gamma * H_emotional
    double alpha = 0.40;
    double beta = 0.30;
    double gamma = 0.30;
};

} // namespace Oidasheim
