#!/usr/bin/env bash
#
# Cross-platform PlantUML diagram generation script for POSIX shells.
# Mirrors the behaviour of generate_diagrams.bat for use inside WSL/Linux.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PLANTUML_VERSION="1.2023.13"
DIAGRAMS_SOURCE="docs/diagrams"
DIAGRAMS_OUTPUT="$DIAGRAMS_SOURCE/generated"
PLANTUML_JAR="plantuml.jar"
VALIDATE=false

if [[ -n "${PLANTUML_JAVA_OPTS:-}" ]]; then
    # shellcheck disable=SC2206
    JAVA_OPTS=( ${PLANTUML_JAVA_OPTS} )
else
    JAVA_OPTS=(-Djava.awt.headless=true)
fi

PLANTUML_CONFIG="$DIAGRAMS_SOURCE/plantuml.config"
CONFIG_ARGS=()
if [[ -f "$PLANTUML_CONFIG" ]]; then
    CONFIG_ARGS=(-config "$ROOT_DIR/$PLANTUML_CONFIG")
fi

usage() {
    echo "Usage: $0 [--validate|-v]"
}

while (($#)); do
    case "$1" in
        --validate|-v)
            VALIDATE=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
    shift
done

echo
echo "ModBusX PlantUML Diagram Generator (POSIX)"
echo "=========================================="

if ! command -v java >/dev/null 2>&1; then
    echo "ERROR: Java is not installed or not in PATH." >&2
    echo "Please install Java 11 or later to run PlantUML." >&2
    exit 1
fi

echo "Checking Java version..."
java -version 2>&1 | head -n 1

if [[ ! -f "$PLANTUML_JAR" ]]; then
    url="https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar"
    echo "PlantUML JAR not found. Downloading v${PLANTUML_VERSION}..."

    if command -v curl >/dev/null 2>&1; then
        curl -L "$url" -o "$PLANTUML_JAR"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$PLANTUML_JAR" "$url"
    else
        echo "ERROR: Neither curl nor wget is available to download PlantUML." >&2
        exit 1
    fi
fi

echo "Verifying PlantUML..."
if ! java "${JAVA_OPTS[@]}" -jar "$PLANTUML_JAR" -version >/dev/null 2>&1; then
    echo "ERROR: PlantUML verification failed." >&2
    exit 1
fi

mkdir -p "$DIAGRAMS_OUTPUT"

if [[ ! -d "$DIAGRAMS_SOURCE" ]]; then
    echo "ERROR: Source directory not found: $DIAGRAMS_SOURCE" >&2
    exit 1
fi

mapfile -t PUML_FILES < <(find "$DIAGRAMS_SOURCE" -maxdepth 1 -type f -name '*.puml' | sort)
if [[ ${#PUML_FILES[@]} -eq 0 ]]; then
    echo "ERROR: No .puml files found in $DIAGRAMS_SOURCE" >&2
    exit 1
fi

echo "Found ${#PUML_FILES[@]} PlantUML files."

pushd "$DIAGRAMS_SOURCE" >/dev/null

echo "Generating SVG diagrams..."
java "${JAVA_OPTS[@]}" -jar "$ROOT_DIR/$PLANTUML_JAR" -tsvg -o "generated" "${CONFIG_ARGS[@]}" *.puml

popd >/dev/null

SVG_COUNT=$(find "$DIAGRAMS_OUTPUT" -maxdepth 1 -type f -name '*.svg' | wc -l | tr -d ' ')

echo
echo "Generated files:"
printf "  SVG: %s\n" "$SVG_COUNT"

if $VALIDATE; then
    echo
    echo "Validating PlantUML syntax..."
    VALIDATION_FAILED=false
    for file in "${PUML_FILES[@]}"; do
        rel_file="${file#$ROOT_DIR/}"
        printf "  Checking %s... " "$rel_file"
        if java "${JAVA_OPTS[@]}" -jar "$PLANTUML_JAR" "${CONFIG_ARGS[@]}" -checkonly "$file" >/dev/null 2>&1; then
            echo "OK"
        else
            echo "ERROR"
            VALIDATION_FAILED=true
        fi
    done

    if $VALIDATION_FAILED; then
        echo "ERROR: Some files have syntax errors." >&2
        exit 1
    fi
fi

echo
echo "Diagram generation complete."
echo "Output directory: $DIAGRAMS_OUTPUT"
echo "Helpful commands:"
echo "  View diagrams:    xdg-open \"$DIAGRAMS_OUTPUT\""
echo "  Validate syntax:  $0 --validate"
