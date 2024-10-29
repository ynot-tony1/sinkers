#!/usr/bin/env python3

import numpy as np
import subprocess
import argparse
import pickle

def get_video_fps(video_file):
    # Get the frame rate of the video using ffprobe
    cmd = [
        'ffprobe', '-v', '0', '-of', 'csv=p=0',
        '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
        video_file
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fps_info = result.stdout.decode('utf-8').strip()
    num, denom = map(float, fps_info.split('/'))
    fps = num / denom
    return fps

def sync_video(video_file, results_file, output_file):
    # Load the offset results from SyncNet's .pckl file
    with open(results_file, 'rb') as f:
        dists = pickle.load(f)
    
    # Calculate the average offset if multiple entries exist
    offset = np.mean(dists) if len(dists) > 0 else 0

    # Get the video's frame rate
    fps = get_video_fps(video_file)

    # Calculate time shift in seconds
    time_shift = offset / fps

    # Calculate the amount to adjust the audio (negative of time_shift)
    shift_amount = -time_shift

    # Build the ffmpeg command based on shift_amount
    if shift_amount > 0:
        # Delay audio
        delay_ms = int(shift_amount * 1000)
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', video_file,
            '-filter_complex', f'[0:a]adelay={delay_ms}|{delay_ms}[aud]',
            '-map', '0:v', '-map', '[aud]',
            '-c:v', 'copy', '-c:a', 'aac',
            output_file
        ]
    elif shift_amount < 0:
        # Advance audio
        trim_start = -shift_amount
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

    # Execute the ffmpeg command
    subprocess.run(ffmpeg_cmd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Synchronize video using SyncNet offset")
    parser.add_argument('--videofile', type=str, required=True, help='Path to the input video file')
    parser.add_argument('--resultsfile', type=str, required=True, help='Path to the SyncNet .pckl file')
    parser.add_argument('--outputfile', type=str, required=True, help='Path to the output synchronized video file')
    args = parser.parse_args()

    sync_video(args.videofile, args.resultsfile, args.outputfile)
