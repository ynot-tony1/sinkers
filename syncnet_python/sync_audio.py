#!/usr/bin/env python3

import numpy as np
import subprocess
import argparse
import pickle
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_video_fps(video_file):
    logging.debug(f"Getting FPS for video: {video_file}")
    cmd = [
        'ffprobe', '-v', '0', '-of', 'csv=p=0',
        '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
        video_file
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fps_info = result.stdout.decode('utf-8').strip()
    num, denom = map(float, fps_info.split('/'))
    fps = num / denom
    logging.debug(f"FPS for {video_file}: {fps}")
    return fps

def sync_video(video_file, offset, output_file):
    logging.debug(f"Syncing video: {video_file} with offset: {offset} to {output_file}")
    fps = get_video_fps(video_file)
    time_shift = offset / fps  # Time shift in seconds

    # Construct FFmpeg command based on the offset
    if offset > 0:
        # If offset is positive, delay the audio
        delay_ms = offset  # Use offset in milliseconds
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', video_file,
            '-filter_complex', f'[0:a]adelay={delay_ms}|{delay_ms}[aud]',
            '-map', '0:v', '-map', '[aud]',
            '-c:v', 'copy', '-c:a', 'aac',
            output_file
        ]
    elif offset < 0:
        # If offset is negative, trim the audio
        trim_start = abs(offset) / 1000  # Convert milliseconds to seconds
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', video_file,
            '-filter_complex', f'[0:a]atrim=start={trim_start},asetpts=PTS-STARTPTS[aud]',
            '-map', '0:v', '-map', '[aud]',
            '-c:v', 'copy', '-c:a', 'aac',
            output_file
        ]
    else:
        # No adjustment needed
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', video_file,
            '-c', 'copy',
            output_file
        ]

    logging.debug(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
    
    try:
        subprocess.run(ffmpeg_cmd, check=True)
        logging.info("Video synchronization completed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during synchronization: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Synchronize video using given offset")
    parser.add_argument('--videofile', type=str, required=True, help='Path to the input video file')
    parser.add_argument('--offset', type=int, required=True, help='Offset in milliseconds to adjust audio')
    parser.add_argument('--outputfile', type=str, required=True, help='Path to the output synchronized video file')
    args = parser.parse_args()

    sync_video(args.videofile, args.offset, args.outputfile)
