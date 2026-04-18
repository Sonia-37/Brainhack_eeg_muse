"""
EEG Preprocessing Pipeline
===========================
Loads participant metadata from participants.csv, reads a muselsl CSV,
builds a properly annotated MNE Raw object, filters it, and saves both
raw.fif and filtered.fif into the correct folder from your study tree.

participants.csv columns:
  id, his_id, first_name, sex, birthday, hand, group
  sex:   1=Male  2=Female  0=Unknown
  hand:  1=Right 2=Left    3=Both  0=Unknown
  group: control / research
  birthday format: YYYY-MM-DD

Single-recording usage
----------------------
  python preprocess.py -p 3 -s 1 -t pre -c open_eyes
  python preprocess.py -p 3 -s 1 -t pre -c open_eyes --bad-channels AF7
  python preprocess.py -p 3 -s 1 -t pre -c open_eyes --skip-plots

Batch usage
-----------
  python preprocess.py -p 3 -s 1 -t pre      # all conditions
  python preprocess.py -p 3 -s 1             # all timings + conditions
  python preprocess.py -p 3                  # all sessions
  python preprocess.py -s 1 -A              # session 1 for ALL participants
  python preprocess.py                       # entire dataset
"""

import os
import argparse
from datetime import datetime, timezone

import pandas as pd
import numpy as np
import mne
import matplotlib.pyplot as plt

BASE_DIR     = "brainhack_eeg_muse"
PARTICIPANTS = "participants.csv"
CH_NAMES     = ["TP9", "AF7", "AF8", "TP10"]
SFREQ        = 256
EXPERIMENTER = "Zofia Sikorska"

NOTCH_FREQS  = [50.0, 100.0]
BANDPASS     = (0.5, 35.0)

ALL_TIMINGS    = ["pre", "post"]
ALL_CONDITIONS = ["open_eyes", "closed_eyes"]

GROUP_LABELS = {
    "control":  "CONTROL  [no exercise]",
    "research": "RESEARCH [eye exercises]",
}

# Colours used in QC plots — different per group so it's instantly obvious
GROUP_COLORS = {
    "control":  ["#4a90d9", "#5ba85b", "#7b68ee", "#e07b39"],  # blue tones
    "research": ["#c0392b", "#e67e22", "#8e44ad", "#16a085"],  # warm tones
}
DEFAULT_COLORS = ["purple", "mediumseagreen", "dodgerblue", "tomato"]


# Path helpers
def condition_path(p, s, timing, condition):
    return os.path.join(
        BASE_DIR,
        f"participant_{p:02d}",
        f"session_{s}",
        timing,
        condition,
    )


def find_csv(p, s, timing, condition):
    csv_dir = os.path.join(condition_path(p, s, timing, condition), "csv")
    print(f"Scanning directory: {csv_dir}")
    if not os.path.isdir(csv_dir):
        print("...it is actually not a directory.")
        return None
    csvs = sorted(
        [f for f in os.listdir(csv_dir) if f.endswith(".csv")],
        reverse=True,
    )
    if not csvs:
        return None
    if len(csvs) > 1:
        print(f"  [!] Multiple CSVs found — using the most recent: {csvs[0]}")
        print(f"      Others: {csvs[1:]}")
    return os.path.join(csv_dir, csvs[0])


def output_paths(p, s, timing, condition):
    base    = condition_path(p, s, timing, condition)
    tag     = f"P{p:02d}_S{s}_{timing}_{condition}"
    raw_fif = os.path.join(base, "raw",      f"{tag}_raw.fif")
    flt_fif = os.path.join(base, "filtered", f"{tag}_filtered_raw.fif")
    return raw_fif, flt_fif


# Participant metadata
def load_participant(p):
    """
    Read participants.csv and return the row for participant p as a dict.
    Includes the 'group' field (control / research).
    """
    if not os.path.isfile(PARTICIPANTS):
        raise FileNotFoundError(
            f"'{PARTICIPANTS}' not found. Create it with columns:\n"
            "  id, his_id, first_name, sex, birthday, hand, group"
        )

    df = pd.read_csv(PARTICIPANTS)
    df.columns = df.columns.str.strip().str.lower()
    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")

    row = df[df["id"] == p]
    if row.empty:
        raise ValueError(
            f"Participant {p} not found in {PARTICIPANTS}.\n"
            f"Available IDs: {sorted(df['id'].dropna().astype(int).tolist())}"
        )
    row = row.iloc[0]

    birthday = datetime.strptime(str(row["birthday"]).strip(), "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )

    group = str(row["group"]).strip() if "group" in df.columns else None

    return {
        "id":       int(row["id"]),
        "his_id":   str(row["his_id"]).strip(),
        "sex":      int(row["sex"]),
        "birthday": birthday,
        "hand":     int(row["hand"]),
        "group":    group,
    }


def all_participant_ids():
    if not os.path.isfile(PARTICIPANTS):
        raise FileNotFoundError(f"'{PARTICIPANTS}' not found.")
    df = pd.read_csv(PARTICIPANTS)
    df.columns = df.columns.str.strip().str.lower()
    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    return sorted(df["id"].dropna().astype(int).tolist())


def all_session_ids():
    sessions = set()
    if not os.path.isdir(BASE_DIR):
        return [1]
    for p_dir in os.listdir(BASE_DIR):
        p_path = os.path.join(BASE_DIR, p_dir)
        if not os.path.isdir(p_path) or not p_dir.startswith("participant_"):
            continue
        for entry in os.listdir(p_path):
            if entry.startswith("session_") and os.path.isdir(os.path.join(p_path, entry)):
                try:
                    sessions.add(int(entry.split("_")[1]))
                except ValueError:
                    pass
    return sorted(sessions) if sessions else [1]


# Group banner — printed once per recording so it's impossible to miss
def print_group_banner(participant):
    """Print a clearly visible group banner for the current participant."""
    group     = participant.get("group")
    group_str = GROUP_LABELS.get((group or "").lower(), (group or "UNKNOWN").upper())
    line      = "─" * 54

    print(f"\n  {line}")
    print(f"  Participant  :  {participant['his_id']}  (id={participant['id']})")
    print(f"  GROUP        :  {group_str}")
    print(f"  {line}")


# MNE object construction
def build_raw(csv_path, participant, rec_datetime):
    df = pd.read_csv(csv_path)
    missing = [c for c in CH_NAMES if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV is missing expected channels: {missing}\n"
            f"Columns found: {list(df.columns)}"
        )

    data = df[CH_NAMES].values.T * 1e-6

    info = mne.create_info(ch_names=CH_NAMES, sfreq=SFREQ, ch_types="eeg")
    info["experimenter"] = EXPERIMENTER
    info.set_meas_date(rec_datetime)

    # MNE's subject_info only accepts specific keys — remove 'group' before passing
    mne_subject_info = {
        k: v for k, v in participant.items()
        if k in ("id", "his_id", "sex", "birthday", "hand")
    }
    info["subject_info"] = mne_subject_info

    raw = mne.io.RawArray(data, info, verbose=False)
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, verbose=False)
    return raw


def parse_recording_datetime(csv_path):
    df = pd.read_csv(csv_path, nrows=5)
    if "timestamps" in df.columns:
        ts = float(df["timestamps"].iloc[0])
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    mtime = os.path.getmtime(csv_path)
    print("  [!] No 'timestamps' column — using file modification time.")
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


# Plotting
def plot_eeg_overview(raw, title="EEG Overview", segment_duration=10,
                      save_path=None, group=None):
    """
    Static multi-panel quality check.
    Channel colours reflect the participant's group so plots are
    instantly distinguishable when reviewing later.
    """
    sfreq    = int(raw.info["sfreq"])
    ch_names = raw.ch_names
    n_ch     = len(ch_names)

    # Choose colour palette based on group
    colors = GROUP_COLORS.get((group or "").lower(), DEFAULT_COLORS)

    n_samples   = min(int(segment_duration * sfreq), raw.n_times)
    data, times = raw[:, :n_samples]
    data_uv     = data * 1e6

    fig, axes = plt.subplots(
        n_ch + 1, 1,
        figsize=(14, 3 * n_ch + 3),
        gridspec_kw={"height_ratios": [2] * n_ch + [1.5]},
    )

    # Add group label to title
    group_str = GROUP_LABELS.get((group or "").lower(), "")
    full_title = f"{title}\n{group_str}" if group_str else title
    fig.suptitle(full_title, fontsize=14, weight="bold", y=1.01)

    for i, (ch, color) in enumerate(zip(ch_names, colors)):
        ax = axes[i]
        ax.plot(times, data_uv[i], color=color, linewidth=0.7, alpha=0.85)
        ax.set_ylabel(f"{ch}\n(µV)", fontsize=10, rotation=0, labelpad=45, va="center")
        ax.spines[["top", "right"]].set_visible(False)
        ax.axhline(0, color="grey", linewidth=0.4, linestyle="--")
        ax.axhspan(-100, 100, color="lightyellow", zorder=0)
        if i < n_ch - 1:
            ax.set_xticklabels([])

    axes[n_ch - 1].set_xlabel("Time (s)", fontsize=11)

    ax_stat = axes[n_ch]
    stds    = data_uv.std(axis=1)
    bars    = ax_stat.bar(ch_names, stds, color=colors, alpha=0.8, edgecolor="white")

    for bar, std_val in zip(bars, stds):
        bar_color = "red" if std_val > 100 else ("orange" if std_val > 50 else None)
        if bar_color:
            bar.set_facecolor(bar_color)
            bar.set_alpha(0.9)
        ax_stat.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{std_val:.1f}",
            ha="center", va="bottom", fontsize=10,
        )

    ax_stat.set_ylabel("Std (µV)", fontsize=10)
    ax_stat.set_title(
        "Channel noise  —  green < 50 µV  |  orange 50–100 µV  |  red > 100 µV",
        fontsize=10,
    )
    ax_stat.spines[["top", "right"]].set_visible(False)
    ax_stat.set_ylim(0, max(stds) * 1.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Plot saved -> {save_path}")

    plt.show()

    print(f"\n  {'Channel':<8}  {'Min (µV)':>10}  {'Max (µV)':>10}  {'Std (µV)':>10}  Status")
    for i, ch in enumerate(ch_names):
        mn, mx, sd = data_uv[i].min(), data_uv[i].max(), data_uv[i].std()
        status = (
            "ok" if sd < 50 else
            "noisy" if sd < 100 else
            "very noisy — consider marking as bad"
        )
        print(f"  {ch:<8}  {mn:>10.1f}  {mx:>10.1f}  {sd:>10.1f}  {status}")


# Single-recording preprocessing
def run(p, s, timing, condition, bad_channels=None, skip_plots=False):
    """
    Preprocess one recording slot. Returns the filtered Raw object,
    or None if no CSV was found.
    """
    print(f"\n  {'─'*60}")
    print(f"  Preprocessing  |  P{p:02d}  |  Session {s}  |  {timing}  |  {condition}")

    # 1. Participant metadata (includes group)
    participant = load_participant(p)

    # 2. Print group banner — always visible
    print_group_banner(participant)

    # 3. Find CSV
    csv_path = find_csv(p, s, timing, condition)
    if csv_path is None:
        print(f"  [SKIP] No CSV found for this slot — continuing.")
        return None
    print(f"  CSV           : {csv_path}")

    # 4. Recording datetime
    rec_dt = parse_recording_datetime(csv_path)
    print(f"  Recording UTC : {rec_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    # 5. Build raw MNE object
    raw = build_raw(csv_path, participant, rec_dt)

    # 6. Mark bad channels
    if bad_channels:
        raw.info["bads"] = bad_channels
        print(f"  Bad channels  : {bad_channels}")

    # 7. Save raw.fif
    raw_fif, flt_fif = output_paths(p, s, timing, condition)
    os.makedirs(os.path.dirname(raw_fif), exist_ok=True)
    os.makedirs(os.path.dirname(flt_fif), exist_ok=True)
    raw.save(raw_fif, overwrite=True)
    print(f"  Saved raw     : {raw_fif}")

    group = participant.get("group")

    # 8. Quality check before filtering
    if not skip_plots:
        png_raw = raw_fif.replace(".fif", "_qc.png")
        plot_eeg_overview(
            raw,
            title=f"P{p:02d} S{s} {timing} {condition} — raw",
            save_path=png_raw,
            group=group,
        )

    # 9. Filtering
    print("\n  Filtering...")
    raw.notch_filter(freqs=NOTCH_FREQS, verbose=False)
    raw.filter(l_freq=BANDPASS[0], h_freq=BANDPASS[1], verbose=False)
    print(f"  Notch: {NOTCH_FREQS} Hz  |  Bandpass: {BANDPASS[0]}–{BANDPASS[1]} Hz")

    # 10. PSD check
    if not skip_plots:
        fig = raw.compute_psd(tmax=np.inf, fmax=128).plot(
            average=True, amplitude=False, picks="data", exclude="bads"
        )
        group_str = GROUP_LABELS.get((group or "").lower(), "")
        fig.suptitle(
            f"PSD after filtering — P{p:02d} S{s} {timing} {condition}"
            f"\n{group_str}",
            fontsize=12,
        )
        psd_path = flt_fif.replace(".fif", "_psd.png")
        fig.savefig(psd_path, dpi=150, bbox_inches="tight")
        print(f"  PSD saved     : {psd_path}")
        plt.show()

    # 11. Save filtered.fif
    raw.save(flt_fif, overwrite=True)
    print(f"  Saved filtered: {flt_fif}")

    # 12. Quality check after filtering
    if not skip_plots:
        png_flt = flt_fif.replace(".fif", "_qc.png")
        plot_eeg_overview(
            raw,
            title=f"P{p:02d} S{s} {timing} {condition} — filtered",
            save_path=png_flt,
            group=group,
        )

    print(f"\n  Done  →  {raw_fif}")
    print(f"          →  {flt_fif}")
    return raw


# Batch runner
def run_batch(participants, sessions, timings, conditions,
              bad_channels=None, skip_plots=False):
    total = len(participants) * len(sessions) * len(timings) * len(conditions)
    print(f"\n  ═══ BATCH MODE ═══")
    print(f"  Participants : {participants}")
    print(f"  Sessions     : {sessions}")
    print(f"  Timings      : {timings}")
    print(f"  Conditions   : {conditions}")
    print(f"  Total slots  : {total}")
    if skip_plots:
        print("  Plots        : skipped")

    # Show group assignments upfront
    try:
        df_p = pd.read_csv(PARTICIPANTS)
        df_p.columns = df_p.columns.str.strip().str.lower()
        if "group" in df_p.columns:
            print("\n  Group assignments:")
            for _, row in df_p.iterrows():
                pid   = int(row["id"])
                grp   = str(row.get("group", "?")).strip()
                label = GROUP_LABELS.get(grp.lower(), grp.upper())
                if pid in participants:
                    print(f"    P{pid:02d}  →  {label}")
    except Exception:
        pass

    results = []

    for p in participants:
        for s in sessions:
            for timing in timings:
                for condition in conditions:
                    label = f"P{p:02d} S{s} {timing} {condition}"
                    try:
                        raw    = run(p, s, timing, condition,
                                     bad_channels=bad_channels,
                                     skip_plots=skip_plots)
                        status = "skipped (no CSV)" if raw is None else "ok"
                    except Exception as exc:
                        status = f"ERROR: {exc}"
                        print(f"\n  [ERROR] {label}: {exc}")
                    results.append((label, status))

    # Summary
    ok      = [r for r in results if r[1] == "ok"]
    skipped = [r for r in results if "skipped" in r[1]]
    errors  = [r for r in results if r[1].startswith("ERROR")]

    print(f"\n  {'═'*60}")
    print(f"  BATCH SUMMARY  ({len(results)} slots)")
    print(f"  {'─'*60}")
    for label, status in results:
        icon = "✓" if status == "ok" else ("–" if "skipped" in status else "✗")
        print(f"  {icon}  {label:<40}  {status}")
    print(f"  {'─'*60}")
    print(f"  ✓ {len(ok)} processed  |  – {len(skipped)} skipped  |  ✗ {len(errors)} errors")
    print(f"  {'═'*60}\n")
    return results


# CLI
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="EEG preprocessing pipeline — single or batch mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single recording:
    python preprocess.py -p 3 -s 1 -t pre -c open_eyes

  All conditions for one participant/session/timing:
    python preprocess.py -p 3 -s 1 -t pre

  All timings + conditions for one participant/session:
    python preprocess.py -p 3 -s 1

  All sessions for one participant:
    python preprocess.py -p 3

  One session across ALL participants:
    python preprocess.py -s 1 -A

  Entire dataset:
    python preprocess.py
        """,
    )

    parser.add_argument("-p", "--participant", type=int, default=None)
    parser.add_argument("-s", "--session",     type=int, default=None)
    parser.add_argument("-A", "--all-participants", action="store_true")
    parser.add_argument("-t", "--timing",   default=None, choices=ALL_TIMINGS)
    parser.add_argument("-c", "--condition", default=None, choices=ALL_CONDITIONS)
    parser.add_argument("--bad-channels", nargs="*", default=None, metavar="CH")
    parser.add_argument("--skip-plots", action="store_true")

    args = parser.parse_args()

    if args.all_participants or args.participant is None:
        participants = all_participant_ids()
    else:
        participants = [args.participant]

    sessions   = [args.session]   if args.session   is not None else all_session_ids()
    timings    = [args.timing]    if args.timing     is not None else ALL_TIMINGS
    conditions = [args.condition] if args.condition  is not None else ALL_CONDITIONS

    is_single = (
        not args.all_participants
        and args.participant is not None
        and args.session     is not None
        and args.timing      is not None
        and args.condition   is not None
    )

    if is_single:
        run(
            p            = args.participant,
            s            = args.session,
            timing       = args.timing,
            condition    = args.condition,
            bad_channels = args.bad_channels,
            skip_plots   = args.skip_plots,
        )
    else:
        run_batch(
            participants = participants,
            sessions     = sessions,
            timings      = timings,
            conditions   = conditions,
            bad_channels = args.bad_channels,
            skip_plots   = args.skip_plots,
        )
