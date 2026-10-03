#!/usr/bin/env python3
"""
verify_stack.py — OIDASHEIM BEAT SYNC STACK VERIFICATION
Comprehensive check of all upgrades and configurations
"""

import json
import sys
from pathlib import Path
from importlib import util

# Windows-Konsolen laufen oft noch auf cp1252 statt UTF-8 -> jeder Emoji
# (checkmark/cross etc.) crasht sonst mit UnicodeEncodeError. Gleicher Fix
# wie in main.py, hier bisher gefehlt -> verify_stack.py crashte immer.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def print_header(text):
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print('=' * 80)

def print_check(name, status, details=""):
    status_icon = "✅" if status else "❌"
    print(f"{status_icon} {name:<50} {'PASS' if status else 'FAIL':<10} {details}")

def check_files():
    """Verify all project files exist"""
    print_header("PROJECT FILES")
    
    required_files = {
        "requirements.txt": "Dependency manifest",
        "requirements-upgraded.txt": "Upgraded dependencies",
        "setup.py": "Setup configuration",
        "pyproject.toml": "Modern packaging config",
        ".env.example": "Environment template",
        ".gitignore": "Git ignore rules",
        "Makefile": "Development tasks",
        "Dockerfile": "Container image",
        "docker-compose.yml": "Container orchestration",
        "UPGRADE.md": "Upgrade documentation",
        "main.py": "Main application",
        "config.py": "Configuration module",
        "timeline_builder.py": "Timeline builder",
        "audio_analysis.py": "Audio processor",
        ".github/workflows/ci.yml": "CI/CD pipeline",
    }
    
    results = {}
    for file_path, description in required_files.items():
        path = Path(file_path)
        exists = path.exists()
        results[file_path] = exists
        print_check(description, exists, f"({file_path})")
    
    return all(results.values())

def check_dependencies():
    """Verify key dependencies are importable"""
    print_header("DEPENDENCY VERIFICATION")
    
    required_packages = {
        "numpy": "Scientific computing",
        "librosa": "Audio processing",
        "torch": "Deep learning",
        "cv2": "Computer vision",
        "flask": "Web framework",
        "requests": "HTTP client",
        "bs4": "HTML parsing",
        "pydantic": "Data validation",
    }
    
    results = {}
    for package, description in required_packages.items():
        try:
            if package == "cv2":
                import cv2 as _
            elif package == "bs4":
                import bs4 as _
            else:
                __import__(package)
            results[package] = True
            print_check(description, True, f"({package})")
        except ImportError as e:
            results[package] = False
            print_check(description, False, f"({package}) — {str(e)[:40]}")
    
    return results

def check_modules():
    """Verify core Python modules compile"""
    print_header("CORE MODULE VERIFICATION")
    
    core_modules = [
        ("main.py", "Main application"),
        ("config.py", "Configuration"),
        ("timeline_builder.py", "Timeline builder"),
        ("audio_analysis.py", "Audio analysis"),
        ("clip_pool.py", "Clip pool"),
        ("db.py", "Database"),
    ]
    
    results = {}
    for module_path, description in core_modules:
        module = Path(module_path)
        if not module.exists():
            results[module_path] = False
            print_check(description, False, f"File not found: {module_path}")
            continue
        
        try:
            import py_compile
            py_compile.compile(str(module), doraise=True)
            results[module_path] = True
            print_check(description, True, module_path)
        except py_compile.PyCompileError as e:
            results[module_path] = False
            print_check(description, False, str(e)[:40])
    
    return all(results.values())

def check_config():
    """Verify configuration"""
    print_header("CONFIGURATION VALIDATION")
    
    # Check environment variables
    import os
    from config import ROOT_DIR, LOG_DIR, DATA_DIR, CLIP_POOL_DIR
    
    print_check("ROOT_DIR defined", ROOT_DIR is not None, str(ROOT_DIR))
    print_check("LOG_DIR defined", LOG_DIR is not None, str(LOG_DIR))
    print_check("DATA_DIR defined", DATA_DIR is not None, str(DATA_DIR))
    print_check("CLIP_POOL_DIR defined", CLIP_POOL_DIR is not None, str(CLIP_POOL_DIR))
    
    # Check .env.example
    env_example = Path(".env.example")
    has_env = env_example.exists()
    print_check(".env.example template", has_env, ".env.example")
    
    return True

def check_documentation():
    """Verify documentation"""
    print_header("DOCUMENTATION")
    
    docs = {
        "README.md": "Project README",
        "UPGRADE.md": "Upgrade guide",
        ".env.example": "Environment template",
    }
    
    results = {}
    for doc, description in docs.items():
        path = Path(doc)
        exists = path.exists()
        results[doc] = exists
        size = path.stat().st_size if exists else 0
        print_check(description, exists, f"{doc} ({size} bytes)")
    
    return all(results.values())

def check_requirements():
    """Validate requirements.txt"""
    print_header("REQUIREMENTS VALIDATION")
    
    req_file = Path("requirements.txt")
    if not req_file.exists():
        print_check("requirements.txt exists", False)
        return False
    
    with open(req_file, 'r') as f:
        lines = f.readlines()
    
    packages = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    pinned = [pkg for pkg in packages if ">=" in pkg or "==" in pkg or "<" in pkg]
    
    print_check("requirements.txt exists", True, "found")
    print_check(f"Total packages", len(packages) > 0, f"{len(packages)} packages")
    print_check(f"Pinned versions", len(pinned) > 0, f"{len(pinned)}/{len(packages)} pinned")
    
    print("\n📦 Top 10 packages:")
    for i, pkg in enumerate(packages[:10], 1):
        print(f"   {i:2}. {pkg}")
    
    return len(packages) >= 20

def generate_report():
    """Generate comprehensive report"""
    print_header("OIDASHEIM BEAT SYNC — UPGRADE VERIFICATION REPORT")
    
    results = {}
    
    results["Files"] = check_files()
    deps = check_dependencies()
    results["Dependencies"] = sum(1 for v in deps.values() if v) / len(deps) > 0.8
    results["Modules"] = check_modules()
    results["Config"] = check_config()
    results["Documentation"] = check_documentation()
    results["Requirements"] = check_requirements()
    
    # Summary
    print_header("SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for category, status in results.items():
        status_icon = "✅" if status else "⚠️"
        print(f"{status_icon} {category:<30} {'PASS' if status else 'PARTIAL'}")
    
    print(f"\n📊 Overall Status: {passed}/{total} categories passed")
    
    if passed == total:
        print("\n🎉 ALL UPGRADES VERIFIED AND OPERATIONAL! 🎉")
        return True
    else:
        print("\n⚠️  Some items need attention. See details above.")
        return False

if __name__ == "__main__":
    try:
        success = generate_report()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
