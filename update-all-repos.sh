#!/bin/bash

################################################################################
# Multi-Repository Update Script
# Updates all local repositories with latest changes from remote
# Usage: ./update-all-repos.sh [--repos-dir /path/to/repos] [--verbose] [--dry-run]
################################################################################

set -euo pipefail

# Configuration
REPOS_DIR="${1:-.}"
VERBOSE=false
DRY_RUN=false
LOG_FILE="update-repos-$(date +%Y%m%d-%H%M%S).log"
FAILED_REPOS=()
UPDATED_REPOS=()
SKIPPED_REPOS=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# Functions
################################################################################

log() {
    local level="$1"
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $@" | tee -a "${LOG_FILE}"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $@" | tee -a "${LOG_FILE}"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $@" | tee -a "${LOG_FILE}"
}

log_error() {
    echo -e "${RED}[✗]${NC} $@" | tee -a "${LOG_FILE}"
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    -d, --repos-dir DIR     Base directory containing all repositories (default: current directory)
    -v, --verbose          Enable verbose output
    -n, --dry-run          Simulate updates without making changes
    -h, --help             Show this help message

Examples:
    $0 --repos-dir ~/projects --verbose
    $0 --dry-run
    $0
EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--repos-dir)
                REPOS_DIR="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

is_git_repo() {
    local dir="$1"
    [[ -d "$dir/.git" ]]
}

update_repo() {
    local repo_path="$1"
    local repo_name=$(basename "$repo_path")
    
    if ! is_git_repo "$repo_path"; then
        SKIPPED_REPOS+=("$repo_name")
        log_warning "Skipping $repo_name (not a git repository)"
        return 0
    fi
    
    log_info "Updating repository: $repo_name"
    
    cd "$repo_path" || return 1
    
    # Check if there are uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        log_warning "Repository $repo_name has uncommitted changes - skipping"
        SKIPPED_REPOS+=("$repo_name")
        cd - > /dev/null || return 1
        return 0
    fi
    
    # Get current branch
    local current_branch=$(git rev-parse --abbrev-ref HEAD)
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would update $repo_name on branch $current_branch"
    else
        # Fetch from remote
        if git fetch origin &>/dev/null; then
            # Check if branch has tracking branch
            if git rev-parse --abbrev-ref "${current_branch}@{u}" &>/dev/null; then
                # Pull with rebase to avoid merge commits
                if git pull --rebase origin "$current_branch" &>/dev/null; then
                    log_success "Updated $repo_name on branch $current_branch"
                    UPDATED_REPOS+=("$repo_name")
                else
                    log_error "Failed to pull updates for $repo_name"
                    FAILED_REPOS+=("$repo_name")
                fi
            else
                log_warning "Branch $current_branch has no tracking branch in $repo_name"
                SKIPPED_REPOS+=("$repo_name")
            fi
        else
            log_error "Failed to fetch from remote for $repo_name"
            FAILED_REPOS+=("$repo_name")
        fi
    fi
    
    cd - > /dev/null || return 1
}

find_and_update_repos() {
    if [[ ! -d "$REPOS_DIR" ]]; then
        log_error "Directory does not exist: $REPOS_DIR"
        exit 1
    fi
    
    log_info "Starting repository update process"
    log_info "Looking for repositories in: $REPOS_DIR"
    
    # Find all directories containing .git
    local repo_count=0
    while IFS= read -r repo_path; do
        update_repo "$repo_path"
        ((repo_count++))
    done < <(find "$REPOS_DIR" -maxdepth 2 -type d -name ".git" -exec dirname {} \; 2>/dev/null | sort)
    
    if [[ $repo_count -eq 0 ]]; then
        log_warning "No git repositories found in $REPOS_DIR"
    fi
}

print_summary() {
    echo ""
    log_info "==============================================="
    log_info "Update Summary"
    log_info "==============================================="
    
    log_success "Successfully updated: ${#UPDATED_REPOS[@]} repositories"
    if [[ ${#UPDATED_REPOS[@]} -gt 0 ]]; then
        for repo in "${UPDATED_REPOS[@]}"; do
            echo "  ✓ $repo"
        done
    fi
    
    echo ""
    log_warning "Skipped: ${#SKIPPED_REPOS[@]} repositories"
    if [[ ${#SKIPPED_REPOS[@]} -gt 0 ]]; then
        for repo in "${SKIPPED_REPOS[@]}"; do
            echo "  ⊘ $repo"
        done
    fi
    
    echo ""
    if [[ ${#FAILED_REPOS[@]} -gt 0 ]]; then
        log_error "Failed: ${#FAILED_REPOS[@]} repositories"
        for repo in "${FAILED_REPOS[@]}"; do
            echo "  ✗ $repo"
        done
    fi
    
    echo ""
    log_info "Log file: $LOG_FILE"
    log_info "==============================================="
}

################################################################################
# Main
################################################################################

main() {
    parse_arguments "$@"
    
    log_info "Repository Update Script Started"
    log_info "DRY RUN: $DRY_RUN"
    log_info "VERBOSE: $VERBOSE"
    
    find_and_update_repos
    print_summary
    
    # Exit with error if any repos failed
    if [[ ${#FAILED_REPOS[@]} -gt 0 ]]; then
        exit 1
    fi
}

main "$@"
