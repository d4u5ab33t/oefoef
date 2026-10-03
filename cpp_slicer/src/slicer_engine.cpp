#include "slicer_engine.hpp"
#include <iostream>
#include <filesystem>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <thread>
#include <future>

namespace Oidasheim {

SlicerEngine::SlicerEngine(const SlicerConfig& config)
    : config_(config), analyzer_(config), dbSync_(config) {}

std::vector<std::string> SlicerEngine::scanInputVideos() {
    std::vector<std::string> videos;
    std::filesystem::path inputPath(config_.inputDir);

    if (!std::filesystem::exists(inputPath)) {
        std::filesystem::path altPath = inputPath.string() + "s";
        if (std::filesystem::exists(altPath)) {
            inputPath = altPath;
        } else {
            std::cerr << "[SlicerEngine] Input directory not found: " << config_.inputDir << "\n";
            return videos;
        }
    }

    std::vector<std::string> validExts = { ".mp4", ".mov", ".mkv", ".avi", ".webm" };

    for (const auto& entry : std::filesystem::recursive_directory_iterator(inputPath)) {
        if (entry.is_regular_file()) {
            std::string ext = entry.path().extension().string();
            std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c){ return std::tolower(c); });
            if (std::find(validExts.begin(), validExts.end(), ext) != validExts.end()) {
                videos.push_back(entry.path().string());
            }
        }
    }

    std::sort(videos.begin(), videos.end());
    return videos;
}

std::string SlicerEngine::generateOutputClipPath(const std::string& srcFile, const std::string& contentGroup, int sliceIndex, double startSec) {
    std::filesystem::path p(srcFile);
    std::string stem = p.stem().string();

    for (char& ch : stem) {
        if (!std::isalnum(static_cast<unsigned char>(ch)) && ch != '_') {
            ch = '_';
        }
    }

    std::filesystem::path outDir(config_.clipPoolDir);
    if (!contentGroup.empty()) {
        outDir /= contentGroup;
    }
    std::filesystem::create_directories(outDir);

    std::stringstream ss;
    ss << stem << "_cut_" << std::setw(4) << std::setfill('0') << sliceIndex
       << "_t" << static_cast<int>(startSec * 10.0) << ".mp4";

    return (outDir / ss.str()).string();
}

bool SlicerEngine::exportClip(const std::string& srcFile, double startSec, double durationSec, const std::string& destFile) {
    std::filesystem::path destPath(destFile);
    std::filesystem::create_directories(destPath.parent_path());

    std::stringstream cmd;
    if (config_.fastCopyMode) {
        cmd << "ffmpeg -hide_banner -y -ss " << std::fixed << std::setprecision(3) << startSec
            << " -i \"" << srcFile << "\" -t " << durationSec
            << " -an -c:v copy -avoid_negative_ts make_zero \"" << destFile << "\" 2>&1";
    } else {
        cmd << "ffmpeg -hide_banner -y -ss " << std::fixed << std::setprecision(3) << startSec
            << " -i \"" << srcFile << "\" -t " << durationSec
            << " -an -c:v libx264 -preset veryfast -crf 18 -g 24 -pix_fmt yuv420p \"" << destFile << "\" 2>&1";
    }

    int res = std::system(cmd.str().c_str());
    if (res != 0 || !std::filesystem::exists(destPath) || std::filesystem::file_size(destPath) == 0) {
        return false;
    }
    return true;
}

void SlicerEngine::processVideoFile(const std::string& filePath) {
    std::cout << "\n=========================================================\n";
    std::cout << "[SlicerEngine] Processing: " << filePath << "\n";
    std::cout << "=========================================================\n";

    // STAGE 1: Video Probe & Scene Segmentation
    VideoSourceInfo info = analyzer_.probeVideo(filePath);
    std::cout << " [STAGE 1] Duration: " << info.duration << "s | Resolution: " 
              << info.width << "x" << info.height << " | FPS: " << info.fps << "\n";

    // Deduplication check: Skip if source already in DB/Flat Globe
    if (config_.skipProcessed && !config_.force && dbSync_.isSourceAlreadyProcessed(filePath, info.fileName)) {
        std::cout << " -> [DEDUPLICATION] Source already processed and indexed in DB/Flat Globe. Skipping duplicate!\n";
        return;
    }

    if (info.duration < config_.minDurationSec) {
        std::cout << " -> Skipped: duration too short (" << info.duration << "s)\n";
        return;
    }

    std::cout << " -> Detecting scene transition boundaries ...\n";
    std::vector<double> sceneChanges = analyzer_.detectSceneChanges(filePath);
    std::cout << "    Found " << sceneChanges.size() << " scene transition points.\n";

    // STAGE 2: Semantic Dynamics & Quality Scan
    std::cout << " [STAGE 2] Scanning visual dynamics, brightness & quality ...\n";
    std::vector<FrameSample> samples = analyzer_.scanVideoDynamics(filePath, info.duration);

    // STAGE 3 & 4: Multi-Factor Highlight Scoring & Beat-Sync Cut Generation
    std::cout << " [STAGE 3 & 4] Multi-Factor Highlight Scoring & Beat-Sync Cut Generation ...\n";
    std::vector<CutCandidate> candidates = analyzer_.generateSemanticCuts(info, sceneChanges, samples);
    std::cout << "    Generated " << candidates.size() << " quality cut candidates.\n";

    if (candidates.empty()) {
        std::cout << " -> No valid cut candidates found for this source.\n";
        return;
    }

    // Export Clips to ClipPool
    std::vector<CutCandidate> exportedClips;
    int sliceIndex = 1;

    for (auto& cand : candidates) {
        std::string outPath = generateOutputClipPath(filePath, cand.contentGroup, sliceIndex, cand.startTime);
        std::cout << " -> Cut #" << sliceIndex << " [" << cand.contentGroup << "] [" 
                  << std::fixed << std::setprecision(2) << cand.startTime << "s - " 
                  << cand.endTime << "s (" << cand.duration << "s / " << cand.bars << " bars)]\n"
                  << "    Score: " << std::fixed << std::setprecision(2) << cand.highlightScore 
                  << " [" << cand.recommendation << "] (Sem: " << cand.hSemantic 
                  << ", Tech: " << cand.hTechnical << ", Emo: " << cand.hEmotional << ")\n"
                  << "    Desc:  " << cand.description << "\n";

        // Check if clip file already exists
        if (!config_.force && std::filesystem::exists(outPath) && std::filesystem::file_size(outPath) > 0) {
            std::cout << "    -> Clip file already exists, skipping re-encode: " << outPath << "\n";
            cand.outputPath = outPath;
            exportedClips.push_back(cand);
            sliceIndex++;
            continue;
        }

        if (exportClip(filePath, cand.startTime, cand.duration, outPath)) {
            cand.outputPath = outPath;
            exportedClips.push_back(cand);
            sliceIndex++;
        } else {
            std::cerr << "    [ERROR] Failed to export clip: " << outPath << "\n";
        }
    }

    // Stage 4 Final: DB & Flat Globe Sync
    if (!exportedClips.empty()) {
        std::cout << " -> Updating Database (SQLite) ...\n";
        dbSync_.recordClipsInDb(exportedClips, info);

        std::cout << " -> Updating Flat Globe Cache (" << config_.flatGlobeJson << ") ...\n";
        dbSync_.updateFlatGlobeJson(exportedClips, info);

        std::cout << " -> Successfully synchronized " << exportedClips.size() << " clips into ClipPool and DB!\n";
    }
}

void SlicerEngine::runPipeline() {
    std::cout << "#########################################################\n";
    std::cout << "# OIDASHEIM 4-STAGE SEMANTIC VIDEO CLIP EXTRACTOR       #\n";
    std::cout << "# (Scene Segmentation -> Semantic Tagging -> Highlight  #\n";
    std::cout << "#  Scoring -> Beat-Sync 140 BPM Clip Generation)        #\n";
    std::cout << "#########################################################\n";
    std::cout << "Input Directory:   " << config_.inputDir << "\n";
    std::cout << "Clip Pool Target:  " << config_.clipPoolDir << "\n";
    std::cout << "Database Target:   " << config_.dbPath << "\n";
    std::cout << "Flat Globe JSON:   " << config_.flatGlobeJson << "\n";
    std::cout << "Target BPM:        " << config_.bpm << " (1 Bar = " << (4.0 * 60.0 / config_.bpm) << "s)\n";

    auto videos = scanInputVideos();
    std::cout << "\nFound " << videos.size() << " long loop video files to process.\n";

    for (size_t i = 0; i < videos.size(); ++i) {
        std::cout << "\n[" << (i + 1) << "/" << videos.size() << "] Processing " << videos[i] << " ...\n";
        processVideoFile(videos[i]);
    }

    std::cout << "\n=========================================================\n";
    std::cout << "[SlicerEngine] 4-Stage Video Clip Extraction Finished Successfully!\n";
    std::cout << "=========================================================\n";
}

} // namespace Oidasheim
