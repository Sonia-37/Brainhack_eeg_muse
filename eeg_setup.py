"""
EEG Study - Auto Folder Creator + Recording Launcher
=====================================================
Usage:
  python eeg_setup.py                  # interactive mode (asks everything)
  python eeg_setup.py --setup-only     # just create all folders upfront

participants.csv must exist next to this script with columns:
  id, his_id, first_name, sex, birthday, hand, group
  group: control / research

Folder structure per recording condition:
  eeg_study/
  └── participant_01/
      └── session_1/
          ├── pre/
          │   ├── open_eyes/
          │   │   ├── csv/
          │   │   ├── raw/
          │   │   └── filtered/
          │   └── closed_eyes/
          │       ├── csv/
          │       ├── raw/
          │       └── filtered/
          └── post/
              ...
"""

import os
import argparse
import subprocess
import pandas as pd
from datetime import datetime

N_PARTICIPANTS  = 5
N_SESSIONS      = 3
RECORDING_SECS  = 120
BASE_DIR        = "eeg_study"
PARTICIPANTS    = "participants.csv"
FILE_TYPES      = ("csv", "raw", "filtered")
ALL_CONDITIONS  = ("open_eyes", "closed_eyes")

GROUP_LABELS = {
    "control":  "CONTROL  [no exercise]",
    "research": "RESEARCH [eye exercises]",
}


# Participant / group helpers
def load_group_map():
    """
    Read participants.csv and return a dict {id: group}.
    Returns empty dict with a warning if file or column is missing.
    """
    if not os.path.isfile(PARTICIPANTS):
        print(f"  [!] '{PARTICIPANTS}' not found — group info unavailable.")
        return {}

    df = pd.read_csv(PARTICIPANTS)
    df.columns = df.columns.str.strip().str.lower()

    if "group" not in df.columns:
        print(f"  [!] No 'group' column in '{PARTICIPANTS}' — add it (control / research).")
        return {}

    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    return {int(row["id"]): str(row["group"]).strip() for _, row in df.iterrows()}


def get_group_label(p, group_map):
    """Return a formatted group string for participant p."""
    group = group_map.get(p)
    if group is None:
        return "GROUP UNKNOWN  [check participants.csv]"
    return GROUP_LABELS.get(group.lower(), group.upper())


def print_participant_banner(p, s, group_map):
    """Print a clearly visible banner showing participant + group."""
    group_str = get_group_label(p, group_map)
    line = "=" * 54
    print(f"\n  {line}")
    print(f"  PARTICIPANT  :  P{p:02d}")
    print(f"  SESSION      :  {s}")
    print(f"  GROUP        :  {group_str}")
    print(f"  {line}")


# Folder helpers
def condition_path(p, s, timing, condition):
    return os.path.join(
        BASE_DIR,
        f"participant_{p:02d}",
        f"session_{s}",
        timing,
        condition,
    )


def create_all_folders():
    """Build the full folder tree for every participant up front."""
    count = 0
    for p in range(1, N_PARTICIPANTS + 1):
        for s in range(1, N_SESSIONS + 1):
            for timing in ("pre", "post"):
                for condition in ALL_CONDITIONS:
                    base = condition_path(p, s, timing, condition)
                    for ft in FILE_TYPES:
                        os.makedirs(os.path.join(base, ft), exist_ok=True)
                        count += 1
    print(f"  Folder tree ready ({count} folders).")


# Interactive prompts
def ask_timings():
    print("\n  Which timings do you want to record?")
    print("    1  pre only")
    print("    2  post only")
    print("    3  both pre and post")
    while True:
        choice = input("  Choice (1/2/3): ").strip()
        if choice == "1":   return ["pre"]
        elif choice == "2": return ["post"]
        elif choice == "3": return ["pre", "post"]
        else: print("  Please enter 1, 2, or 3.")


def ask_conditions():
    print("\n  Which eye conditions do you want to record?")
    print("    1  open eyes only")
    print("    2  closed eyes only")
    print("    3  both  (open first,   then closed)")
    print("    4  both  (closed first, then open)")
    while True:
        choice = input("  Choice (1/2/3/4): ").strip()
        if choice == "1":   return ["open_eyes"]
        elif choice == "2": return ["closed_eyes"]
        elif choice == "3": return ["open_eyes", "closed_eyes"]
        elif choice == "4": return ["closed_eyes", "open_eyes"]
        else: print("  Please enter 1, 2, 3, or 4.")


# Recording
def run_recording(p, s, timing, condition, group_map):
    base     = condition_path(p, s, timing, condition)
    csv_dir  = os.path.join(base, "csv")
    raw_dir  = os.path.join(base, "raw")
    filt_dir = os.path.join(base, "filtered")

    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename   = os.path.join(
        csv_dir,
        f"P{p:02d}_S{s}_{timing}_{condition}_{timestamp}.csv"
    )

    cond_label = "OPEN EYES"   if condition == "open_eyes" else "CLOSED EYES"
    group_str  = get_group_label(p, group_map)

    print(f"\n  {'─'*54}")
    print(f"  P{p:02d}  |  Session {s}  |  {timing.upper()}  |  {cond_label}")
    print(f"  Group            :  {group_str}")
    print(f"  CSV will save to :  {filename}")
    print(f"  Drop raw.fif  -> :  {raw_dir}/")
    print(f"  Drop filt.fif -> :  {filt_dir}/")
    print(f"  Duration         :  {RECORDING_SECS} s  ({RECORDING_SECS // 60} min)")
    input("\n  Press ENTER to start recording...")

    subprocess.run(
        ["muselsl", "record", "--duration", str(RECORDING_SECS), "--filename", filename],
        check=True,
    )
    print(f"\n  Recording saved -> {filename}")


# Interactive mode
def interactive_mode():
    print("\n  EEG Study — Recording\n")

    group_map = load_group_map()

    # Show full group summary so experimenter can verify before starting
    if group_map:
        print("  Participant groups loaded from participants.csv:")
        for pid, grp in sorted(group_map.items()):
            label = GROUP_LABELS.get(grp.lower(), grp.upper())
            print(f"    P{pid:02d}  →  {label}")
    print()

    p = int(input(f"  Participant number (1–{N_PARTICIPANTS}): "))
    s = int(input(f"  Session number    (1–{N_SESSIONS}): "))

    # Prominent banner — group is impossible to miss
    print_participant_banner(p, s, group_map)

    timings    = ask_timings()
    conditions = ask_conditions()

    order = [
        (timing, condition)
        for timing in timings
        for condition in conditions
    ]

    print(f"\n  Recording plan — {len(order)} slot(s):")
    for i, (timing, condition) in enumerate(order, 1):
        cond_label = "open eyes" if condition == "open_eyes" else "closed eyes"
        print(f"    {i}. {timing:<4}  —  {cond_label}")

    input("\n  Press ENTER to begin the first recording...")

    for timing, condition in order:
        run_recording(p, s, timing, condition, group_map)

    # Final summary
    group_str = get_group_label(p, group_map)
    print(f"\n  {'='*54}")
    print(f"  All {len(order)} recording(s) complete")
    print(f"  Participant :  P{p:02d}  |  Session {s}")
    print(f"  Group       :  {group_str}")
    print(f"  {'='*54}")
    print("\n  Reminder — copy preprocessed files to:")
    for timing, condition in order:
        base = condition_path(p, s, timing, condition)
        print(f"    raw      -> {os.path.join(base, 'raw')}/")
        print(f"    filtered -> {os.path.join(base, 'filtered')}/")
    print()


# Entry point
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