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
    iouThres = 0.5  # Minimum IOU between consecutive face detections
    tracks = []

    while True:
        track = []
        for framefaces in scenefaces:
            for face in framefaces:
                if track == []:
                    track.append(face)
                    framefaces.remove(face)
                elif face['frame'] - track[-1]['frame'] <= opt.num_failed_det:
                    iou = bb_intersection_over_union(face['bbox'], track[-1]['bbox'])
                    if iou > iouThres:
                        track.append(face)
                        framefaces.remove(face)
                        continue
                else:
                    break

        if track == []:
            break
        elif len(track) > opt.min_track:
            framenum = np.array([f['frame'] for f in track])
            bboxes = np.array([np.array(f['bbox']) for f in track])

            frame_i = np.arange(framenum[0], framenum[-1] + 1)

            bboxes_i = []
            for ij in range(0, 4):
                interpfn = interp1d(framenum, bboxes[:, ij])
                bboxes_i.append(interpfn(frame_i))
            bboxes_i = np.stack(bboxes_i, axis=1)

            if max(np.mean(bboxes_i[:, 2] - bboxes_i[:, 0]), np.mean(bboxes_i[:, 3] - bboxes_i[:, 1])) > opt.min_face_size:
                tracks.append({'frame': frame_i, 'bbox': bboxes_i})

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

