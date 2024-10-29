#!/usr/bin/python
# -*- coding: utf-8 -*-

import time, pdb, argparse, subprocess, pickle, os, gzip, glob, logging
from SyncNetInstance import *

# Set up logging to output to debug_log.txt
logging.basicConfig(filename='debug_log.txt', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# ==================== PARSE ARGUMENT ====================

logging.debug("Starting argument parsing.")
parser = argparse.ArgumentParser(description="SyncNet")
parser.add_argument('--initial_model', type=str, default="data/syncnet_v2.model", help='')
parser.add_argument('--batch_size', type=int, default=20, help='')
parser.add_argument('--vshift', type=int, default=15, help='')
parser.add_argument('--data_dir', type=str, default='data/work', help='')
parser.add_argument('--videofile', type=str, default='', help='')
parser.add_argument('--reference', type=str, default='', help='')
opt = parser.parse_args()

logging.debug(f"Arguments parsed: {opt}")

# Set directory attributes
setattr(opt, 'avi_dir', os.path.join(opt.data_dir, 'pyavi'))
setattr(opt, 'tmp_dir', os.path.join(opt.data_dir, 'pytmp'))
setattr(opt, 'work_dir', os.path.join(opt.data_dir, 'pywork'))
setattr(opt, 'crop_dir', os.path.join(opt.data_dir, 'pycrop'))

logging.debug("Directory paths set.")
logging.debug(f"AVI directory: {opt.avi_dir}")
logging.debug(f"TMP directory: {opt.tmp_dir}")
logging.debug(f"Work directory: {opt.work_dir}")
logging.debug(f"Crop directory: {opt.crop_dir}")

# ==================== LOAD MODEL AND FILE LIST ====================

logging.debug("Loading model...")
s = SyncNetInstance()
s.loadParameters(opt.initial_model)
logging.debug(f"Model {opt.initial_model} loaded successfully.")

# Get list of .avi files in the crop directory
flist = glob.glob(os.path.join(opt.crop_dir, opt.reference, '0*.avi'))
flist.sort()
logging.debug(f"Video files found for processing: {flist}")

# ==================== GET OFFSETS ====================

dists = []
logging.debug("Starting offset evaluation for each video file.")
for idx, fname in enumerate(flist):
    logging.debug(f"Evaluating file {idx+1}/{len(flist)}: {fname}")
    offset, conf, dist = s.evaluate(opt, videofile=fname)
    logging.debug(f"Offset: {offset}, Confidence: {conf}, Distance: {dist}")
    dists.append(dist)

# ==================== PRINT RESULTS TO FILE ====================

output_path = os.path.join(opt.work_dir, opt.reference, 'activesd.pckl')
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'wb') as fil:
    pickle.dump(dists, fil)
logging.debug(f"Results saved to {output_path}")
logging.debug("Script execution completed.")
