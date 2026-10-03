#include "db_sync.hpp"
#include <iostream>
#include <fstream>
#include <sstream>
#include <filesystem>
#include <iomanip>
#include <chrono>
#include <array>
#include <memory>

namespace Oidasheim {

DbSync::DbSync(const SlicerConfig& config)
    : config_(config) {}

bool DbSync::executeSql(const std::string& sql) {
    std::filesystem::path dbPath(config_.dbPath);
    if (!std::filesystem::exists(dbPath.parent_path())) {
        std::filesystem::create_directories(dbPath.parent_path());
    }

    std::filesystem::path sqlScript = dbPath.parent_path() / "temp_sync.sql";
    {
        std::ofstream ofs(sqlScript);
        if (!ofs) return false;
        ofs << "PRAGMA journal_mode=WAL;\n"
            << "PRAGMA synchronous=NORMAL;\n"
            << "BEGIN TRANSACTION;\n"
            << sql
            << "\nCOMMIT;\n";
    }

    std::stringstream cmd;
    cmd << "sqlite3 \"" << config_.dbPath << "\" < \"" << sqlScript.string() << "\" 2>&1";
    int res = std::system(cmd.str().c_str());

    std::error_code ec;
    std::filesystem::remove(sqlScript, ec);
    return res == 0;
}

bool DbSync::isSourceAlreadyProcessed(const std::string& sourcePath, const std::string& fileName) {
    // 1. Check Flat Globe JSON
    std::filesystem::path globePath(config_.flatGlobeJson);
    if (std::filesystem::exists(globePath)) {
        std::ifstream ifs(globePath);
        std::string line;
        while (std::getline(ifs, line)) {
            if (line.find("\"source_loop\": \"" + fileName + "\"") != std::string::npos) {
                return true;
            }
        }
    }

    // 2. Check SQLite Database
    std::filesystem::path dbPath(config_.dbPath);
    if (std::filesystem::exists(dbPath)) {
        std::string query = "SELECT COUNT(*) FROM longloops_slices WHERE source_file='" + fileName + "' OR source_file='" + sourcePath + "';";
        std::stringstream cmd;
        cmd << "sqlite3 \"" << config_.dbPath << "\" \"" << query << "\" 2>nul";
        
        std::array<char, 128> buffer;
        std::string result;
        std::unique_ptr<FILE, decltype(&_pclose)> pipe(_popen(cmd.str().c_str(), "r"), _pclose);
        if (pipe) {
            while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe.get()) != nullptr) {
                result += buffer.data();
            }
            int count = std::atoi(result.c_str());
            if (count > 0) return true;
        }
    }

    return false;
}

bool DbSync::recordClipsInDb(const std::vector<CutCandidate>& clips, const VideoSourceInfo& source) {
    std::stringstream sql;
    sql << "CREATE TABLE IF NOT EXISTS longloops_slices (\n"
        << "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        << "  source_file TEXT NOT NULL,\n"
        << "  clip_path TEXT UNIQUE NOT NULL,\n"
        << "  start_time REAL NOT NULL,\n"
        << "  end_time REAL NOT NULL,\n"
        << "  duration REAL NOT NULL,\n"
        << "  start_frame INTEGER,\n"
        << "  end_frame INTEGER,\n"
        << "  bars REAL,\n"
        << "  recommendation TEXT,\n"
        << "  h_semantic REAL,\n"
        << "  h_technical REAL,\n"
        << "  h_emotional REAL,\n"
        << "  motion_score REAL,\n"
        << "  spitting_score REAL,\n"
        << "  dj_action_score REAL,\n"
        << "  highlight_score REAL,\n"
        << "  description TEXT,\n"
        << "  created_at REAL NOT NULL\n"
        << ");\n\n";

    auto nowSec = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    for (const auto& c : clips) {
        if (c.outputPath.empty()) continue;

        std::string safeDesc = c.description;
        size_t pos = 0;
        while ((pos = safeDesc.find("'", pos)) != std::string::npos) {
            safeDesc.replace(pos, 1, "''");
            pos += 2;
        }

        std::string safePath = c.outputPath;
        pos = 0;
        while ((pos = safePath.find("'", pos)) != std::string::npos) {
            safePath.replace(pos, 1, "''");
            pos += 2;
        }

        std::string safeSrc = source.filePath;
        pos = 0;
        while ((pos = safeSrc.find("'", pos)) != std::string::npos) {
            safeSrc.replace(pos, 1, "''");
            pos += 2;
        }

        sql << "INSERT INTO longloops_slices (source_file, clip_path, start_time, end_time, duration, "
            << "start_frame, end_frame, bars, recommendation, h_semantic, h_technical, h_emotional, "
            << "motion_score, spitting_score, dj_action_score, highlight_score, description, created_at) "
            << "VALUES ('" << safeSrc << "', '" << safePath << "', "
            << c.startTime << ", " << c.endTime << ", " << c.duration << ", "
            << c.startFrame << ", " << c.endFrame << ", " << c.bars << ", '" << c.recommendation << "', "
            << c.hSemantic << ", " << c.hTechnical << ", " << c.hEmotional << ", "
            << c.motionScore << ", " << c.spittingScore << ", " << c.djActionScore << ", "
            << c.highlightScore << ", '" << safeDesc << "', " << nowSec << ") "
            << "ON CONFLICT(clip_path) DO UPDATE SET "
            << "recommendation=excluded.recommendation, highlight_score=excluded.highlight_score, "
            << "description=excluded.description;\n";
    }

    return executeSql(sql.str());
}

std::string DbSync::buildJsonEntry(const CutCandidate& clip, const VideoSourceInfo& source) {
    std::stringstream ss;
    ss << "    {\n";
    ss << "      \"duration\": " << std::fixed << std::setprecision(3) << clip.duration << ",\n";
    ss << "      \"width\": " << (source.width > 0 ? source.width : config_.targetWidth) << ",\n";
    ss << "      \"height\": " << (source.height > 0 ? source.height : config_.targetHeight) << ",\n";
    ss << "      \"aspect_ratio\": \"" << (source.width > 0 ? std::to_string(source.width) : "1920")
       << ":" << (source.height > 0 ? std::to_string(source.height) : "1080") << "\",\n";
    ss << "      \"aspect_ratio_float\": 1.778,\n";
    ss << "      \"start_frame\": " << clip.startFrame << ",\n";
    ss << "      \"end_frame\": " << clip.endFrame << ",\n";
    ss << "      \"bars\": " << std::fixed << std::setprecision(1) << clip.bars << ",\n";
    ss << "      \"tags\": [";
    for (size_t i = 0; i < clip.tags.size(); ++i) {
        ss << "\"" << clip.tags[i] << "\"";
        if (i + 1 < clip.tags.size()) ss << ", ";
    }
    ss << "],\n";
    ss << "      \"vector\": [],\n";
    ss << "      \"motion_score\": " << std::fixed << std::setprecision(3) << clip.motionScore << ",\n";
    ss << "      \"motion_direction\": " << std::fixed << std::setprecision(4) << clip.motionDirection << ",\n";
    ss << "      \"face_score\": " << std::fixed << std::setprecision(3) << clip.faceScore << ",\n";
    ss << "      \"spitting_score\": " << std::fixed << std::setprecision(3) << clip.spittingScore << ",\n";
    ss << "      \"is_spitting_performance\": " << (clip.spittingScore >= 0.40 ? "true" : "false") << ",\n";
    ss << "      \"dj_action_score\": " << std::fixed << std::setprecision(3) << clip.djActionScore << ",\n";
    ss << "      \"is_dj_action\": " << (clip.djActionScore >= 0.45 ? "true" : "false") << ",\n";
    ss << "      \"h_semantic\": " << std::fixed << std::setprecision(3) << clip.hSemantic << ",\n";
    ss << "      \"h_technical\": " << std::fixed << std::setprecision(3) << clip.hTechnical << ",\n";
    ss << "      \"h_emotional\": " << std::fixed << std::setprecision(3) << clip.hEmotional << ",\n";
    ss << "      \"highlight_score\": " << std::fixed << std::setprecision(3) << clip.highlightScore << ",\n";
    ss << "      \"highlight_recommendation\": \"" << clip.recommendation << "\",\n";
    ss << "      \"camera\": \"" << clip.cameraMovement << "\",\n";
    ss << "      \"camera_movement\": \"" << clip.cameraMovement << "\",\n";
    ss << "      \"shot_type\": \"" << clip.shotType << "\",\n";
    ss << "      \"lighting\": \"natural\",\n";
    ss << "      \"color\": \"neutral\",\n";
    ss << "      \"object_flow\": \"" << clip.objectFlow << "\",\n";
    ss << "      \"playback_ok\": true,\n";
    
    std::string escapedDesc;
    for (char ch : clip.description) {
        if (ch == '"') escapedDesc += "\\\"";
        else if (ch == '\\') escapedDesc += "\\\\";
        else escapedDesc += ch;
    }

    ss << "      \"description\": \"" << escapedDesc << "\",\n";
    ss << "      \"analysis_version\": 6,\n";
    ss << "      \"source_loop\": \"" << source.fileName << "\",\n";
    ss << "      \"loop_slice_range\": [" << clip.startTime << ", " << clip.endTime << "]\n";
    ss << "    }";
    return ss.str();
}

bool DbSync::updateFlatGlobeJson(const std::vector<CutCandidate>& clips, const VideoSourceInfo& source) {
    std::filesystem::path globePath(config_.flatGlobeJson);
    if (!std::filesystem::exists(globePath.parent_path())) {
        std::filesystem::create_directories(globePath.parent_path());
    }

    std::string existingContent;
    if (std::filesystem::exists(globePath)) {
        std::ifstream ifs(globePath);
        std::stringstream ss;
        ss << ifs.rdbuf();
        existingContent = ss.str();
    }

    size_t lastBrace = existingContent.rfind('}');
    std::stringstream newJson;
    if (existingContent.empty() || lastBrace == std::string::npos) {
        newJson << "{\n";
    } else {
        std::string prefix = existingContent.substr(0, lastBrace);
        while (!prefix.empty() && (prefix.back() == ' ' || prefix.back() == '\t' || prefix.back() == '\r' || prefix.back() == '\n')) {
            prefix.pop_back();
        }
        newJson << prefix;
        if (prefix.find('{') != std::string::npos && prefix.length() > 2) {
            newJson << ",\n";
        }
    }

    for (size_t i = 0; i < clips.size(); ++i) {
        const auto& c = clips[i];
        if (c.outputPath.empty()) continue;

        std::string jsonPath;
        for (char ch : c.outputPath) {
            if (ch == '\\') jsonPath += "\\\\";
            else jsonPath += ch;
        }

        newJson << "  \"" << jsonPath << "\": " << buildJsonEntry(c, source);
        if (i + 1 < clips.size()) {
            newJson << ",\n";
        } else {
            newJson << "\n";
        }
    }

    newJson << "}\n";

    std::filesystem::path tmpPath = globePath.parent_path() / (globePath.filename().string() + ".tmp");
    std::filesystem::path bakPath = globePath.parent_path() / (globePath.filename().string() + ".bak");

    {
        std::ofstream ofs(tmpPath);
        if (!ofs) return false;
        ofs << newJson.str();
    }

    std::error_code ec;
    if (std::filesystem::exists(globePath)) {
        std::filesystem::copy_file(globePath, bakPath, std::filesystem::copy_options::overwrite_existing, ec);
    }

    std::filesystem::rename(tmpPath, globePath, ec);
    return !ec;
}

} // namespace Oidasheim
