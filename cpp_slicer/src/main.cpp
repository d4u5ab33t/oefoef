#include "slicer_engine.hpp"
#include <iostream>
#include <string>

void printUsage() {
    std::cout << "Usage: oidasheim_slicer [options]\n\n"
              << "Options:\n"
              << "  --input <path>       Input directory with long videos (default: D:\\Oidasheim\\NFOs\\longloops)\n"
              << "  --clip-pool <path>   Target ClipPool directory (default: J:\\raw_vidz\\_raw_reorga__)\n"
              << "  --db <path>          Path to SQLite database (default: J:\\Oidasheim\\mo.gen\\beat_sync.db)\n"
              << "  --globe <path>       Path to Flat Globe JSON (default: J:\\Oidasheim\\mo.gen\\libsync-flat-globe.db.json)\n"
              << "  --bpm <value>        Target musical BPM for bar alignment (default: 140.0)\n"
              << "  --min-dur <sec>      Minimum cut duration in seconds (default: 1.8)\n"
              << "  --max-dur <sec>      Maximum cut duration in seconds (default: 8.5)\n"
              << "  --fast-copy          Use direct stream copy without re-encoding (faster, keyframe-aligned)\n"
              << "  --force              Force reprocessing and overwrite existing clips (ignore duplicate check)\n"
              << "  --help               Display this help message\n";
}

int main(int argc, char* argv[]) {
    Oidasheim::SlicerConfig config;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--input" && i + 1 < argc) {
            config.inputDir = argv[++i];
        } else if (arg == "--clip-pool" && i + 1 < argc) {
            config.clipPoolDir = argv[++i];
        } else if (arg == "--db" && i + 1 < argc) {
            config.dbPath = argv[++i];
        } else if (arg == "--globe" && i + 1 < argc) {
            config.flatGlobeJson = argv[++i];
        } else if (arg == "--bpm" && i + 1 < argc) {
            config.bpm = std::atof(argv[++i]);
        } else if (arg == "--min-dur" && i + 1 < argc) {
            config.minDurationSec = std::atof(argv[++i]);
        } else if (arg == "--max-dur" && i + 1 < argc) {
            config.maxDurationSec = std::atof(argv[++i]);
        } else if (arg == "--fast-copy") {
            config.fastCopyMode = true;
        } else if (arg == "--force") {
            config.force = true;
        } else if (arg == "--help" || arg == "-h") {
            printUsage();
            return 0;
        }
    }

    try {
        Oidasheim::SlicerEngine engine(config);
        engine.runPipeline();
    } catch (const std::exception& ex) {
        std::cerr << "[FATAL ERROR] " << ex.what() << "\n";
        return 1;
    }

    return 0;
}
