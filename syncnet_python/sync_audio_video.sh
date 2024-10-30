#!/bin/bash

# =============================================================================
# Script Name: precise_sync_audio_video.sh
# Description: Adjusts audio in the video based on SyncNet-reported offset.
# Usage: ./precise_sync_audio_video.sh <input_video> <output_video> <offset_ms> <pad_end_sec>
# Example:
#   ./precise_sync_audio_video.sh data/work/pycrop/example/0001.avi data/work/pycrop/example/0001_synced_final.avi 22 0.016
# =============================================================================

# Exit on error
set -e

# Display usage
usage() {
    echo "Usage: $0 <input_video> <output_video> <offset_ms> <pad_end_sec>"
    exit 1
}

# Check argument count
if [ "$#" -ne 4 ]; then
    usage
fi

# Variables
INPUT_VIDEO="$1"
OUTPUT_VIDEO="$2"
OFFSET_MS="$3"
PAD_END_SEC="$4"
TEMP_DIR=$(mktemp -d)

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Apply positive or negative offset
if [ "$OFFSET_MS" -ge 0 ]; then
    echo "Adding $OFFSET_MS ms silence to the start for positive offset."
    # Convert milliseconds to seconds with three decimal places for FFmpeg compatibility
    ABS_DELAY_SEC=$(printf "%.3f" "$(echo "$OFFSET_MS / 1000" | bc -l)")

    # Add silence at the beginning
    ffmpeg -y -f lavfi -i anullsrc=r=16000:cl=mono -t "$ABS_DELAY_SEC" "$TEMP_DIR/silence.aac"
    ffmpeg -y -i "$INPUT_VIDEO" -vn -acodec aac "$TEMP_DIR/original_audio.aac"
    ffmpeg -y -i "concat:$TEMP_DIR/silence.aac|$TEMP_DIR/original_audio.aac" -c copy "$TEMP_DIR/audio_with_silence.aac"


else
    # Adjust for negative offset by adding silence and trimming start
ABS_OFFSET_MS=$(echo "$OFFSET_MS" | sed 's/-//')
ABS_OFFSET_SEC=$(printf "%.3f" "$(echo "$ABS_OFFSET_MS/1000" | bc -l)")

# Step 1: Add silence at the beginning
ffmpeg -y -f lavfi -i anullsrc=r=16000:cl=mono -t "$ABS_OFFSET_SEC" "$TEMP_DIR/silence.aac"
ffmpeg -y -i "$INPUT_VIDEO" -vn -acodec aac "$TEMP_DIR/original_audio.aac"
ffmpeg -y -i "concat:$TEMP_DIR/silence.aac|$TEMP_DIR/original_audio.aac" -c copy "$TEMP_DIR/audio_with_silence.aac"

# Step 2: Trim the start to align audio backward by the specified delay
ffmpeg -y -i "$TEMP_DIR/audio_with_silence.aac" -ss "$ABS_OFFSET_SEC" -c copy "$TEMP_DIR/audio_trimmed.aac"

fi

# Combine adjusted audio with video
ffmpeg -y -i "$INPUT_VIDEO" -i "$TEMP_DIR/audio_with_silence.aac" \
       -map 0:v -map 1:a -c:v copy -c:a aac -shortest "$TEMP_DIR/temp_aligned.avi"

# Pad audio with silence at the end
ffmpeg -y -i "$TEMP_DIR/temp_aligned.avi" \
       -af "apad=pad_dur=${PAD_END_SEC}" \
       -c:v copy -c:a aac -shortest "$OUTPUT_VIDEO"

echo "Synchronization complete. Output file: $OUTPUT_VIDEO"
exit 0

# Command to send it forward without using this script
# ffmpeg -y -i data/work/pycrop/example/0002.avi -ss 0.88 -i data/work/pycrop/example/0002.avi -map 0:v -map 1:a -c:v copy -c:a aac -shortest data/work/pycrop/example/0002_synced_manual.avi

