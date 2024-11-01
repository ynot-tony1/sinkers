#!/bin/bash

# ==================== CONFIGURATION ====================

# Desired video and audio specifications
DESIRED_FRAME_RATE=25
DESIRED_RESOLUTION="224x224"        # Desired resolution
DESIRED_VIDEO_CODEC="mpeg4"         # Enforce mpeg4 codec
DESIRED_AUDIO_CODEC="pcm_s16le"     # Raw audio codec for 16 kHz, mono
DESIRED_AUDIO_SAMPLE_RATE=16000     # Sample rate in Hz
DESIRED_AUDIO_CHANNELS=1            # Mono audio
OUTPUT_SUFFIX="_processed.avi"

# Logging file
LOG_FILE="preprocess_syncnet.log"

# ==================== FUNCTIONS ====================

# Function to display usage instructions
usage() {
    echo "Usage: $0 path/to/video_file"
    echo "Example: $0 data/work/pycrop/example/0003.avi"
    exit 1
}

# Function to log messages with timestamp
log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" | tee -a "$LOG_FILE"
}

# Function to preprocess the video
preprocess_video() {
    INPUT_VIDEO="$1"

    # Check if the input file exists
    if [ ! -f "$INPUT_VIDEO" ]; then
        log "ERROR: File '$INPUT_VIDEO' does not exist."
        exit 1
    fi

    # Extract directory and filename
    DIR_NAME=$(dirname "$INPUT_VIDEO")
    BASE_NAME=$(basename "$INPUT_VIDEO" .avi)

    # Define output filenames
    OUTPUT_VIDEO="${DIR_NAME}/${BASE_NAME}${OUTPUT_SUFFIX}"
    TEMP_AUDIO="${DIR_NAME}/${BASE_NAME}_temp_audio.wav"
    PROCESSED_AUDIO="${DIR_NAME}/${BASE_NAME}_processed_audio.wav"

    # Check if output file already exists
    if [ -f "$OUTPUT_VIDEO" ]; then
        log "WARNING: Output file '$OUTPUT_VIDEO' already exists. It will be overwritten."
    fi

    log "Preprocessing video: $INPUT_VIDEO"
    log "Saving processed video as: $OUTPUT_VIDEO"

    # Step 1: Preprocess the video with ffmpeg, ensuring desired specs, strip audio
    ffmpeg -y -i "$INPUT_VIDEO" \
        -vf "scale=${DESIRED_RESOLUTION},fps=${DESIRED_FRAME_RATE}" \
        -c:v "${DESIRED_VIDEO_CODEC}" \
        -an \
        "$OUTPUT_VIDEO" \
        >> "$LOG_FILE" 2>&1

    if [ $? -ne 0 ]; then
        log "ERROR: Video preprocessing failed."
        exit 1
    fi

    # Step 2: Extract audio from the original video
    ffmpeg -y -i "$INPUT_VIDEO" -c:a copy "$TEMP_AUDIO" >> "$LOG_FILE" 2>&1

    if [ $? -ne 0 ]; then
        log "WARNING: Failed to extract audio. Will generate silence."
        rm -f "$TEMP_AUDIO"
    fi

    # Step 3: Check if TEMP_AUDIO exists and is valid
    if [ -f "$TEMP_AUDIO" ]; then
        PROC_AUDIO_DURATION=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration \
                              -of default=noprint_wrappers=1:nokey=1 "$TEMP_AUDIO")
        if [[ -z "$PROC_AUDIO_DURATION" || "$PROC_AUDIO_DURATION" == "N/A" ]]; then
            log "WARNING: Extracted audio duration invalid. Will generate silence."
            rm -f "$TEMP_AUDIO"
        fi
    fi

    # If audio extraction failed or audio invalid, create silence
    if [ ! -f "$TEMP_AUDIO" ]; then
        log "Creating silence audio to match video duration."
        # Get video duration
        PROC_VIDEO_DURATION=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration \
                              -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_VIDEO")
        # Create silence audio
        ffmpeg -y -f lavfi -i anullsrc=channel_layout=mono:sample_rate="$DESIRED_AUDIO_SAMPLE_RATE" \
            -t "$PROC_VIDEO_DURATION" -c:a "${DESIRED_AUDIO_CODEC}" "$PROCESSED_AUDIO" \
            >> "$LOG_FILE" 2>&1

        if [ $? -ne 0 ]; then
            log "ERROR: Generating silence audio failed."
            exit 1
        fi

        PROC_AUDIO_DURATION="$PROC_VIDEO_DURATION"
    else
        # Audio was extracted, now need to process it
        # Resample and set to desired codec and channels
        ffmpeg -y -i "$TEMP_AUDIO" \
            -c:a "${DESIRED_AUDIO_CODEC}" -ar "${DESIRED_AUDIO_SAMPLE_RATE}" -ac "${DESIRED_AUDIO_CHANNELS}" \
            "$PROCESSED_AUDIO" \
            >> "$LOG_FILE" 2>&1

        if [ $? -ne 0 ]; then
            log "ERROR: Processing extracted audio failed."
            exit 1
        fi

        # Get processed audio duration
        PROC_AUDIO_DURATION=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration \
                              -of default=noprint_wrappers=1:nokey=1 "$PROCESSED_AUDIO")
    fi

    # Get video duration
    PROC_VIDEO_DURATION=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration \
                          -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_VIDEO")

    log "Processed Video Duration: $PROC_VIDEO_DURATION seconds"
    log "Processed Audio Duration: $PROC_AUDIO_DURATION seconds"

    # Calculate duration difference
    DURATION_DIFF=$(echo "$PROC_VIDEO_DURATION - $PROC_AUDIO_DURATION" | bc)
    # Absolute value
    ABS_DURATION_DIFF=$(echo "$DURATION_DIFF" | awk '{print ($1 < 0) ? -$1 : $1}')

    # Set epsilon
    EPSILON=0.01

    # If audio is longer, trim
    if (( $(echo "$DURATION_DIFF < -$EPSILON" | bc -l) )); then
        log "Trimming audio to match video duration."
        ffmpeg -y -i "$PROCESSED_AUDIO" \
            -c:a copy \
            -t "$PROC_VIDEO_DURATION" \
            "$PROCESSED_AUDIO.tmp.wav" \
            >> "$LOG_FILE" 2>&1

        if [ $? -ne 0 ]; then
            log "ERROR: Trimming audio failed."
            exit 1
        fi

        mv "$PROCESSED_AUDIO.tmp.wav" "$PROCESSED_AUDIO"
        PROC_AUDIO_DURATION="$PROC_VIDEO_DURATION"
    fi

    # If audio is shorter, pad with silence
    if (( $(echo "$DURATION_DIFF > $EPSILON" | bc -l) )); then
        PAD_DURATION=$(printf "%.6f" "$DURATION_DIFF")
        log "Padding audio with $PAD_DURATION seconds of silence to match video duration."
        # Create silence pad
        ffmpeg -y -f lavfi -i anullsrc=channel_layout=mono:sample_rate="$DESIRED_AUDIO_SAMPLE_RATE" \
            -t "$PAD_DURATION" -c:a "${DESIRED_AUDIO_CODEC}" "$DIR_NAME/silence_pad.wav" \
            >> "$LOG_FILE" 2>&1

        if [ $? -ne 0 ]; then
            log "ERROR: Generating silence pad failed."
            exit 1
        fi

        # Concatenate the existing audio with silence_pad.wav
        # Create a concat list
        echo "file '$(realpath "$PROCESSED_AUDIO")'" > "$DIR_NAME/concat_list.txt"
        echo "file '$(realpath "$DIR_NAME/silence_pad.wav")'" >> "$DIR_NAME/concat_list.txt"

        # Concatenate
        ffmpeg -y -f concat -safe 0 -i "$DIR_NAME/concat_list.txt" \
            -c:a "${DESIRED_AUDIO_CODEC}" -ar "${DESIRED_AUDIO_SAMPLE_RATE}" -ac "${DESIRED_AUDIO_CHANNELS}" \
            "$PROCESSED_AUDIO.tmp.wav" \
            >> "$LOG_FILE" 2>&1

        if [ $? -ne 0 ]; then
            log "ERROR: Concatenating audio with silence pad failed."
            exit 1
        fi

        mv "$PROCESSED_AUDIO.tmp.wav" "$PROCESSED_AUDIO"

        # Remove temporary files
        rm "$DIR_NAME/silence_pad.wav" "$DIR_NAME/concat_list.txt"

        PROC_AUDIO_DURATION="$PROC_VIDEO_DURATION"
    fi

    log "Audio and video durations are now synchronized."

    # Remux video and audio
    log "Remuxing video and audio into final output."
    ffmpeg -y -i "$OUTPUT_VIDEO" -i "$PROCESSED_AUDIO" \
        -c:v copy \
        -c:a copy \
        -shortest \
        "${OUTPUT_VIDEO}.final.avi" \
        >> "$LOG_FILE" 2>&1

    if [ $? -ne 0 ]; then
        log "ERROR: Remuxing video and audio failed."
        exit 1
    fi

    mv "${OUTPUT_VIDEO}.final.avi" "$OUTPUT_VIDEO"

    # Remove temporary audio files
    rm -f "$TEMP_AUDIO" "$PROCESSED_AUDIO"

    log "Preprocessing completed successfully."
    log "Processed video saved at: $OUTPUT_VIDEO"
}

# ==================== MAIN SCRIPT ====================

# Check if exactly one argument is provided
if [ "$#" -ne 1 ]; then
    usage
fi

INPUT_VIDEO="$1"

# Start preprocessing
log "==================== Preprocessing Pipeline Started ===================="
log "Input Video: $INPUT_VIDEO"

preprocess_video "$INPUT_VIDEO"

log "==================== Preprocessing Pipeline Completed ===================="
exit 0



#  ./preprocess_syncnet.sh data/work/pycrop/example/0003.avi