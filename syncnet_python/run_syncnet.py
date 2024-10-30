#!/usr/bin/python
# -*- coding: utf-8 -*-

import time, pdb, argparse, subprocess, pickle, os, gzip, glob
from SyncNetInstance import *
import numpy as np
import matplotlib.pyplot as plt

# ==================== PARSE ARGUMENT ====================

parser = argparse.ArgumentParser(description="SyncNet")
parser.add_argument('--initial_model', type=str, default="data/syncnet_v2.model", help='')
parser.add_argument('--batch_size', type=int, default='20', help='')
parser.add_argument('--vshift_initial', type=int, default='50', help='Initial maximum shift in frames for synchronization')
parser.add_argument('--vshift_fine', type=int, default='15', help='Fine maximum shift in frames for synchronization')
parser.add_argument('--data_dir', type=str, default='data/work', help='')
parser.add_argument('--videofile', type=str, default='', help='')
parser.add_argument('--reference', type=str, default='', help='')
parser.add_argument('--conf_threshold', type=float, default='0.8', help='Confidence threshold for fine synchronization')
opt = parser.parse_args()

setattr(opt, 'avi_dir', os.path.join(opt.data_dir, 'pyavi'))
setattr(opt, 'tmp_dir', os.path.join(opt.data_dir, 'pytmp'))
setattr(opt, 'work_dir', os.path.join(opt.data_dir, 'pywork'))
setattr(opt, 'crop_dir', os.path.join(opt.data_dir, 'pycrop'))

# ==================== LOAD MODEL AND FILE LIST ====================

s = SyncNetInstance()
s.loadParameters(opt.initial_model)
print("Model %s loaded." % opt.initial_model)

flist = glob.glob(os.path.join(opt.crop_dir, opt.reference, '0*.avi'))
flist.sort()

# ==================== DEFINE SYNCHRONIZATION FUNCTIONS ====================

def refine_offset_with_curve_fitting(shifts, distances):
    min_idx = np.argmin(distances)
    if 0 < min_idx < len(distances) - 1:
        # Extract the three points around the minimum
        x = shifts[min_idx - 1:min_idx + 2]
        y = distances[min_idx - 1:min_idx + 2]
        # Fit a quadratic curve
        coeffs = np.polyfit(x, y, 2)
        # Vertex of the parabola (minimum point)
        offset = -coeffs[1] / (2 * coeffs[0])
    else:
        offset = shifts[min_idx]
    return offset

def synchronize_video(s, opt, fname, initial_vshift, fine_vshift, conf_threshold):
    # Initial broad synchronization
    opt.vshift = initial_vshift
    offset_coarse, conf_coarse, dist_coarse = s.evaluate(opt, videofile=fname)
    
    if conf_coarse < conf_threshold:
        # Define the narrow range around the coarse offset
        vshift_start = int(round(offset_coarse)) - fine_vshift
        vshift_end = int(round(offset_coarse)) + fine_vshift
        
        # Fine synchronization within the narrow range
        offset_fine, conf_fine, dist_fine = s.evaluate(opt, videofile=fname, vshift_start=vshift_start, vshift_end=vshift_end)
        
        # Define shifts and distances for refinement
        shifts = range(vshift_start, vshift_end + 1)
        distances = dist_fine  # Assuming dist_fine corresponds to these shifts
        
        # Refine the offset with curve fitting
        refined_offset = refine_offset_with_curve_fitting(shifts, distances)
    else:
        refined_offset = offset_coarse
    
    return refined_offset

# ==================== GET OFFSETS ====================

dists = []
offsets = []
confidences = []

for idx, fname in enumerate(flist):
    print(f"Processing file {idx+1}/{len(flist)}: {fname}")
    try:
        refined_offset = synchronize_video(s, opt, fname, initial_vshift=opt.vshift_initial, fine_vshift=opt.vshift_fine, conf_threshold=opt.conf_threshold)
        offsets.append(refined_offset)
    except Exception as e:
        print(f"Error processing {fname}: {e}")
        offsets.append(None)
        continue



# ==================== PRINT RESULTS TO FILE ====================

with open(os.path.join(opt.work_dir, opt.reference, 'activesd.pckl'), 'wb') as fil:
    pickle.dump(offsets, fil)

print("Synchronization complete. Results saved.")
