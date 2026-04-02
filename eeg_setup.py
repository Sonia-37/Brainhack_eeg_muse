"""
EEG Study - Auto Folder Creator + Recording Launcher
=====================================================
Usage:
  python eeg_setup.py                  # interactive mode (asks everything)
  python eeg_setup.py --setup-only     # just create all folders upfront

Folder structure per recording condition:
  eeg_study/
  └── participant_01/
      └── session_1/
          ├── pre/
          │   ├── open_eyes/
          │   │   ├── csv/          ← muselsl .csv recordings land here
          │   │   ├── raw/          ← raw .fif files go here
          │   │   └── filtered/     ← filtered .fif files go here
          │   └── closed_eyes/
          │       ├── csv/
          │       ├── raw/
          │       └── filtered/
          └── post/
              ├── open_eyes/
              │   ├── csv/
              │   ├── raw/
              │   └── filtered/
              └── closed_eyes/
                  ├── csv/
                  ├── raw/
                  └── filtered/
"""

import os
import argparse
import subprocess
from datetime import datetime

N_PARTICIPANTS = 5            
N_SESSIONS     = 3
RECORDING_SECS = 120          # 2 minutes per condition
BASE_DIR       = "eeg_study"  # root folder (created next to this script)
FILE_TYPES     = ("csv", "raw", "filtered")
# 


def condition_path(p, s, timing, condition):
    """Root path for one recording slot (no file-type subfolder)."""
    return os.path.join(
        BASE_DIR,
        f"participant_{p:02d}",
        f"session_{s}",
        timing,       # "pre" or "post"
        condition,    # "open_eyes" or "closed_eyes"
    )


def create_all_folders():
    """Build the full folder tree for every participant up front."""
    count = 0
    for p in range(1, N_PARTICIPANTS + 1):
        for s in range(1, N_SESSIONS + 1):
            for timing in ("pre", "post"):
                for condition in ("open_eyes", "closed_eyes"):
                    base = condition_path(p, s, timing, condition)
                    for ft in FILE_TYPES:
                        os.makedirs(os.path.join(base, ft), exist_ok=True)
                        count += 1


def run_recording(p, s, timing, condition):
    """
    Launch muselsl record for one condition and save the CSV with a
    descriptive filename into the csv/ subfolder.

    After recording, prints reminder paths for raw/ and filtered/ so
    you know exactly where to drop the .fif files during preprocessing.
    """
    base      = condition_path(p, s, timing, condition)
    csv_dir   = os.path.join(base, "csv")
    raw_dir   = os.path.join(base, "raw")
    filt_dir  = os.path.join(base, "filtered")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = os.path.join(
        csv_dir,
        f"P{p:02d}_S{s}_{timing}_{condition}_{timestamp}.csv"
    )

    print(f"  Participant {p:02d}  |  Session {s}  |  {timing.upper()}  |  {condition}")
    print(f"  CSV will save to : {filename}")
    print(f"  Drop raw.fif  -> : {raw_dir}/")
    print(f"  Drop filt.fif -> : {filt_dir}/")
    print(f"  Duration         : {RECORDING_SECS} s  ({RECORDING_SECS // 60} min)")
    input("\n  Press ENTER to start recording...")

    subprocess.run(
        ["muselsl", "record", "--duration", str(RECORDING_SECS), "--filename", filename],
        check=True,
    )

    print(f"\n  Recording saved -> {filename}")


def interactive_mode():
    """Walk the experimenter through recordings for one session."""
    print("\n EEG Study  - Recording \n")
 
    p = int(input(f"Participant number (1 - {N_PARTICIPANTS}): "))
    s = int(input(f"Session number    (1 - {N_SESSIONS}): "))
 
    print("\n  Which recordings do you want to run?")
    print("    1  pre only")
    print("    2  post only")
    print("    3  both pre and post")
    choice = input("  Choice (1/2/3): ").strip()
 
    if choice == "1":
        timings = ["pre"]
    elif choice == "2":
        timings = ["post"]
    else:
        timings = ["pre", "post"]
 
    order = [
        (timing, condition)
        for timing in timings
        for condition in ("open_eyes", "closed_eyes")
    ]
 
    for timing, condition in order:
        run_recording(p, s, timing, condition)
 
    print(f"\n{'='*52}")
    print(f"  All {len(order)} recording(s) done for P{p:02d} / Session {s}")
    print(f"{'='*52}\n")
    print("  Reminder - copy your preprocessed files to:")
    for timing, condition in order:
        base = condition_path(p, s, timing, condition)
        print(f"    raw      -> {os.path.join(base, 'raw')}/")
        print(f"    filtered -> {os.path.join(base, 'filtered')}/")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EEG study folder manager + recorder")
    parser.add_argument(
        "--setup-only", action="store_true",
        help="Create folder tree without launching any recording"
    )
    args = parser.parse_args()

    create_all_folders()

    if not args.setup_only:
        interactive_mode()
