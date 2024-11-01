#!/bin/bash

# ==================== CONFIGURATION ====================

# Check if exactly two arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 path/to/video_file offset_in_ms"
    echo "Example: $0 data/work/pycrop/example/0003_processed.avi -50"
    exit 1
fi

INPUT_VIDEO="$1"
AV_OFFSET_MS="$2"

# Ensure AV_OFFSET_MS is an integer
if ! [[ "$AV_OFFSET_MS" =~ ^-?[0-9]+$ ]]; then
    echo "Error: offset_in_ms must be an integer."
    exit 1
fi

# Extract directory and base name
DIR_NAME=$(dirname "$INPUT_VIDEO")
BASE_NAME=$(basename "$INPUT_VIDEO" .avi)

# Define output filenames
OUTPUT_VIDEO="${DIR_NAME}/${BASE_NAME}_synced.avi"
TEMP_AUDIO="${DIR_NAME}/${BASE_NAME}_temp_audio.wav"
SHIFTED_AUDIO="${DIR_NAME}/${BASE_NAME}_shifted_audio.wav"

# Initialize log file
LOG_FILE="sync_audio.log"
echo "$(date) - Starting synchronization for: $INPUT_VIDEO with AV offset: $AV_OFFSET_MS ms" > "$LOG_FILE"

# ==================== SYNCHRONIZATION PROCESS ====================

# Step 1: Extract audio with correct codec
echo "$(date) - Extracting audio from video." >> "$LOG_FILE"
ffmpeg -y -i "$INPUT_VIDEO" -vn -acodec pcm_s16le "$TEMP_AUDIO" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "$(date) - ERROR: Failed to extract audio." >> "$LOG_FILE"
    exit 1
fi

# Step 2: Adjust the audio timing
if [ "$AV_OFFSET_MS" -lt 0 ]; then
    # Negative offset: audio is ahead; delay audio
    OFFSET_MS_POSITIVE=$(( -AV_OFFSET_MS ))
    echo "$(date) - Delaying audio by $OFFSET_MS_POSITIVE ms" >> "$LOG_FILE"
    # Corrected: Single delay value for mono audio
    ffmpeg -y -i "$TEMP_AUDIO" -af "adelay=${OFFSET_MS_POSITIVE}" "$SHIFTED_AUDIO" >> "$LOG_FILE" 2>&1
elif [ "$AV_OFFSET_MS" -gt 0 ]; then
    # Positive offset: audio is behind; advance audio
    OFFSET_SECONDS=$(echo "scale=3; $AV_OFFSET_MS / 1000" | bc)
    echo "$(date) - Advancing audio by $OFFSET_SECONDS seconds" >> "$LOG_FILE"
    # Advance audio by trimming the start and padding the end
    ffmpeg -y -i "$TEMP_AUDIO" -af "atrim=start=${OFFSET_SECONDS}, apad=pad_dur=${OFFSET_SECONDS}" "$SHIFTED_AUDIO" >> "$LOG_FILE" 2>&1
else
    echo "$(date) - No synchronization needed. Copying original audio." >> "$LOG_FILE"
    cp "$TEMP_AUDIO" "$SHIFTED_AUDIO"
fi

if [ $? -ne 0 ]; then
    echo "$(date) - ERROR: Failed to adjust audio timing." >> "$LOG_FILE"
    exit 1
fi

# Step 3: Ensure audio and video durations match
AUDIO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$SHIFTED_AUDIO")
VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT_VIDEO")

# Use bc to compute duration difference
DURATION_DIFF=$(echo "$VIDEO_DURATION - $AUDIO_DURATION" | bc)
# Get absolute value
DURATION_DIFF=${DURATION_DIFF#-}

# Define epsilon for floating point comparison
EPSILON=0.01

if (( $(echo "$AUDIO_DURATION > $VIDEO_DURATION" | bc -l) )); then
    echo "$(date) - Trimming shifted audio to match video duration." >> "$LOG_FILE"
    ffmpeg -y -i "$SHIFTED_AUDIO" -t "$VIDEO_DURATION" "${SHIFTED_AUDIO}.tmp.wav" >> "$LOG_FILE" 2>&1
    if [ $? -ne 0 ]; then
        echo "$(date) - ERROR: Trimming audio failed." >> "$LOG_FILE"
        exit 1
    fi
    mv "${SHIFTED_AUDIO}.tmp.wav" "$SHIFTED_AUDIO"
elif (( $(echo "$AUDIO_DURATION < $VIDEO_DURATION" | bc -l) )); then
    echo "$(date) - Padding audio by $DURATION_DIFF seconds to match video duration." >> "$LOG_FILE"
    ffmpeg -y -i "$SHIFTED_AUDIO" -af "apad=pad_dur=${DURATION_DIFF}" "$SHIFTED_AUDIO.tmp.wav" >> "$LOG_FILE" 2>&1
    if [ $? -ne 0 ]; then
        echo "$(date) - ERROR: Padding audio failed." >> "$LOG_FILE"
        exit 1
    fi
    mv "$SHIFTED_AUDIO.tmp.wav" "$SHIFTED_AUDIO"
else
    echo "$(date) - Audio and video durations are equal. No adjustment needed." >> "$LOG_FILE"
fi

# Step 4: Combine adjusted audio with original video
echo "$(date) - Combining adjusted audio with video." >> "$LOG_FILE"
ffmpeg -y -i "$INPUT_VIDEO" -i "$SHIFTED_AUDIO" -c:v copy -c:a copy -map 0:v:0 -map 1:a:0 "$OUTPUT_VIDEO" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "$(date) - ERROR: Combining audio and video failed." >> "$LOG_FILE"
    exit 1
fi

# Clean up temporary files
rm "$TEMP_AUDIO" "$SHIFTED_AUDIO"

echo "$(date) - Synchronization completed successfully." >> "$LOG_FILE"
echo "$(date) - Synced video saved at: $OUTPUT_VIDEO" >> "$LOG_FILE"
echo "Synchronization complete. Output video: $OUTPUT_VIDEO"
