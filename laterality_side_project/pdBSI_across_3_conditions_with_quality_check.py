#!/usr/bin/env python3
"""
pdBSI Analysis — Muse 2 EEG Data
=================================
Pipeline:
  1. Auto-discover all participants in data_dir (files named <ID>_<condition>.zip/.csv.gz)
  2. Quality control per subject × condition:
       - Remove rows where any band column is NaN or negative (invalid sensor readings)
       - Remove rows where power values are extreme outliers (> 3 SD from the mean)
       - Print how many rows were removed and the percentage of data lost
  3. Plot the cleaned time series for every subject × condition × band
  4. Compute pdBSI on the cleaned data and plot the group-level dot plot

pdBSI formula:
  ((Right - Left) / (Right + Left)) * 100
  Positive = right hemisphere dominance
  Negative = left hemisphere dominance
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import re

# ── Global configuration ──────────────────────────────────────────────────────

FREQUENCY_BANDS  = ['Delta', 'Theta', 'Alpha', 'Beta']
CONDITIONS       = ['rest', 'language', 'emotional']
ELECTRODE_PAIR   = ('TP9', 'TP10')

# Colour per condition (used in every plot)
CONDITION_COLORS = {
    'rest':      '#4C72B0',
    'language':  '#DD8452',
    'emotional': '#55A868',
}

# Outlier rejection threshold: rows where ANY band channel deviates more than
# this many SDs from its own mean will be marked as bad and removed.
OUTLIER_SD_THRESHOLD = 3.0

# Data directory — adjust to your local path
DATA_DIR = Path("data")


# ── Helper: compression detection ────────────────────────────────────────────

def guess_compression(file):
    """Return the pandas compression string based on the file suffix."""
    s = str(file).lower()
    if s.endswith(".gz"):  return "gzip"
    if s.endswith(".zip"): return "zip"
    return None


# ── Helper: participant discovery ────────────────────────────────────────────

def find_participants(data_dir):
    """
    Scan data_dir for files matching <ID>_<condition>.(zip|csv.gz|csv).
    Returns a dict  {participant_id: {condition: Path, ...}, ...}
    Only participants that have ALL three conditions are kept.
    """
    pattern = re.compile(
        r'^(.+)_(rest|language|emotional)\.(csv\.gz|zip|csv)$',
        re.IGNORECASE
    )
    found = {}
    for f in sorted(data_dir.iterdir()):
        m = pattern.match(f.name)
        if m:
            pid       = m.group(1)
            condition = m.group(2).lower()
            found.setdefault(pid, {})[condition] = f

    complete   = {p: c for p, c in found.items()
                  if all(cond in c for cond in CONDITIONS)}
    incomplete = set(found) - set(complete)
    if incomplete:
        print(f"⚠  Skipping participants with missing files: {sorted(incomplete)}")

    return complete


# ── Step 2: Quality control ───────────────────────────────────────────────────

def load_and_clean(csv_file):
    """
    Load a Mind Monitor CSV, run quality control, and return the cleaned
    DataFrame together with a short QC report dict.

    QC steps
    --------
    1. Parse TimeStamp; drop rows where timestamp is missing or invalid
       (these are Mind Monitor event-marker rows, not EEG samples).
    2. Convert every band × electrode column to numeric;
       rows that are NaN after conversion are dropped.
    3. Drop rows where any relevant band-power value is negative
       (negative power is physically meaningless — sensor artefact).
    4. Drop rows where any relevant band-power value deviates more than
       OUTLIER_SD_THRESHOLD standard deviations from that column's mean
       (large transient artefacts / movement spikes).

    Returns
    -------
    df_clean : pd.DataFrame   — cleaned data, TimeStamp as index
    qc       : dict           — keys: total_rows, kept_rows, removed_rows,
                                pct_removed, removal_breakdown
    """
    left_elec, right_elec = ELECTRODE_PAIR
    band_cols = []
    for band in FREQUENCY_BANDS:
        band_cols += [f"{band}_{left_elec}", f"{band}_{right_elec}"]

    # ── Load ──────────────────────────────────────────────────────────────────
    df = pd.read_csv(csv_file, compression=guess_compression(csv_file))
    total_rows_raw = len(df)

    # ── Step 1: valid timestamp ───────────────────────────────────────────────
    df['TimeStamp'] = pd.to_datetime(df['TimeStamp'], errors='coerce')
    bad_ts  = df['TimeStamp'].isna().sum()
    df      = df[df['TimeStamp'].notna()].copy()
    total_rows = len(df)   # rows with a valid timestamp

    # ── Step 2: coerce band columns to numeric ────────────────────────────────
    existing_cols = [c for c in band_cols if c in df.columns]
    for col in existing_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    bad_numeric = df[existing_cols].isna().any(axis=1).sum()
    df = df.dropna(subset=existing_cols).copy()

    # ── Step 3: remove negative-power rows ───────────────────────────────────
    neg_mask  = (df[existing_cols] < 0).any(axis=1)
    bad_neg   = neg_mask.sum()
    df        = df[~neg_mask].copy()

    # ── Step 4: outlier rejection per column (> N SD from mean) ──────────────
    outlier_mask = pd.Series(False, index=df.index)
    for col in existing_cols:
        col_mean = df[col].mean()
        col_sd   = df[col].std()
        outlier_mask |= (df[col] - col_mean).abs() > OUTLIER_SD_THRESHOLD * col_sd

    bad_outlier = outlier_mask.sum()
    df_clean    = df[~outlier_mask].copy()

    # ── QC report ─────────────────────────────────────────────────────────────
    kept         = len(df_clean)
    total_removed = total_rows - kept
    pct_removed  = 100.0 * total_removed / total_rows if total_rows > 0 else np.nan

    qc = {
        'file':               Path(csv_file).name,
        'total_rows':         total_rows,
        'kept_rows':          kept,
        'removed_rows':       total_removed,
        'pct_removed':        pct_removed,
        'breakdown': {
            'bad_timestamp':  bad_ts,
            'bad_numeric':    bad_numeric,
            'negative_power': bad_neg,
            'outliers':       bad_outlier,
        }
    }

    return df_clean, qc


def print_qc_report(participant, condition, qc):
    """Pretty-print the QC summary for one file."""
    b = qc['breakdown']
    print(
        f"  [{participant} | {condition.upper():>10}]  "
        f"{qc['file']}  →  "
        f"{qc['kept_rows']:>6} / {qc['total_rows']:>6} rows kept  "
        f"({qc['pct_removed']:.1f}% removed)"
    )
    print(
        f"      └─ bad timestamp: {b['bad_timestamp']}  |  "
        f"non-numeric: {b['bad_numeric']}  |  "
        f"negative power: {b['negative_power']}  |  "
        f"outliers (>{OUTLIER_SD_THRESHOLD}σ): {b['outliers']}"
    )


# ── Step 3: Plot cleaned time series ─────────────────────────────────────────

def plot_timeseries(participant, cond_dataframes, data_dir):
    """
    Plot the cleaned EEG power time series for one participant.

    Layout: rows = frequency bands, columns = conditions.
    Both left (TP9) and right (TP10) traces are drawn per subplot so you
    can see the raw asymmetry before the single pdBSI number is computed.
    """
    left_elec, right_elec = ELECTRODE_PAIR
    n_bands = len(FREQUENCY_BANDS)
    n_conds = len(CONDITIONS)

    fig, axes = plt.subplots(
        n_bands, n_conds,
        figsize=(5.5 * n_conds, 2.5 * n_bands),
        sharey=False,     # bands have very different power scales
        sharex=False,
        squeeze=False,
    )

    for col, condition in enumerate(CONDITIONS):
        df = cond_dataframes.get(condition)

        for row, band in enumerate(FREQUENCY_BANDS):
            ax        = axes[row][col]
            left_col  = f"{band}_{left_elec}"
            right_col = f"{band}_{right_elec}"

            if df is not None and left_col in df.columns and right_col in df.columns:
                # Plot left and right power traces
                ax.plot(df['TimeStamp'], df[left_col],
                        linewidth=0.6, alpha=0.8, color='steelblue',
                        label=left_elec)
                ax.plot(df['TimeStamp'], df[right_col],
                        linewidth=0.6, alpha=0.8, color='tomato',
                        label=right_elec)
            else:
                ax.text(0.5, 0.5, 'No data', transform=ax.transAxes,
                        ha='center', va='center', color='gray', fontsize=9)

            ax.grid(True, alpha=0.2)
            ax.tick_params(axis='x', labelsize=7, rotation=30)
            ax.tick_params(axis='y', labelsize=7)

            # Row labels (band names) on left column only
            if col == 0:
                ax.set_ylabel(f"{band}\n(µV²/Hz)", fontsize=9, fontweight='bold')

            # Column titles (conditions) on top row only
            if row == 0:
                ax.set_title(
                    condition.capitalize(), fontsize=11, fontweight='bold',
                    color=CONDITION_COLORS[condition]
                )

            # Legend once (top-right subplot)
            if row == 0 and col == n_conds - 1:
                ax.legend(fontsize=7, loc='upper right', framealpha=0.6)

    fig.suptitle(
        f"Cleaned EEG Power Time Series  —  Participant: {participant}  "
        f"(TP9 = left, TP10 = right)\n"
        f"Outlier threshold: >{OUTLIER_SD_THRESHOLD}σ removed",
        fontsize=12, fontweight='bold',
    )
    plt.tight_layout()
    out = data_dir / f"{participant}_timeseries_cleaned.png"
    plt.savefig(out, dpi=130, bbox_inches='tight')
    plt.show()
    print(f"  Time-series plot saved: {out}")


# ── pdBSI computation ─────────────────────────────────────────────────────────

def compute_pdbsi(df):
    """
    Given a cleaned DataFrame for one condition, compute one pdBSI value
    per frequency band.

    Strategy: average the left and right power across the entire (cleaned)
    recording first, then apply the pdBSI formula once.  This is more
    robust than computing pdBSI sample-by-sample and then averaging,
    because the latter is sensitive to samples where the denominator
    approaches zero.

    Returns
    -------
    dict  {band: {'mean': float}}
    """
    left_elec, right_elec = ELECTRODE_PAIR
    band_stats = {}

    for band in FREQUENCY_BANDS:
        left_col  = f"{band}_{left_elec}"
        right_col = f"{band}_{right_elec}"

        if left_col not in df.columns or right_col not in df.columns:
            continue

        mean_left  = np.nanmean(pd.to_numeric(df[left_col],  errors='coerce'))
        mean_right = np.nanmean(pd.to_numeric(df[right_col], errors='coerce'))

        denom = mean_left + mean_right
        pdBSI = ((mean_right - mean_left) / denom) * 100 if denom != 0 else np.nan

        band_stats[band] = {'mean': pdBSI}

    return band_stats


# ── Step 4: Group-level dot plot ──────────────────────────────────────────────

def plot_group_dots(group_data, data_dir):
    """
    Group-level dot plot of pdBSI across participants.

    Layout: one subplot per frequency band (columns).
    Within each subplot: x-axis = conditions, dots = individual participants,
    thick horizontal line = group mean, error bars = ±1 SD.

    Positive pdBSI → right hemisphere dominance (bar above zero line)
    Negative pdBSI → left  hemisphere dominance (bar below zero line)
    """
    participants = list(group_data.keys())
    n            = len(participants)
    n_bands      = len(FREQUENCY_BANDS)

    fig, axes = plt.subplots(
        1, n_bands,
        figsize=(4.2 * n_bands, 5.5),
        sharey=False,
    )
    if n_bands == 1:
        axes = [axes]

    condition_x = {cond: i for i, cond in enumerate(CONDITIONS)}

    for col, band in enumerate(FREQUENCY_BANDS):
        ax = axes[col]

        for condition in CONDITIONS:
            xpos = condition_x[condition]

            # Collect one pdBSI value per participant for this band × condition
            vals = np.array([
                group_data[p].get(condition, {}).get(band, {}).get('mean', np.nan)
                for p in participants
            ], dtype=float)
            valid = vals[~np.isnan(vals)]

            if len(valid) == 0:
                continue

            # Jitter individual dots so they don't overlap
            jitter = np.linspace(-0.12, 0.12, len(valid)) if len(valid) > 1 else [0.0]
            ax.scatter(
                [xpos + j for j in jitter], valid,
                color=CONDITION_COLORS[condition],
                s=65, zorder=4, alpha=0.85,
                edgecolors='white', linewidths=0.7,
            )

            # Group mean line
            m  = np.nanmean(valid)
            sd = np.nanstd(valid)
            ax.plot(
                [xpos - 0.18, xpos + 0.18], [m, m],
                color=CONDITION_COLORS[condition],
                linewidth=2.8, zorder=5, solid_capstyle='round',
            )

            # ±1 SD error bar
            ax.errorbar(
                xpos, m, yerr=sd,
                fmt='none',
                ecolor=CONDITION_COLORS[condition],
                elinewidth=1.8, capsize=5, capthick=1.8,
                zorder=5,
            )

        # Zero reference line
        ax.axhline(y=0, color='black', linewidth=0.9, linestyle='--', alpha=0.5)

        ax.set_xticks(list(condition_x.values()))
        ax.set_xticklabels([c.capitalize() for c in CONDITIONS], fontsize=10)
        ax.set_xlim(-0.55, len(CONDITIONS) - 0.45)
        ax.set_title(band, fontsize=12, fontweight='bold')
        ax.grid(True, axis='y', alpha=0.25, linestyle=':')

        if col == 0:
            ax.set_ylabel('pdBSI (%)\n← left dominant  |  right dominant →',
                          fontsize=10)

    # Shared legend
    legend_handles = [
        plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor=CONDITION_COLORS[c],
                   markersize=9, label=c.capitalize())
        for c in CONDITIONS
    ]
    fig.legend(
        handles=legend_handles, title='Condition',
        loc='upper center', ncol=len(CONDITIONS),
        fontsize=10, title_fontsize=10,
        bbox_to_anchor=(0.5, 1.03),
    )

    fig.suptitle(
        f"Group-level pdBSI — TP9-TP10  |  N={n} participants\n"
        f"Line = mean  ·  bars = ±SD  ·  dots = individual participants",
        fontsize=12, fontweight='bold', y=1.09,
    )

    plt.tight_layout()
    out = data_dir / 'group_pdBSI_dotplot.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    print(f"  Group dot plot saved: {out}")


# ── Summary table ─────────────────────────────────────────────────────────────

def build_summary_table(group_data):
    """Return a tidy DataFrame: Participant × Condition × Band → pdBSI."""
    rows = []
    for participant, all_results in group_data.items():
        for condition, bands_data in all_results.items():
            for band, stats in bands_data.items():
                rows.append({
                    'Participant':    participant,
                    'Condition':      condition.capitalize(),
                    'Frequency_Band': band,
                    'pdBSI':          round(stats['mean'], 3),
                })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

participants = find_participants(DATA_DIR)

if not participants:
    print("❌  No complete participant datasets found. "
          "Check filenames and directory path.")
else:
    print(f"✔  Found {len(participants)} participant(s): "
          f"{sorted(participants.keys())}\n")
    print("=" * 70)

    group_data = {}   # {participant: {condition: {band: {'mean': float}}}}

    for participant, cond_files in sorted(participants.items()):

        print(f"\n{'='*70}")
        print(f"  PARTICIPANT: {participant}")
        print(f"{'='*70}")

        # ── Step 2: QC — load, clean, report removed rows ─────────────────
        print("\n  ── Quality Control ─────────────────────────────────────────")
        cond_dataframes = {}   # cleaned DataFrames, keyed by condition

        for condition in CONDITIONS:
            df_clean, qc = load_and_clean(cond_files[condition])
            print_qc_report(participant, condition, qc)
            cond_dataframes[condition] = df_clean

        # ── Step 3: Plot cleaned time series ─────────────────────────────
        print(f"\n  ── Cleaned Time Series Plot ────────────────────────────────")
        plot_timeseries(participant, cond_dataframes, DATA_DIR)

        # ── pdBSI computation (on cleaned data) ───────────────────────────
        all_results = {}
        print(f"\n  ── pdBSI Values (computed on cleaned data) ─────────────────")
        for condition in CONDITIONS:
            df_clean = cond_dataframes[condition]
            band_stats = compute_pdbsi(df_clean)
            all_results[condition] = band_stats
            for band, stats in band_stats.items():
                print(f"    {condition:>10} | {band:<6}: {stats['mean']:+.3f}%")

        group_data[participant] = all_results

    # ── Summary table ─────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  SUMMARY TABLE")
    print(f"{'='*70}")
    summary = build_summary_table(group_data)
    print(summary.to_string(index=False))

    out_csv = DATA_DIR / 'pdBSI_summary_cleaned.csv'
    summary.to_csv(out_csv, index=False)
    print(f"\n  Summary saved: {out_csv}")

    # ── Step 4: Group-level dot plot ──────────────────────────────────────
    print(f"\n{'='*70}")
    print("  GROUP-LEVEL DOT PLOT")
    print(f"{'='*70}")
    plot_group_dots(group_data, DATA_DIR)
