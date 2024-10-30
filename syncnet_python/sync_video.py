#!/usr/bin/env python3

import subprocess
import argparse

def sync_audio(video_file, offset_ms, output_file):
    # Build the ffmpeg command to delay the audio
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-i', video_file,
        '-filter_complex', f'[0:a]adelay={offset_ms}|{offset_ms}[aud]',
        '-map', '0:v', '-map', '[aud]',
        '-c:v', 'copy', '-c:a', 'aac',
        output_file
    ]

    # Execute the ffmpeg command and capture output
    print("Running FFmpeg command...")
    process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

    # Print FFmpeg output and errors for troubleshooting
    print("FFmpeg Output:")
    print(process.stdout)
    print("FFmpeg Errors:")
    print(process.stderr)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Synchronize audio with video")
    parser.add_argument('--videofile', type=str, required=True, help='Path to the input video file')
    parser.add_argument('--offset', type=int, required=True, help='Audio offset in milliseconds (positive to delay audio)')
    parser.add_argument('--outputfile', type=str, required=True, help='Path to the output synchronized video file')
    args = parser.parse_args()

    # Call the sync function
    sync_audio(args.videofile, args.offset, args.outputfile)
