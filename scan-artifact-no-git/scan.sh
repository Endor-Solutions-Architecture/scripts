#!/bin/bash
set -euo pipefail

##############################################################################
# scan.sh — Scan a model artifact (tar.gz or folder) using Endor Labs
#
# Designed for environments like Databricks where artifacts are not in a git
# repo. Creates a synthetic git repo around the artifact so endorctl can scan
# it for dependency vulnerabilities via the requirements.txt manifest.
#
# Prerequisites are installed automatically if missing: endorctl, git.
##############################################################################

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME <artifact-path> [options]

  <artifact-path>   Path to a .tar.gz file or a folder containing the model artifact.

Options:
  --namespace      Endor Labs namespace       (default: \$ENDOR_NAMESPACE)
  --api-key        Endor Labs API key         (default: \$ENDOR_API_KEY)
  --api-secret     Endor Labs API secret      (default: \$ENDOR_API_SECRET)
  --project-name   Project name for Endor portal (default: derived from artifact filename)
  --github-org     GitHub org for synthetic remote (default: \$ENDOR_GITHUB_ORG or "example-org")
  -h, --help       Show this help message

Environment variables:
  ENDOR_NAMESPACE    Endor Labs namespace
  ENDOR_API_KEY      Endor Labs API key (client ID)
  ENDOR_API_SECRET   Endor Labs API secret (client secret)
  ENDOR_GITHUB_ORG   GitHub org used in the synthetic remote origin

Examples:
  # Using environment variables
  export ENDOR_NAMESPACE=my-namespace
  export ENDOR_API_KEY=my-key
  export ENDOR_API_SECRET=my-secret
  ./scan.sh /path/to/model.tar.gz

  # Using CLI arguments
  ./scan.sh /path/to/model.tar.gz --namespace my-namespace --api-key my-key --api-secret my-secret

  # Scanning a folder directly
  ./scan.sh /path/to/model-folder --namespace my-namespace --api-key my-key --api-secret my-secret
EOF
  exit 0
}

log() { echo "[scan] $*"; }
err() { echo "[scan] ERROR: $*" >&2; }
die() { err "$@"; exit 1; }

##############################################################################
# Parse arguments
##############################################################################

ARTIFACT_PATH=""
NAMESPACE="${ENDOR_NAMESPACE:-}"
API_KEY="${ENDOR_API_KEY:-}"
API_SECRET="${ENDOR_API_SECRET:-}"
PROJECT_NAME=""
GITHUB_ORG="${ENDOR_GITHUB_ORG:-example-org}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)      usage ;;
    --namespace)    NAMESPACE="$2"; shift 2 ;;
    --api-key)      API_KEY="$2"; shift 2 ;;
    --api-secret)   API_SECRET="$2"; shift 2 ;;
    --project-name) PROJECT_NAME="$2"; shift 2 ;;
    --github-org)   GITHUB_ORG="$2"; shift 2 ;;
    -*)             die "Unknown option: $1" ;;
    *)
      if [[ -z "$ARTIFACT_PATH" ]]; then
        ARTIFACT_PATH="$1"; shift
      else
        die "Unexpected argument: $1"
      fi
      ;;
  esac
done

[[ -n "$ARTIFACT_PATH" ]] || die "Missing required argument: <artifact-path>. Run with --help for usage."
[[ -n "$NAMESPACE" ]]     || die "Namespace is required. Set ENDOR_NAMESPACE or pass --namespace."
[[ -n "$API_KEY" ]]       || die "API key is required. Set ENDOR_API_KEY or pass --api-key."
[[ -n "$API_SECRET" ]]    || die "API secret is required. Set ENDOR_API_SECRET or pass --api-secret."

##############################################################################
# Step 1: Ensure git is available
##############################################################################

ensure_git() {
  if command -v git &>/dev/null; then
    log "git found: $(git --version)"
    return
  fi

  log "git not found, installing..."

  if [[ "$(uname -s)" == "Linux" ]]; then
    if command -v apt-get &>/dev/null; then
      sudo apt-get update -qq && sudo apt-get install -y -qq git
    elif command -v yum &>/dev/null; then
      sudo yum install -y git
    elif command -v apk &>/dev/null; then
      apk add --no-cache git
    else
      die "Cannot install git: no supported package manager found (apt-get, yum, apk)."
    fi
  elif [[ "$(uname -s)" == "Darwin" ]]; then
    if command -v brew &>/dev/null; then
      brew install git
    else
      die "Cannot install git: Homebrew not found. Install git manually."
    fi
  else
    die "Cannot install git: unsupported OS $(uname -s)."
  fi

  command -v git &>/dev/null || die "git installation failed."
  log "git installed: $(git --version)"
}

##############################################################################
# Step 2: Ensure endorctl is available
##############################################################################

ensure_endorctl() {
  if command -v endorctl &>/dev/null; then
    log "endorctl found: $(endorctl --version 2>/dev/null || echo 'version unknown')"
    return
  fi

  log "endorctl not found, installing..."

  local os arch binary_name download_url
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"

  case "$arch" in
    x86_64)  arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) die "Unsupported architecture: $arch" ;;
  esac

  # Map OS names
  case "$os" in
    linux)  ;;
    darwin) ;;
    *) die "Unsupported OS: $os" ;;
  esac

  binary_name="endorctl_${os}_${arch}"
  download_url="https://api.endorlabs.com/download/latest/${binary_name}"

  log "Downloading endorctl from $download_url"
  curl -sSL "$download_url" -o /tmp/endorctl
  chmod +x /tmp/endorctl

  # Make it available on PATH
  if [[ -d /usr/local/bin ]] && [[ -w /usr/local/bin ]]; then
    mv /tmp/endorctl /usr/local/bin/endorctl
  else
    export PATH="/tmp:$PATH"
  fi

  command -v endorctl &>/dev/null || die "endorctl installation failed."
  log "endorctl installed: $(endorctl --version 2>/dev/null || echo 'version unknown')"
}

##############################################################################
# Step 3: Prepare the artifact in a working directory
##############################################################################

WORK_DIR=""
CLEANUP_WORK_DIR=false

prepare_artifact() {
  local artifact_path="$1"

  # Resolve to absolute path
  artifact_path="$(cd "$(dirname "$artifact_path")" && pwd)/$(basename "$artifact_path")"

  if [[ -f "$artifact_path" ]]; then
    # It's a file — check if it's a tar.gz
    case "$artifact_path" in
      *.tar.gz|*.tgz)
        log "Extracting $artifact_path ..."
        WORK_DIR="$(mktemp -d)"
        CLEANUP_WORK_DIR=true
        tar -xzf "$artifact_path" -C "$WORK_DIR"

        # Navigate into the extracted top-level directory if there is one
        local dirs
        dirs=( "$WORK_DIR"/*/ )
        if [[ ${#dirs[@]} -eq 1 && -d "${dirs[0]}" ]]; then
          WORK_DIR="${dirs[0]%/}"
        fi

        log "Extracted to $WORK_DIR"
        ;;
      *)
        die "Unsupported file type: $artifact_path (expected .tar.gz or .tgz)"
        ;;
    esac
  elif [[ -d "$artifact_path" ]]; then
    # It's a directory — copy to temp dir so we don't modify the original
    log "Copying folder $artifact_path to temp directory..."
    WORK_DIR="$(mktemp -d)"
    CLEANUP_WORK_DIR=true
    cp -r "$artifact_path"/. "$WORK_DIR"/
    log "Working directory: $WORK_DIR"
  else
    die "Artifact not found: $artifact_path"
  fi

  # Verify requirements.txt exists
  if [[ ! -f "$WORK_DIR/requirements.txt" ]]; then
    log "WARNING: requirements.txt not found in $WORK_DIR"
    log "Contents of working directory:"
    ls -la "$WORK_DIR"
  fi
}

##############################################################################
# Step 4: Derive the project name
##############################################################################

derive_project_name() {
  if [[ -n "$PROJECT_NAME" ]]; then
    return
  fi

  local basename_artifact
  basename_artifact="$(basename "$ARTIFACT_PATH")"

  # Strip extensions
  basename_artifact="${basename_artifact%.tar.gz}"
  basename_artifact="${basename_artifact%.tgz}"

  PROJECT_NAME="$basename_artifact"
  log "Derived project name: $PROJECT_NAME"
}

##############################################################################
# Step 5: Set up synthetic git repo and scan
##############################################################################

run_scan() {
  cd "$WORK_DIR"

  # Remove any existing .git directory (artifacts may contain one)
  if [[ -d .git ]]; then
    log "Removing existing .git directory from artifact"
    rm -rf .git
  fi

  log "Initializing synthetic git repository..."
  git init -q
  git config user.email "scan@endorlabs.com"
  git config user.name "Endor Labs Scan"
  git add .
  git commit -q -m "model artifact scan"

  local remote_url="https://github.com/${GITHUB_ORG}/${PROJECT_NAME}.git"
  git remote add origin "$remote_url"
  log "Set remote origin to $remote_url"
  log "This determines the project name in the Endor Labs portal."

  log "Running endorctl scan..."
  local scan_exit_code=0
  endorctl scan \
    --namespace "$NAMESPACE" \
    --api-key "$API_KEY" \
    --api-secret "$API_SECRET" || scan_exit_code=$? \
    --log-level "debug"

  return "$scan_exit_code"
}

##############################################################################
# Step 6: Cleanup
##############################################################################

cleanup() {
  if [[ "$CLEANUP_WORK_DIR" == true && -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
    log "Cleaning up $WORK_DIR"
    rm -rf "$WORK_DIR"
  fi
}

trap cleanup EXIT

##############################################################################
# Main
##############################################################################

main() {
  # Enable Python requirements.txt scanning in endorctl
  export ENDOR_SCAN_ENABLE_PYTHON_REQUIREMENTS_AUTO_DETECT=true

  log "Starting artifact scan..."

  ensure_git
  ensure_endorctl
  prepare_artifact "$ARTIFACT_PATH"
  derive_project_name

  local scan_exit_code=0
  run_scan || scan_exit_code=$?

  if [[ "$scan_exit_code" -eq 0 ]]; then
    log "Scan passed — no policy violations found."
  else
    log "Scan finished with exit code $scan_exit_code — review findings in the Endor Labs portal."
  fi

  exit "$scan_exit_code"
}

main
