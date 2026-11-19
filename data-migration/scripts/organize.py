"""
Script to organize files into their
"""
import os
import shutil
from tqdm import tqdm


KEY_WORD_TABLE = [
    "FlightState_zoa",
    "FlightState_view",
    "Custom_view",
    "Wkload",
    "Pilot_zoa",
    "Custom_zoa",
    "CompMet_view",
    "Traj_zoa",
    "AtcState_view",
    "Atc_ZOA",
]


for dir_name in KEY_WORD_TABLE:
    if not os.path.exists(dir_name):
        os.mkdir(dir_name)


for file in tqdm(os.listdir()):
    if not os.path.isfile(file):
        continue

    for key_word in KEY_WORD_TABLE:
        if key_word in file:
            shutil.move(file, key_word)

print("Done")
