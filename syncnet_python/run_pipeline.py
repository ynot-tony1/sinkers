#!/usr/bin/python

import sys, time, os, pdb, argparse, pickle, subprocess, glob, cv2
import numpy as np
from shutil import rmtree

import scenedetect
from scenedetect.video_manager import VideoManager
from scenedetect.scene_manager import SceneManager
from scenedetect.frame_timecode import FrameTimecode
from scenedetect.stats_manager import StatsManager
from scenedetect.detectors import ContentDetector

from scipy.interpolate import interp1d
from scipy.io import wavfile
from scipy import signal

from detectors import S3FD

# ========== ========== ========== ==========
# # PARSE ARGS
# ========== ========== ========== ==========

parser = argparse.ArgumentParser(description="FaceTracker")
parser.add_argument('--data_dir', type=str, default='data/work', help='Output directory')
parser.add_argument('--videofile', type=str, default='', help='Input video file')
parser.add_argument('--reference', type=str, default='', help='Video reference')
parser.add_argument('--facedet_scale', type=float, default=0.25, help='Scale factor for face detection')
parser.add_argument('--crop_scale', type=float, default=0.40, help='Scale bounding box')
parser.add_argument('--min_track', type=int, default=100, help='Minimum face track duration')
parser.add_argument('--frame_rate', type=int, default=25, help='Frame rate')
parser.add_argument('--num_failed_det', type=int, default=25, help='Number of missed detections allowed before tracking is stopped')
parser.add_argument('--min_face_size', type=int, default=100, help='Minimum face size in pixels')
opt = parser.parse_args()

setattr(opt, 'avi_dir', os.path.join(opt.data_dir, 'pyavi'))
setattr(opt, 'tmp_dir', os.path.join(opt.data_dir, 'pytmp'))
setattr(opt, 'work_dir', os.path.join(opt.data_dir, 'pywork'))
setattr(opt, 'crop_dir', os.path.join(opt.data_dir, 'pycrop'))
setattr(opt, 'frames_dir', os.path.join(opt.data_dir, 'pyframes'))

print(f"Arguments: data_dir={opt.data_dir}, videofile={opt.videofile}, reference={opt.reference}")

# ========== ========== ========== ==========
# # FACE TRACKING
# ========== ========== ========== ==========

def track_shot(opt, scenefaces):
    print("Starting face tracking...")
    iouThres = 0.5
    tracks = []

    for frame_idx, framefaces in enumerate(scenefaces):
        print(f"Processing frame {frame_idx}: Detected faces - {len(framefaces)}")
        
        for face in framefaces:
            print(f"Evaluating face: {face}")

            if tracks:
                last_track_frame = tracks[-1]['frame'][-1]  # Last frame number from the last track
                print(f"Last track frame: {last_track_frame}")
                
                if face['frame'] - last_track_frame <= opt.num_failed_det:
                    last_track_face = tracks[-1]['bbox'][-1]  # Last bounding box of the last track
                    iou = bb_intersection_over_union(face['bbox'], last_track_face)
                    print(f"IOU with last track face: {iou}")

                    if iou > iouThres:
                        print("Linking to existing track.")
                        tracks[-1]['frame'].append(face['frame'])
                        tracks[-1]['bbox'].append(face['bbox'])
                    else:
                        print("Starting a new track due to low IOU.")
                        tracks.append({'frame': [face['frame']], 'bbox': [face['bbox']]})
                else:
                    print("Starting a new track as frames are too far apart.")
                    tracks.append({'frame': [face['frame']], 'bbox': [face['bbox']]})
            else:
                print("Starting a new track as no previous track is available.")
                tracks.append({'frame': [face['frame']], 'bbox': [face['bbox']]})

    print(f"Completed tracking with {len(tracks)} tracks found.")
    return tracks





# ========== ========== ========== ==========
# # FACE DETECTION
# ========== ========== ========== ==========

def inference_video(opt):
    print("Starting face detection...")
    DET = S3FD(device='cuda')

    flist = glob.glob(os.path.join(opt.frames_dir, opt.reference, '*.jpg'))
    flist.sort()
    print(f"Total frames to process for face detection: {len(flist)}")

    dets = []

    for fidx, fname in enumerate(flist):
        start_time = time.time()

        image = cv2.imread(fname)
        image_np = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        bboxes = DET.detect_faces(image_np, conf_th=0.9, scales=[opt.facedet_scale])

        dets.append([])
        for bbox in bboxes:
            dets[-1].append({'frame': fidx, 'bbox': (bbox[:-1]).tolist(), 'conf': bbox[-1]})

        elapsed_time = time.time() - start_time
        print(f'{fname} - Frame {fidx:05d}; {len(dets[-1])} detections; {1/elapsed_time:.2f} Hz')

    savepath = os.path.join(opt.work_dir, opt.reference, 'faces.pckl')
    with open(savepath, 'wb') as fil:
        pickle.dump(dets, fil)

    print(f"Face detection completed, results saved to {savepath}")
    return dets



def bb_intersection_over_union(boxA, boxB):
    # Unpack the bounding box coordinates
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    # Compute the area of intersection rectangle
    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)

    # Compute the area of both the prediction and ground-truth rectangles
    boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
    boxBArea = (boxB[2] - boxB[0] + 1) * (boxB[3] - boxB[1] + 1)

    # Compute the intersection over union by dividing the intersection area by the sum of
    # the prediction + ground-truth areas - the intersection area
    iou = interArea / float(boxAArea + boxBArea - interArea)

    return iou

import cv2

def crop_video(opt, track, output_dir):
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Load the video file corresponding to the track
    video_path = os.path.join(opt.avi_dir, opt.reference, 'video.avi')
    cap = cv2.VideoCapture(video_path)

    for i, bbox in enumerate(track['bbox']):
        # Read the video frame corresponding to the track
        frame_num = track['frame'][i]
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()

        if ret:
            # Crop the frame using the bounding box
            x1, y1, x2, y2 = map(int, bbox)
            cropped_frame = frame[y1:y2, x1:x2]

            # Save the cropped frame to the output directory
            output_path = os.path.join(output_dir, f'frame_{frame_num:05d}.jpg')
            cv2.imwrite(output_path, cropped_frame)

    cap.release()




# ========== ========== ========== ==========
# # SCENE DETECTION
# ========== ========== ========== ==========

def scene_detect(opt):
    print("Starting scene detection...")
    video_manager = VideoManager([os.path.join(opt.avi_dir, opt.reference, 'video.avi')])
    stats_manager = StatsManager()
    scene_manager = SceneManager(stats_manager)
    scene_manager.add_detector(ContentDetector())

    video_manager.set_downscale_factor()
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)

    scene_list = scene_manager.get_scene_list(video_manager.get_base_timecode())
    savepath = os.path.join(opt.work_dir, opt.reference, 'scene.pckl')
    if not scene_list:
        scene_list = [(video_manager.get_base_timecode(), video_manager.get_current_timecode())]

    with open(savepath, 'wb') as fil:
        pickle.dump(scene_list, fil)
    
    print(f"Scene detection completed, {len(scene_list)} scenes detected, results saved to {savepath}")
    return scene_list

# ========== ========== ========== ==========
# # EXECUTE DEMO
# ========== ========== ========== ==========

# ========== MAKE NEW DIRECTORIES ==========

print("Creating working directory structure...")

# Convert Video and Extract Frames
print("Converting video to AVI format and extracting frames...")
command = f"ffmpeg -y -i {opt.videofile} -qscale:v 2 -async 1 -r 25 {os.path.join(opt.avi_dir, opt.reference, 'video.avi')}"
subprocess.call(command, shell=True)

command = f"ffmpeg -y -i {os.path.join(opt.avi_dir, opt.reference, 'video.avi')} -qscale:v 2 -threads 1 -f image2 {os.path.join(opt.frames_dir, opt.reference, '%06d.jpg')}"
subprocess.call(command, shell=True)

command = f"ffmpeg -y -i {os.path.join(opt.avi_dir, opt.reference, 'video.avi')} -ac 1 -vn -acodec pcm_s16le -ar 16000 {os.path.join(opt.avi_dir, opt.reference, 'audio.wav')}"
subprocess.call(command, shell=True)

# Face Detection
faces = inference_video(opt)

# Scene Detection
scene = scene_detect(opt)

# Face Tracking
alltracks = []
for shot in scene:
    if shot[1].frame_num - shot[0].frame_num >= opt.min_track:
        alltracks.extend(track_shot(opt, faces[shot[0].frame_num:shot[1].frame_num]))

# Face Track Cropping
print("Starting video cropping for each face track...")
vidtracks = []
for ii, track in enumerate(alltracks):
    vidtracks.append(crop_video(opt, track, os.path.join(opt.crop_dir, opt.reference, f'{ii:05d}')))

# Save Results
savepath = os.path.join(opt.work_dir, opt.reference, 'tracks.pckl')
print(f"Saving final tracks data to {savepath}")
with open(savepath, 'wb') as fil:
    pickle.dump(vidtracks, fil)

print("Execution completed.")

