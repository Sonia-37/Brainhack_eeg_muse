"""
EEG Preprocessing Pipeline
===========================
Loads participant metadata from participants.csv, reads a muselsl CSV,
builds a properly annotated MNE Raw object, filters it, and saves both
raw.fif and filtered.fif into the correct folder from your study tree.

Usage
-----
  python preprocess.py --participant 3 --session 1 --timing pre --condition open_eyes
  python preprocess.py -p 3 -s 1 -t pre -c open_eyes --bad-channels AF7
  python preprocess.py -p 3 -s 1 -t pre -c open_eyes --skip-plots

participants.csv columns (one row per participant, edit before the study):
  id, his_id, first_name, sex, birthday, hand
  sex:  1=Male  2=Female  0=Unknown
  hand: 1=Right 2=Left    3=Both  0=Unknown
  birthday format: YYYY-MM-DD
"""

import os
import argparse
from datetime import datetime, timezone

import pandas as pd
import numpy as np
import mne
import matplotlib
import matplotlib.pyplot as plt

BASE_DIR     = "eeg_study"
PARTICIPANTS = "participants.csv"   # sits next to this script
CH_NAMES     = ["TP9", "AF7", "AF8", "TP10"]
SFREQ        = 256
EXPERIMENTER = "Zofia Sikorska"

NOTCH_FREQS  = [50.0, 100.0]       # Hz  — power-line noise
BANDPASS     = (0.5, 35.0)         # Hz  — l_freq, h_freq


def condition_path(p, s, timing, condition):
    return os.path.join(
        BASE_DIR,
        f"participant_{p:02d}",
        f"session_{s}",
        timing,
        condition,
    )


def find_csv(p, s, timing, condition):
    """
    Return the most recent .csv inside the csv/ subfolder for this slot.
    Raises a clear error if none is found.
    """
    csv_dir = os.path.join(condition_path(p, s, timing, condition), "csv")
    if not os.path.isdir(csv_dir):
        raise FileNotFoundError(f"CSV folder not found: {csv_dir}")

    csvs = sorted(
        [f for f in os.listdir(csv_dir) if f.endswith(".csv")],
        reverse=True,   # newest first (timestamp in filename)
    )
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in: {csv_dir}")

    if len(csvs) > 1:
        print(f"  [!] Multiple CSVs found — using the most recent: {csvs[0]}")
        print(f"      Others: {csvs[1:]}")

    return os.path.join(csv_dir, csvs[0])


def output_paths(p, s, timing, condition):
    """Return (raw_fif_path, filtered_fif_path) for this recording slot."""
    base    = condition_path(p, s, timing, condition)
    tag     = f"P{p:02d}_S{s}_{timing}_{condition}"
    raw_fif = os.path.join(base, "raw",      f"{tag}_raw.fif")
    flt_fif = os.path.join(base, "filtered", f"{tag}_filtered_raw.fif")
    return raw_fif, flt_fif



def load_participant(p):
    """
    Read participants.csv and return the row for participant p as a dict.
    Converts types so MNE accepts them directly.
    """
    if not os.path.isfile(PARTICIPANTS):
        raise FileNotFoundError(
            f"'{PARTICIPANTS}' not found. Create it with columns:\n"
            "  id, his_id, first_name, sex, birthday, hand"
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

    return {
        "id":       int(row["id"]),
        "his_id":   str(row["his_id"]).strip(),
        "sex":      int(row["sex"]),
        "birthday": birthday,
        "hand":     int(row["hand"]),
    }



def build_raw(csv_path, participant, rec_datetime):
    """
    Read a muselsl CSV, create an MNE RawArray with full metadata, and
    apply the standard 10-20 montage.

    Parameters
    ----------
    csv_path    : str            — path to the muselsl .csv file
    participant : dict           — output of load_participant()
    rec_datetime: datetime       — recording start (UTC) parsed from the CSV
                                   timestamps or passed explicitly

    Returns
    -------
    mne.io.RawArray
    """
    df = pd.read_csv(csv_path)

    # Validate expected channels are present
    missing = [c for c in CH_NAMES if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV is missing expected channels: {missing}\n"
            f"Columns found: {list(df.columns)}"
        )

    data = df[CH_NAMES].values.T * 1e-6      # µV → V, shape: (4, n_samples)

    info = mne.create_info(ch_names=CH_NAMES, sfreq=SFREQ, ch_types="eeg")
    info["experimenter"] = EXPERIMENTER
    info["subject_info"] = participant
    info.set_meas_date(rec_datetime)

    raw = mne.io.RawArray(data, info, verbose=False)

    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, verbose=False)

    return raw


def parse_recording_datetime(csv_path):
    """
    Extract UTC recording start from the muselsl CSV timestamps column.
    Falls back to file modification time if the column is absent.
    """
    df = pd.read_csv(csv_path, nrows=5)

    # muselsl writes a 'timestamps' column in Unix time
    if "timestamps" in df.columns:
        ts = float(df["timestamps"].iloc[0])
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    # fallback: file modification time
    mtime = os.path.getmtime(csv_path)
    print("  [!] No 'timestamps' column found — using file modification time as recording date.")
    return datetime.fromtimestamp(mtime, tz=timezone.utc)



def plot_eeg_overview(raw, title="EEG Overview", segment_duration=10, save_path=None):
    """
    Static multi-panel quality check — works in any environment.

    Panels:
      1..n  Raw traces per channel (first `segment_duration` seconds).
      n+1   Per-channel std bar chart — colour coded for noise level.
    """
    sfreq    = int(raw.info["sfreq"])
    ch_names = raw.ch_names
    n_ch     = len(ch_names)
    colors   = ["purple", "mediumseagreen", "dodgerblue", "tomato"]

    n_samples       = min(int(segment_duration * sfreq), raw.n_times)
    data, times     = raw[:, :n_samples]
    data_uv         = data * 1e6

    fig, axes = plt.subplots(
        n_ch + 1, 1,
        figsize=(14, 3 * n_ch + 3),
        gridspec_kw={"height_ratios": [2] * n_ch + [1.5]},
    )
    fig.suptitle(title, fontsize=14, weight="bold", y=1.01)

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
        color = "red" if std_val > 100 else ("orange" if std_val > 50 else None)
        if color:
            bar.set_facecolor(color)
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

    # Console stats table
    print(f"\n  {'Channel':<8}  {'Min (µV)':>10}  {'Max (µV)':>10}  {'Std (µV)':>10}  Status")
    for i, ch in enumerate(ch_names):
        mn, mx, sd = data_uv[i].min(), data_uv[i].max(), data_uv[i].std()
        status = (
            "ok" if sd < 50 else
            "noisy" if sd < 100 else
            "very noisy — consider marking as bad"
        )
        print(f"  {ch:<8}  {mn:>10.1f}  {mx:>10.1f}  {sd:>10.1f}  {status}")



def run(p, s, timing, condition, bad_channels=None, skip_plots=False):
    print(f"  Preprocessing  |  P{p:02d}  |  Session {s}  |  {timing}  |  {condition}")

    # 1. Load participant metadata
    participant = load_participant(p)
    print(f"  Participant   : {participant['his_id']}  (id={participant['id']})")

    # 2. Find CSV
    csv_path = find_csv(p, s, timing, condition)
    print(f"  CSV           : {csv_path}")

    # 3. Parse recording datetime
    rec_dt = parse_recording_datetime(csv_path)
    print(f"  Recording UTC : {rec_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    # 4. Build raw MNE object
    raw = build_raw(csv_path, participant, rec_dt)

    # 5. Mark bad channels if supplied
    if bad_channels:
        raw.info["bads"] = bad_channels
        print(f"  Bad channels  : {bad_channels}")

    # 6. Save raw.fif
    raw_fif, flt_fif = output_paths(p, s, timing, condition)
    raw.save(raw_fif, overwrite=True)
    print(f"  Saved raw     : {raw_fif}")

    # 7. Quality check before filtering
    if not skip_plots:
        png_raw = raw_fif.replace(".fif", "_qc.png")
        plot_eeg_overview(
            raw,
            title=f"P{p:02d} S{s} {timing} {condition} — raw",
            save_path=png_raw,
        )

    # 8. Filtering
    print("\n  Filtering...")
    raw.notch_filter(freqs=NOTCH_FREQS, verbose=False)
    raw.filter(l_freq=BANDPASS[0], h_freq=BANDPASS[1], verbose=False)
    print(f"  Notch: {NOTCH_FREQS} Hz  |  Bandpass: {BANDPASS[0]}–{BANDPASS[1]} Hz")

    # 9. PSD check
    if not skip_plots:
        fig = raw.compute_psd(tmax=np.inf, fmax=128).plot(
            average=True, amplitude=False, picks="data", exclude="bads"
        )
        fig.suptitle(f"PSD after filtering — P{p:02d} S{s} {timing} {condition}", fontsize=12)
        psd_path = flt_fif.replace(".fif", "_psd.png")
        fig.savefig(psd_path, dpi=150, bbox_inches="tight")
        print(f"  PSD saved     : {psd_path}")
        plt.show()

    # 10. Save filtered.fif
    raw.save(flt_fif, overwrite=True)
    print(f"  Saved filtered: {flt_fif}")

    # 11. Quality check after filtering
    if not skip_plots:
        png_flt = flt_fif.replace(".fif", "_qc.png")
        plot_eeg_overview(
            raw,
            title=f"P{p:02d} S{s} {timing} {condition} — filtered",
            save_path=png_flt,
        )

    print(f"\n  Done. Files written:")
    print(f"    {raw_fif}")
    print(f"    {flt_fif}\n")

    return raw



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EEG preprocessing pipeline")
    parser.add_argument("-p", "--participant", type=int, required=True,
                        help="Participant number, e.g. 3")
    parser.add_argument("-s", "--session",     type=int, required=True,
                        help="Session number (1–3)")
    parser.add_argument("-t", "--timing",      required=True,
                        choices=["pre", "post"],
                        help="pre or post")
    parser.add_argument("-c", "--condition",   required=True,
                        choices=["open_eyes", "closed_eyes"],
                        help="open_eyes or closed_eyes")
    parser.add_argument("--bad-channels",      nargs="*", default=None,
                        metavar="CH",
                        help="Channels to mark as bad, e.g. --bad-channels AF7 TP9")
    parser.add_argument("--skip-plots",        action="store_true",
                        help="Skip all plots (useful for batch runs)")

    args = parser.parse_args()

    run(
        p             = args.participant,
        s             = args.session,
        timing        = args.timing,
        condition     = args.condition,
        bad_channels  = args.bad_channels,
        skip_plots    = args.skip_plots,
    )
