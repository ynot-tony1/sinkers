#!/bin/bash

# =============================================================================
# Script Name: precise_sync_audio_video.sh
# Description: Adjusts audio in the video based on SyncNet-reported offset.
# Usage: ./precise_sync_audio_video.sh <input_video> <output_video> <offset_ms> <pad_end_sec>
# Example:
#   ./precise_sync_audio_video.sh data/work/pycrop/example/0003_original.avi data/work/pycrop/example/0003_synced_final.avi -50 0.016
# =============================================================================

# Exit on error and enable debug mode
set -e
# Uncomment the next line for debugging
# set -x

# Display usage
usage() {
    echo "Usage: $0 <input_video> <output_video> <offset_ms> <pad_end_sec>"
    echo "  <offset_ms>: Positive to delay audio, negative to advance audio (in milliseconds)"
    echo "  <pad_end_sec>: Seconds to pad at the end of audio to match video length"
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
echo "Temporary directory created at $TEMP_DIR"

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
    echo "Temporary files cleaned up."
}
trap cleanup EXIT

# Ensure 'bc' is installed
if ! command -v bc &> /dev/null
then
    echo "'bc' could not be found. Installing it now..."
    sudo apt-get update && sudo apt-get install -y bc
fi

# Calculate offset in seconds
OFFSET_SEC=$(printf "%.3f" "$(echo "$OFFSET_MS / 1000" | bc -l)")
echo "Offset: $OFFSET_MS ms ($OFFSET_SEC seconds)"

# Extract audio properties
AUDIO_INFO=$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate,channels -of default=noprint_wrappers=1:nokey=1 "$INPUT_VIDEO")
SAMPLE_RATE=$(echo "$AUDIO_INFO" | head -n1)
CHANNELS=$(echo "$AUDIO_INFO" | tail -n1)
echo "Original Audio Sample Rate: $SAMPLE_RATE Hz, Channels: $CHANNELS"

# Set target sample rate and channels for SyncNet
TARGET_SAMPLE_RATE=16000
TARGET_CHANNELS=1

# Extract original audio as WAV and resample to target properties
echo "Extracting and resampling original audio to $TARGET_SAMPLE_RATE Hz, $TARGET_CHANNELS channel(s)..."
ffmpeg -y -i "$INPUT_VIDEO" -vn -acodec pcm_s16le -ar "$TARGET_SAMPLE_RATE" -ac "$TARGET_CHANNELS" "$TEMP_DIR/original_audio.wav"

# Check if audio extraction succeeded
if [ ! -f "$TEMP_DIR/original_audio.wav" ]; then
    echo "Error: Failed to extract audio."
    exit 1
fi

# Adjust audio based on offset
if (( $(echo "$OFFSET_MS == 0" | bc -l) )); then
    echo "No offset adjustment needed."
    cp "$TEMP_DIR/original_audio.wav" "$TEMP_DIR/adjusted_audio.wav"

elif (( $(echo "$OFFSET_MS > 0" | bc -l) )); then
    echo "Positive offset detected: Delaying audio by $OFFSET_SEC seconds."

    # Create silence WAV
    echo "Generating $OFFSET_SEC seconds of silence..."
    ffmpeg -y -f lavfi -i anullsrc=channel_layout=mono:sample_rate="$TARGET_SAMPLE_RATE" -t "$OFFSET_SEC" "$TEMP_DIR/silence.wav"

    # Create concat list file
    echo "Creating concat list file..."
    echo "file '$TEMP_DIR/silence.wav'" > "$TEMP_DIR/concat_list.txt"
    echo "file '$TEMP_DIR/original_audio.wav'" >> "$TEMP_DIR/concat_list.txt"

    # Concatenate silence and original audio
    echo "Concatenating silence and original audio..."
    ffmpeg -y -f concat -safe 0 -i "$TEMP_DIR/concat_list.txt" -c copy "$TEMP_DIR/adjusted_audio.wav"

elif (( $(echo "$OFFSET_MS < 0" | bc -l) )); then
    echo "Negative offset detected: Advancing audio by $OFFSET_SEC seconds."

    # Trim audio from the beginning
    echo "Trimming $OFFSET_SEC seconds from the start of audio..."
    ffmpeg -y -i "$TEMP_DIR/original_audio.wav" -ss "$OFFSET_SEC" -c copy "$TEMP_DIR/trimmed_audio.wav"

    # Pad the end with silence to maintain duration
    echo "Padding audio at the end by $PAD_END_SEC seconds..."
    ffmpeg -y -i "$TEMP_DIR/trimmed_audio.wav" -af "apad=pad_dur=${PAD_END_SEC}" "$TEMP_DIR/adjusted_audio.wav"
fi

# Check if adjusted audio exists
if [ ! -f "$TEMP_DIR/adjusted_audio.wav" ]; then
    echo "Error: Adjusted audio not found."
    exit 1
fi

# Verify adjusted audio duration matches or exceeds video duration
VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT_VIDEO")
AUDIO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$TEMP_DIR/adjusted_audio.wav")

echo "Video Duration: $VIDEO_DURATION seconds"
echo "Adjusted Audio Duration: $AUDIO_DURATION seconds"

# Combine adjusted audio with original video
echo "Combining adjusted audio with video..."
# Re-encode video to ensure correct pixel format
ffmpeg -y -i "$INPUT_VIDEO" -i "$TEMP_DIR/adjusted_audio.wav" \
    -map 0:v -map 1:a \
    -c:v libx264 -pix_fmt yuv420p \
    -c:a aac -b:a 128k \
    -shortest "$OUTPUT_VIDEO"

echo "Synchronization complete. Output file: $OUTPUT_VIDEO"
exit 0

# Example command to run the script:
# ./precise_sync_audio_video.sh data/work/pycrop/example/0003_original.avi data/work/pycrop/example/0003_synced_final.avi -50 0.016




# Command to run the script:
# ./precise_sync_audio_video.sh data/work/pycrop/example/0001.avi data/work/pycrop/example/0001_synced_final.avi -3 0.016



# Command to send it forward  0.88 (880ms) without using this script
# ffmpeg -y -i data/work/pycrop/example/0002.avi -ss 0.88 -i data/work/pycrop/example/0002.avi -map 0:v -map 1:a -c:v copy -c:a aac -shortest data/work/pycrop/example/0002_synced_manual.avi



