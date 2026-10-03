#include "video_analyzer.hpp"
#include <iostream>
#include <sstream>
#include <regex>
#include <cmath>
#include <algorithm>
#include <filesystem>
#include <array>
#include <memory>

#ifdef _WIN32
#define popen _popen
#define pclose _pclose
#endif

namespace Oidasheim {

VideoAnalyzer::VideoAnalyzer(const SlicerConfig& config)
    : config_(config) {}

std::string VideoAnalyzer::execCommand(const std::string& cmd) {
    std::array<char, 4096> buffer;
    std::string result;
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(cmd.c_str(), "r"), pclose);
    if (!pipe) {
        return "";
    }
    while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe.get()) != nullptr) {
        result += buffer.data();
    }
    return result;
}

VideoSourceInfo VideoAnalyzer::probeVideo(const std::string& videoPath) {
    VideoSourceInfo info;
    info.filePath = videoPath;
    
    std::filesystem::path p(videoPath);
    info.fileName = p.filename().string();
    try {
        info.fileSize = std::filesystem::file_size(p);
    } catch (...) {
        info.fileSize = 0;
    }

    std::stringstream cmd;
    cmd << "ffprobe -v error -select_streams v:0 "
        << "-show_entries stream=width,height,r_frame_rate,codec_name:format=duration "
        << "-of default=noprint_wrappers=1 \"" << videoPath << "\" 2>&1";

    std::string output = execCommand(cmd.str());
    std::istringstream iss(output);
    std::string line;

    while (std::getline(iss, line)) {
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = line.substr(0, eq);
        std::string val = line.substr(eq + 1);

        if (key == "width") {
            info.width = std::atoi(val.c_str());
        } else if (key == "height") {
            info.height = std::atoi(val.c_str());
        } else if (key == "codec_name") {
            info.codec = val;
        } else if (key == "duration") {
            info.duration = std::atof(val.c_str());
        } else if (key == "r_frame_rate") {
            size_t slash = val.find('/');
            if (slash != std::string::npos) {
                double num = std::atof(val.substr(0, slash).c_str());
                double den = std::atof(val.substr(slash + 1).c_str());
                if (den > 0) info.fps = num / den;
            } else {
                info.fps = std::atof(val.c_str());
            }
        }
    }

    if (info.fps <= 0.0) info.fps = 24.0;
    return info;
}

std::vector<double> VideoAnalyzer::detectSceneChanges(const std::string& videoPath) {
    std::vector<double> scenes;
    std::stringstream cmd;
    cmd << "ffmpeg -hide_banner -i \"" << videoPath << "\" "
        << "-filter:v \"select='gt(scene," << config_.sceneThreshold << ")',metadata=print:file=-\" "
        << "-an -f null - 2>&1";

    std::string output = execCommand(cmd.str());
    std::regex ptsRegex(R"(pts_time:([0-9.]+))");
    auto words_begin = std::sregex_iterator(output.begin(), output.end(), ptsRegex);
    auto words_end = std::sregex_iterator();

    for (std::sregex_iterator i = words_begin; i != words_end; ++i) {
        std::smatch match = *i;
        double t = std::atof(match[1].str().c_str());
        if (scenes.empty() || (t - scenes.back()) > 0.5) {
            scenes.push_back(t);
        }
    }

    return scenes;
}

std::vector<FrameSample> VideoAnalyzer::scanVideoDynamics(const std::string& videoPath, double duration) {
    std::vector<FrameSample> samples;
    if (duration <= 0.0) return samples;

    std::stringstream cmd;
    cmd << "ffmpeg -hide_banner -i \"" << videoPath << "\" "
        << "-vf \"fps=4,scale=320:-2:flags=fast_bilinear,signalstats,metadata=print:file=-\" "
        << "-an -f null - 2>&1";

    std::string output = execCommand(cmd.str());
    std::regex yavgRegex(R"(YAVG=([0-9.]+))");
    auto words_begin = std::sregex_iterator(output.begin(), output.end(), yavgRegex);
    auto words_end = std::sregex_iterator();

    int idx = 0;
    double prevY = 0.0;
    for (std::sregex_iterator i = words_begin; i != words_end; ++i) {
        std::smatch match = *i;
        double yVal = std::atof(match[1].str().c_str());
        
        FrameSample fs;
        fs.timestamp = idx * 0.25; // 4 fps = 0.25s per frame
        fs.brightness = yVal;
        fs.diffFromPrev = (idx > 0) ? std::abs(yVal - prevY) : 0.0;
        fs.isBlack = (yVal < 14.0); // Black or ultra-dark
        fs.isFrozen = (idx > 0 && fs.diffFromPrev < 0.20);

        samples.push_back(fs);
        prevY = yVal;
        idx++;
    }

    return samples;
}

bool VideoAnalyzer::checkClipQuality(const std::vector<FrameSample>& samples, double start, double end) {
    if (samples.empty()) return true;

    int totalInWindow = 0;
    int blackCount = 0;
    int frozenCount = 0;

    for (const auto& s : samples) {
        if (s.timestamp >= start && s.timestamp <= end) {
            totalInWindow++;
            if (s.isBlack) blackCount++;
            if (s.isFrozen) frozenCount++;
        }
    }

    if (totalInWindow == 0) return true;
    double blackRatio = static_cast<double>(blackCount) / totalInWindow;
    double frozenRatio = static_cast<double>(frozenCount) / totalInWindow;

    // Reject if > 25% black or > 40% completely frozen
    if (blackRatio > 0.25 || frozenRatio > 0.40) {
        return false;
    }
    return true;
}

double VideoAnalyzer::estimateMotion(const std::vector<FrameSample>& samples, double start, double end) {
    if (samples.empty()) return 0.45;

    double sumDiff = 0.0;
    int count = 0;

    for (const auto& s : samples) {
        if (s.timestamp >= start && s.timestamp <= end) {
            sumDiff += s.diffFromPrev;
            count++;
        }
    }

    if (count == 0) return 0.45;
    double avgDiff = sumDiff / count;
    double score = std::min(1.0, avgDiff / 8.0);
    return std::max(0.1, score);
}

std::vector<CutCandidate> VideoAnalyzer::generateSemanticCuts(const VideoSourceInfo& info,
                                                             const std::vector<double>& sceneChanges,
                                                             const std::vector<FrameSample>& samples) {
    std::vector<CutCandidate> candidates;
    if (info.duration <= config_.minDurationSec) return candidates;

    // 140 BPM Beat-Sync Math:
    // 1 Beat = 60 / 140 = 0.42857 s
    // 1 Bar = 4 Beats = 1.71428 s
    // 4 Bars = 6.857 s | 3.5 Bars = 6.000 s | 3 Bars = 5.143 s
    double beatDur = 60.0 / config_.bpm;
    double barDur = 4.0 * beatDur;

    // Anchor points: scene changes
    std::vector<double> cutPoints = { 0.0 };
    for (double sc : sceneChanges) {
        if (sc > config_.minDurationSec && sc < (info.duration - config_.minDurationSec)) {
            cutPoints.push_back(sc);
        }
    }
    cutPoints.push_back(info.duration);
    std::sort(cutPoints.begin(), cutPoints.end());

    auto tags = tagger_.extractTagsFromPath(info.filePath);

    double currentPos = 0.0;
    while (currentPos < info.duration - config_.minDurationSec) {
        // Find next scene boundary
        double nextScene = info.duration;
        for (double cp : cutPoints) {
            if (cp > currentPos + config_.minDurationSec) {
                nextScene = cp;
                break;
            }
        }

        // Estimate preliminary motion & emotion in the window
        double windowEnd = std::min(info.duration, currentPos + 4.0 * barDur);
        double preliminaryMotion = estimateMotion(samples, currentPos, windowEnd);
        double preliminaryFace = (info.fileName.find("portrait") != std::string::npos ||
                                  info.fileName.find("face") != std::string::npos) ? 0.85 : 0.0;

        // Stage 2 & 3: Multi-Factor Scoring
        double svoScore = tagger_.calculateSvoScore(tags, "");
        double emotionScore = tagger_.calculateEmotionScore(0.2, 0.7, tags);
        std::string camMov = (preliminaryMotion > 0.65) ? "fast" :
                             (preliminaryMotion > 0.25) ? "tracking" : "static";
        std::string shotType = (preliminaryFace > 0.4) ? "CU" : "MS";

        double hSem = tagger_.calculateSemanticHighlight(svoScore, emotionScore, preliminaryMotion, preliminaryFace, 0.75);
        double hTech = tagger_.calculateTechnicalScore(preliminaryMotion, camMov, shotType);
        double hEmo = emotionScore;

        double hTotal = tagger_.calculateTotalHighlight(hSem, hTech, hEmo, config_.alpha, config_.beta, config_.gamma);
        std::string recommendation = tagger_.determineRecommendation(hTotal);
        
        // Stage 4: Dynamic Length Variation (1.0 to 4.0 Bars) based on Movement & Highlights:
        // - Fast motion / action burst (motion >= 0.70) -> 1.0 or 2.0 Bars (snappy cuts)
        // - Epic highlight / Face / Performance (hTotal >= 0.85 or face >= 0.70) -> 4.0 Bars (full showcase)
        // - Steady tracking flow (0.35 <= motion < 0.70, hTotal >= 0.70) -> 3.0 or 3.5 Bars
        // - Static scene (motion < 0.25) -> 1.0 Bar (short, avoids boring freeze feel)
        // - Standard default -> 2.0 Bars
        double bars = 2.0;
        if (preliminaryMotion >= 0.70) {
            bars = (hTotal >= 0.80) ? 2.0 : 1.0;
        } else if (hTotal >= 0.85 || preliminaryFace >= 0.70) {
            bars = 4.0;
        } else if (hTotal >= 0.70 && preliminaryMotion >= 0.35) {
            bars = 3.5;
        } else if (preliminaryMotion < 0.25) {
            bars = 1.0;
        } else {
            bars = (hTotal >= 0.60) ? 2.0 : 1.0;
        }

        double chosenDuration = bars * barDur;

        // Ensure within bounds and available scene time
        if (chosenDuration > (nextScene - currentPos) && (nextScene - currentPos) >= config_.minDurationSec) {
            chosenDuration = nextScene - currentPos;
            bars = std::round((chosenDuration / barDur) * 2.0) / 2.0;
            if (bars < 1.0) bars = 1.0;
        }
        if (chosenDuration < config_.minDurationSec) chosenDuration = config_.minDurationSec;
        if (chosenDuration > config_.maxDurationSec) chosenDuration = config_.maxDurationSec;

        // Highlight & Movement Peak Picking: Find optimal start point in local window
        double bestStart = currentPos;
        double maxWindowEnergy = preliminaryMotion;
        if ((nextScene - currentPos) > chosenDuration + 1.0) {
            double searchLimit = std::min(currentPos + 2.0 * barDur, nextScene - chosenDuration);
            for (double tCandidate = currentPos; tCandidate <= searchLimit; tCandidate += 0.5) {
                double m = estimateMotion(samples, tCandidate, tCandidate + chosenDuration);
                if (m > maxWindowEnergy) {
                    maxWindowEnergy = m;
                    bestStart = tCandidate;
                }
            }
        }

        double cutStart = bestStart;
        double cutEnd = std::min(info.duration, cutStart + chosenDuration);

        // Quality check (reject black/freeze)
        if (checkClipQuality(samples, cutStart, cutEnd)) {
            CutCandidate candidate;
            candidate.startTime = cutStart;
            candidate.endTime = cutEnd;
            candidate.duration = cutEnd - cutStart;
            candidate.startFrame = static_cast<int64_t>(std::round(cutStart * info.fps));
            candidate.endFrame = static_cast<int64_t>(std::round(cutEnd * info.fps));
            candidate.bars = bars;

            candidate.hSemantic = hSem;
            candidate.hTechnical = hTech;
            candidate.hEmotional = hEmo;
            candidate.highlightScore = hTotal;
            candidate.recommendation = recommendation;

            candidate.motionScore = maxWindowEnergy;
            candidate.motionDirection = (candidate.motionScore > 0.5) ? 0.35 : 0.0;
            candidate.faceScore = preliminaryFace;
            
            candidate.spittingScore = tagger_.calculateSpittingScore(tags, candidate.faceScore, candidate.motionScore);
            candidate.djActionScore = tagger_.calculateDjScore(tags, candidate.motionScore, candidate.faceScore);

            candidate.cameraMovement = camMov;
            candidate.shotType = shotType;
            candidate.objectFlow = (candidate.motionScore >= 0.20) ? "continuous" : "broken";
            candidate.tags = tags;
            candidate.contentGroup = tagger_.determineContentGroup(tags, candidate.faceScore, candidate.spittingScore, candidate.djActionScore);

            candidate.description = tagger_.buildDescription(tags, candidate.cameraMovement,
                                                             candidate.objectFlow, candidate.highlightScore,
                                                             candidate.motionScore, candidate.faceScore,
                                                             candidate.recommendation);

            candidates.push_back(candidate);
        }

        currentPos = cutEnd;
    }

    return candidates;
}

} // namespace Oidasheim
