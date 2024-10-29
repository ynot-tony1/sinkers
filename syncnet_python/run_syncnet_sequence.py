#!/usr/bin/env python3

import subprocess
import os

# Define paths and filenames
data_dir = 'data'
original_video = os.path.join(data_dir, 'example.avi')
out_of_sync_video = os.path.join(data_dir, 'example_out_of_sync.avi')
back_in_sync_video = os.path.join(data_dir, 'example_back_in_sync.avi')

try:
    # Step 1: Run SyncNet on the original video
    print("Running SyncNet on original video...")
    result = subprocess.run(
        ['python3', 'run_syncnet.py', '--videofile', original_video, '--reference', 'example'],
        capture_output=True, text=True
    )
    print("Output from SyncNet on original video:", result.stdout)
    print("Errors (if any):", result.stderr)

    # Step 2: Create an out-of-sync version of the video
    print("Creating out-of-sync video...")
    delay_ms = 1000  # Delay in milliseconds (1000ms = 1s)
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-i', original_video,
        '-filter_complex', f'[0:a]adelay={delay_ms}|{delay_ms}[aud]',
        '-map', '0:v', '-map', '[aud]',
        '-c:v', 'copy', '-c:a', 'aac',
        out_of_sync_video
    ]
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    print("Output from FFmpeg:", result.stdout)
    print("Errors (if any):", result.stderr)

    # Step 3: Run SyncNet on the out-of-sync video
    print("Running SyncNet on out-of-sync video...")
    result = subprocess.run(
        ['python3', 'run_syncnet.py', '--videofile', out_of_sync_video, '--reference', 'example_out_of_sync'],
        capture_output=True, text=True
    )
    print("Output from SyncNet on out-of-sync video:", result.stdout)
    print("Errors (if any):", result.stderr)

    # Step 4: Synchronize the audio using sync_video.py with .pckl format
    print("Synchronizing the out-of-sync video...")
    results_file = os.path.join(data_dir, 'work', 'pywork', 'example_out_of_sync', 'activesd.pckl')  # Updated to .pckl
    result = subprocess.run(
        ['python3', 'sync_video.py', '--videofile', out_of_sync_video, '--resultsfile', results_file, '--outputfile', back_in_sync_video],
        capture_output=True, text=True
    )
    print("Output from sync_video.py:", result.stdout)
    print("Errors (if any):", result.stderr)

    # Step 5: Run SyncNet on the synchronized video
    print("Running SyncNet on synchronized video...")
    result = subprocess.run(
        ['python3', 'run_syncnet.py', '--videofile', back_in_sync_video, '--reference', 'example_back_in_sync'],
        capture_output=True, text=True
    )
    print("Output from SyncNet on synchronized video:", result.stdout)
    print("Errors (if any):", result.stderr)

    print("All steps completed.")

except Exception as e:
    print("An error occurred:", e)
