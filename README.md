# Step-by-Step Guide for EEG Setup with Muse

## Table of Contents

1. [Environment Setup](#1-environment)
2. [Connecting to the Muse and Checking the Data](#2-connecting-to-the-muse-and-checking-the-data)
3. [Automating Your Experiment](#3-automating-your-experiment-eeg_setuppy)
4. [Cleaning and Processing the Data](#4-cleaning-and-processing-the-data-preprocesspy)
5. [Analyzing the Results](#5-analyzing-the-results-analysisipynb)
   - [Sections of Notebook](#sections-12--initialisation)
   - [Metric Glossary and How to Interpret Results](#metric-glossary-and-how-to-interpret-results)
   - [Statistical Results — How to Read Them](#statistical-results--how-to-read-them)
   - [Output Files](#output-files)

## 1. Environment

Before creating the environment, ensure you have **Miniconda** or **Anaconda** installed on your computer. If you don't have it here's the link for installation: [Miniconda](https://www.anaconda.com/docs/getting-started/miniconda/install/overview)

*Note: This tutorial is written for Linux systems. Windows and macOS setups may differ slightly. If you are using Windows or macOS, you may need to adapt these terminal commands.*

You should have access to the `environment.yml` file. Open your terminal, navigate to the folder containing this file, and run the following commands sequentially:

```bash
conda env create -f environment.yml
conda activate muse
python -m ipykernel install --user --name=muse --display-name="Python (muse)"
```

In case you encounter any issues with the `.yml` file, you can create the environment manually by running these commands:

```bash
conda create --name muse -c conda-forge -c defaults python=3.10 ipykernel pandas numpy pywavelets matplotlib scipy pingouin pip -y
conda activate muse
pip install mne muselsl fooof antropy
python -m ipykernel install --user --name=muse --display-name="Python (muse)"
```

---

## 2. Connecting to the Muse and Checking the Data

### 1. Putting on the Muse headband
If you are unsure how to properly wear the device, please watch this [quick video guide](https://youtu.be/oRFiHhm-mQc?si=Li7c_tmKWqrp1KL7).

### 2. Connecting to the Muse
Turn on the Muse device. Check your computer's Bluetooth settings; you should see the device appear, but **do not** try to pair it directly yet.

1. Open the Jupyter Notebook script [Checking eeg](eeg_check.ipynb).
2. Run the following command in a notebook cell to find your device's address:
   ```bash
   !bluetoothctl devices | grep -i muse
   ```
   *This will return the MAC address for your Muse next to the word 'Device' (e.g., `00:55:DA:BB:5D:FA`).*

3. Open a **separate terminal window** and start the stream using your specific address:
   ```bash
   muselsl stream --address <YOUR_DEVICE_ADDRESS>
   ```
   *This command streams data from your EEG device to your computer, but it does not record it yet.*

Because the Muse may not always have a perfect connection across all channels initially, you must verify the signal quality for each participant before the actual experiment. We will start with a 10-second test recording.

### 3. Recording a Test Sample
Ask your participant to remain still. Then, run the following command in your notebook:

```bash
!muselsl record --duration 10
```

This will generate a `.csv` file that starts with `EEG`. 

Next, update the `path = " "` variable in your script with the path to this newly generated `.csv` file. Run the rest of the script until the plot is generated. 

**Analyzing the Plot:**
* **Good Data:** If all channels fall within the range of $-100 \mu V$ to $100 \mu V$, the data quality is good, and you can proceed to the actual recording.
* **Bad Data:** If any channel falls outside this range (like **TP9** in the example image below), you must improve the connectivity for that specific electrode.

![alt text](/images/image.png)

### 4. How to Improve Connectivity
If the signal is poor, try the following troubleshooting steps:
- Use a skin preparation gel ([such as Nuprep abrasive gel](https://allegro.pl/produkt/zel-scierny-nuprep-tuba-114g-1-szt-736bf951-532c-42de-9807-d48a9f85aeaa?offerId=10963802995&dd_referrer=)) and wipe the area with alcohol pads.
- Lightly wet the electrodes using a drop of water on your finger.
- Tighten the headband to ensure flush contact with the skin.
- Make sure all hair is moved completely out of the way of the electrodes.

**Repeat step 3 (Recording a Test Sample)** until all electrodes show a clean signal within the correct range.

---

## 3. Automating Your Experiment [eeg_setup.py](eeg_setup.py) 

The `eeg_setup.py` script is designed to handle complex folder creation and manage recording sessions for multiple participants. It ensures that data is never lost and is always saved in a standardized format.

### What does this script actually do?
It acts as both an **Organizer** and a **Recording Assistant**:

1.  **The Organizer:** It builds a deep, perfectly organized folder tree for your entire study. It creates dedicated sub-folders for every participant, session, and experimental condition.
    * **Folder Structure:** It creates a hierarchy like this: `eeg_study/participant_01/session_1/pre/open_eyes/csv/`.
    * **Placeholders:** It also creates empty `raw/` and `filtered/` folders within each condition to hold your processed data later.
2.  **The Assistant:** When you record, it asks simple questions (e.g., "Which participant?", "Which session?"). It automatically:
    * **Checks Groups:** It reads `participants.csv` to tell you if the person is in the **Control** or **Research** group.
    * **Labels Files:** It names the file with a unique timestamp: `P01_S1_pre_open_eyes_20240415_1030.csv`.
    * **Manages Logic:** It can queue up multiple recordings (e.g., "Record pre-task open eyes, then closed eyes") so you don't have to restart the script between every 2-minute trial.

### How to use it:

Open your terminal, ensure you are in the same folder as the script, and follow these steps:

**1. Prepare your participant list:**
Ensure you have a `participants.csv` file in the same directory. The script uses the `group` column to help you track your experimental conditions:
```csv
id, his_id, first_name, sex, birthday, hand, group
1, P01, Alice, 2, 1995-05-14, 1, experimental
2, P02, Bob, 1, 1998-11-20, 1, control
```

**2. Initialize the folders (Do this once):**
```bash
python eeg_setup.py --setup-only
```
*This instantly generates the `eeg_study/` folder tree for all participants and sessions.*

**3. Run an actual recording session:**
```bash
python eeg_setup.py
```
* The script will display a summary of your participants and their assigned groups.
* It will ask for the **Participant Number** and **Session Number**.
* **Choose Timing:** Select if you are recording `pre`, `post`, or `both`.
* **Choose Condition:** Select `open_eyes`, `closed_eyes`, or a sequence of both.
* The script will then guide you through each recording. Press **ENTER** when the participant is ready to start the `muselsl` stream.

### What YOU can change:
Open `eeg_setup.py` in a text editor to adjust the experiment parameters at the top:

* **`N_PARTICIPANTS = 5`**: The total number of people in your study.
* **`N_SESSIONS = 3`**: How many times each person returns for a session.
* **`RECORDING_SECS = 120`**: The duration of each EEG recording (in seconds).
* **`GROUP_LABELS`**: You can change the descriptions for "control" and "research" to match your specific study goals.

---

## 4. Cleaning and Processing the Data [preprocess.py](preprocess.py)

After recording, you are left with raw `.csv` files. These files contain raw voltage but lack the metadata and cleanliness required for scientific study. The `preprocess.py` script acts as your automated data cleaner and converter.

### What does this script actually do?
1.  **Metadata Injection:** It merges the EEG data with your `participants.csv`. It embeds the participant's ID, sex, age, and handedness directly into the file header.
2.  **Conversion to Standard Format:** It transforms `.csv` files into `.fif` files. This is the professional standard for EEG, allowing the data to be opened in any major analysis toolbox (MNE, EEGLAB, etc.).
3.  **Group-Aware Quality Control (QC):** * It generates visual plots of the brainwaves. 
    * **Smart Colors:** Channels are colored based on the participant's group (**Blue tones for Control**, **Warm tones for Research**) so you can instantly tell them apart during review.
    * **Noise Detection:** It calculates the Standard Deviation ($SD$) for every channel. It highlights noisy sensors in **Orange** ($>50 \mu V$) or **Red** ($>100 \mu V$) to warn you of bad data.
4.  **Digital Filtering (The Cleaning):**
    * **Notch Filter:** Targets $50$ Hz and $100$ Hz to remove the electrical hum from the walls.
    * **Bandpass Filter:** Removes slow-moving artifacts (sweat/drifts) and fast-moving noise (muscle clenches), keeping only the clean brainwave spectrum ($0.5$–$35$ Hz).
5.  **Power Spectral Density (PSD):** It creates a frequency graph showing the "strength" of different brainwaves (Alpha, Beta, etc.) to verify the filters worked correctly.

### How to use it:

This script is highly flexible. You can process one specific file or your entire study at once.

**1. Process a single trial:**
```bash
python preprocess.py -p 1 -s 1 -t pre -c open_eyes
```

**2. Handle "Bad" sensors:**
If you know the `AF7` electrode was loose during a specific recording, tell the script to ignore it:
```bash
python preprocess.py -p 1 -s 1 -t pre -c open_eyes --bad-channels AF7
```

**3. Batch Processing (The Power User move):**
You don't have to run the script 100 times. It can detect what files you have:
* **Process all sessions for Participant 1:** `python preprocess.py -p 1`
* **Process Session 1 for EVERYONE:** `python preprocess.py -s 1 -A`
* **Process the ENTIRE dataset:** `python preprocess.py`

### What YOU can change:
Near the top of `preprocess.py`, you can customize the "cleaning" rules:

* **`EXPERIMENTER`**: Put your name here so it's saved in the file metadata.
* **`NOTCH_FREQS = [50.0, 100.0]`**: If you are in the USA or Canada, change `50.0` to `60.0`.
* **`BANDPASS = (0.5, 35.0)`**: If you want to look at high-frequency "Gamma" waves, you might increase the `35.0` limit to `45.0` or `50.0`.

---

## 5. Analyzing the Results [analysis.ipynb](analysis.ipynb)

### Sections 1–2 — Initialisation

Library imports, creation of output folders (`results/`, `results/figures/`), and configuration of signal parameters (sampling rate, frequency bands, FOOOF settings).

---

### Section 3 — Loading Data

The `discover_recordings()` function walks the folder tree and builds a list of all recordings. Each recording is described by:
- path to the CSV file
- participant and session number
- timing (`pre` / `post`)
- condition (`open_eyes` / `closed_eyes`)
- group assignment (read from `participants.csv`)

---

### Section 4 — Computing the Power Spectrum (PSD)

The **Morlet Continuous Wavelet Transform (CWT)** converts the raw time-domain signal into a 2D power matrix `(frequency × time)`. Averaging over time yields the **mean PSD** — the typical frequency profile of the entire recording.

Why wavelets instead of FFT?
- FFT provides a global spectral picture but loses information about *when* specific frequencies occurred.
- CWT produces a time-resolved power estimate (spectrogram), making it easier to detect movement artefacts.

---

### Section 5 — EEG Metrics

Computes: band power (delta, theta, alpha, beta), relative band power, DAR, DTABR, pdBSI, and FOOOF parameters.  
Full description → [Metric Glossary](#metric-glossary-and-how-to-interpret-results).

---

### Section 6 — Signal Complexity Measures

Hjorth parameters and three entropy measures (spectral, sample, permutation).  
Full description → [Metric Glossary](#metric-glossary-and-how-to-interpret-results).

---

### Sections 7–8 — Processing and Saving

The `process_file()` function runs the full pipeline for one recording and returns a dictionary of metrics. Results are saved to:
- `results/per_recording_metrics.csv` — all scalar metrics
- `results/<label>_mean_psd.csv` — mean PSD for each recording (used for plots)

---

### Section 9 — Results Overview

A table of all metrics with a colour gradient (red = higher DAR/DTABR/pdBSI values). Group-level aggregates by session, timing, and group.

---

### Sections 10–11 — Visualisations

| Plot | What it shows |
|---|---|
| **Spectrogram** | Power over time and frequency (2D heatmap) |
| **Mean PSD** | Frequency profile of the recording (log scale) |
| **Band ratio bars** | DAR and DTABR values across all recordings |
| **pdBSI bars** | Left/right hemisphere asymmetry |
| **FOOOF fit** | 1/f model fit with detected oscillatory peaks |
| **Hjorth bars** | Activity, mobility, complexity for TP9 and TP10 |
| **Entropy bars** | Three entropy measures for TP9 and TP10 |
| **Relative power** | Stacked bars of relative band power |
| **Group timeline (dot plot)** | Participant trajectories across 4 timepoints (S1pre → S1post → S2pre → S2post) |
| **Boxplot panel** | Distributions at each timepoint split by group |

---

### Section 12 — Statistical Analysis

The statistical pipeline consists of five steps:

| Step | What it does |
|---|---|
| **12b** | Merges EEG results with demographic data |
| **12c** | Demographics table — verify data entry |
| **12d** | Covariate screening (age, sex, handedness) — Spearman correlations with BH correction |
| **12e** | Assumption checks (Shapiro-Wilk normality, Levene homogeneity of variance) |
| **12f** | 2×2×2 mixed ANOVA (Group × Session × Timing) + non-parametric fallbacks for metrics violating normality |
| **12g** | Results display: significant effects table, p-value heatmap, η² heatmap |
| **12h** | Pairwise post-hoc tests (Hedges' g as effect size measure) |
| **12i** | Effect size forest plot (η²) |

---

## Metric Glossary and How to Interpret Results

### 🔵 Frequency Band Power

| Band | Range | Typical associations | High power → |
|---|---|---|---|
| **Delta (δ)** | 1–3 Hz | Deep sleep, anaesthesia | Drowsiness, pathological states |
| **Theta (θ)** | 4–7 Hz | Drowsiness, meditation, memory encoding | Fatigue, deep relaxation |
| **Alpha (α)** | 8–13 Hz | Relaxed wakefulness, eyes closed | Calm, eyes closed, reduced cognitive effort |
| **Beta (β)** | 14–20 Hz | Active thinking, alertness | Concentration, cognitive activity, stress |

**Relative band power (`rel_*`)** — the percentage of total power in each band. Removes dependence on absolute signal amplitude (which varies across participants). The values always sum to 1.0: `rel_delta + rel_theta + rel_alpha + rel_beta = 1.0`.

---

### 🔴 DAR — Delta/Alpha Ratio

```
DAR = delta_power / alpha_power
```

| Value | Interpretation |
|---|---|
| DAR < 1 | Alpha dominates — relaxation, eyes closed |
| DAR ≈ 1 | Balance between slow and fast activity |
| DAR > 1 | Delta dominates — drowsiness, fatigue, or pathological state |

**Typical pattern:** eyes closed → strong alpha → low DAR. Eyes open or drowsy → weakened alpha → higher DAR.

---

### 🔴 DTABR — (Delta+Theta)/(Alpha+Beta) Ratio

```
DTABR = (delta_power + theta_power) / (alpha_power + beta_power)
```

Interpretation is analogous to DAR, but captures more frequency bands:

| Value | Interpretation |
|---|---|
| DTABR < 1 | Fast activity dominates (alpha+beta) — alertness |
| DTABR > 1 | Slow activity dominates (delta+theta) — drowsiness, fatigue |

DTABR is more sensitive than DAR because it incorporates theta (linked to drowsiness and stress) and beta (linked to active attention).

---

### 🟣 pdBSI — Power-difference Brain Symmetry Index

```
pdBSI = mean( |P_TP10(f) - P_TP9(f)| / (P_TP10(f) + P_TP9(f)) )
```
Mean is computed across all frequencies in the 1–30 Hz range.

| Value | Interpretation |
|---|---|
| pdBSI ≈ 0 | Symmetric activity in both hemispheres |
| pdBSI ≈ 0.5 | Moderate asymmetry |
| pdBSI ≈ 1 | Maximum asymmetry (all activity on one side) |

**Clinical context:** elevated pdBSI is observed after stroke, in epilepsy, and in certain mood disorders. In cognitive research, asymmetry can reflect lateralisation of function (e.g. frontal asymmetry in emotional regulation).

---

### 🟠 FOOOF Slope — Aperiodic Component Steepness

FOOOF (Fitting Oscillations & One-Over-F) decomposes the EEG spectrum into two components:
- **Aperiodic (1/f):** background noise floor — a straight line with negative slope in log–log space
- **Periodic:** oscillatory peaks above the background (e.g. alpha peak ~10 Hz)

**`fooof_slope`** = steepness of that line (positive value; higher = steeper drop in power with frequency).

| Value | Interpretation |
|---|---|
| Higher slope | More pronounced 1/f character; associated with older age, lower arousal |
| Lower slope | Flatter spectrum; associated with higher arousal, E/I balance disruption |

> Changes in FOOOF slope may reflect shifts in the excitation/inhibition (E/I) balance in the cortex.

---

### 🟢 Hjorth Parameters

Computed directly from the raw time-domain signal (no frequency transform needed):

| Parameter | Formula | Interpretation |
|---|---|---|
| **Activity** | Var(x) | Signal variance — measure of oscillation amplitude |
| **Mobility** | √(Var(x') / Var(x)) | Proxy for mean frequency — higher = faster oscillations |
| **Complexity** | Mobility(x'') / Mobility(x') | Deviation of signal shape from a pure sine wave — higher = more irregular |

Where x' is the first derivative (differences between consecutive samples) and x'' is the second derivative.

**Typical patterns:**
- Strong alpha oscillation (eyes closed) → high Activity, low Complexity (signal close to a sine wave)
- General anaesthesia → very high Activity, very low Complexity
- Active attention → lower Activity, higher Mobility and Complexity

---

### 🟤 Entropy Measures

For all entropy measures: **higher = more irregular/complex signal**.

#### Spectral Entropy

```
H = -Σ p(f) · log₂(p(f))
```
Treats the normalised PSD as a probability distribution.

| Value | Interpretation |
|---|---|
| Low | Power concentrated in a narrow band (e.g. strong alpha) |
| High | Power spread evenly across all frequencies (broadband activity) |

#### Sample Entropy (SampEn)

Measures how rarely short patterns in the signal repeat.

| Value | Interpretation |
|---|---|
| Low | Regular, predictable signal (e.g. strong alpha rhythm, anaesthesia) |
| High | Complex, unpredictable signal (wakefulness, active attention) |

> ⚠️ SampEn is computationally expensive — for long recordings the signal is downsampled to 2048 samples before computation.

#### Permutation Entropy

Analyses rank-order patterns in short windows of the signal. Faster and more robust to noise than SampEn.

| Value | Interpretation |
|---|---|
| Close to 0 | Highly regular signal (the same ordinal patterns keep recurring) |
| Close to 1 | Completely random signal (all patterns equally likely) |

---

## Statistical Results — How to Read Them

### Covariate Screening (12d)

Table of Spearman correlations between demographic variables (age, sex, handedness) and EEG metrics.  
`p_adj_BH < 0.05` → significant correlation after correction for multiple comparisons.

**What to do if a covariate is significant?**  
Consider adding it as a covariate in the ANOVA model (listed in `COVARIATES_TO_INCLUDE`).

---

### Assumption Checks (12e)

- **`normality_ok = True` (green)** → data for this metric do not significantly deviate from a normal distribution → ANOVA is appropriate
- **`normality_ok = False` (red)** → normality violated → non-parametric tests (Friedman + Mann-Whitney) are run additionally for this metric
- **`levene_ok`** → whether variances are homogeneous across groups. Violation is less critical for balanced designs.

---

### Mixed ANOVA — Main Effects and Interactions (12f / 12g)

The model tests three sources of variance:

| Source | What it tests |
|---|---|
| `group` | Do the two groups (control vs experimental) differ overall? |
| `within` | Do metrics change across the 4 timepoints (S1pre→S1post→S2pre→S2post)? |
| `group * within` | Does the change over time follow a *different pattern* in each group? (interaction effect — the most important term for intervention studies!) |

**How to read the results table:**

| Column | Meaning |
|---|---|
| `F` | F-statistic — higher = stronger effect |
| `p_unc` | Uncorrected p-value |
| `p_adj_BH` | BH-corrected p-value (use this one!) |
| `np2` (η²p) | Partial eta-squared — effect size (see table below) |
| `significant_adj` | `True` = effect is significant after correction |

**Interpreting η²p (partial eta-squared):**

| η²p | Interpretation |
|---|---|
| < 0.01 | Negligible effect |
| 0.01 – 0.06 | Small effect |
| 0.06 – 0.14 | Medium effect |
| > 0.14 | Large effect |

---

### P-value Heatmap (12g)

Colours: **green = small p** (close to significance), **red = large p** (no effect).  
Allows a quick overview of which metrics and which ANOVA sources are potentially interesting, even if they did not survive correction.

---

### Post-hoc Tests (12h)

Run only for metrics with a significant effect in the ANOVA.  
Compare each pair of conditions (e.g. S1_pre vs S1_post, control vs experimental at S2_post).

| Column | Meaning |
|---|---|
| `A` / `B` | Compared conditions |
| `p-corr` | FDR-corrected p-value (use this one!) |
| `hedges` | Hedges' g — effect size measure (see table below) |

**Interpreting Hedges' g:**

| \|g\| | Interpretation |
|---|---|
| < 0.2 | Negligible effect |
| 0.2 – 0.5 | Small effect |
| 0.5 – 0.8 | Medium effect |
| > 0.8 | Large effect |

---

### Effect Size Forest Plot (12i)

- **Solid, saturated bars** = statistically significant effect (p_adj < 0.05)
- **Faded bars** = non-significant effect
- Vertical dashed lines = Cohen's benchmarks (small / medium / large)
- Bar colour = ANOVA term: 🔵 group, 🟠 within, 🟣 interaction

---

### Group Timeline Dot Plot (Section 11)

- **Each dot** = one participant at one timepoint
- **Thick horizontal tick** = group mean
- **Thin lines** = trajectory of the same participant within a session (pre → post)
- **Dashed vertical line** = boundary between sessions
- 🔵 blue = control group, 🟠 orange = experimental group

**What to look for:**
- Do lines consistently rise or fall within one group? → within-session effect
- Does the pattern of change differ between groups? → interaction effect
- Are there any outlying observations (isolated dots)?

---

## Output Files

```
results/
  per_recording_metrics.csv          ← all metrics, one row per recording
  <label>_mean_psd.csv               ← mean PSD (TP9, TP10, avg) per recording
  stats_covariate_screening.csv      ← Spearman correlations: covariates × metrics
  stats_assumption_checks.csv        ← Shapiro-Wilk and Levene test results
  stats_mixed_anova.csv              ← mixed ANOVA results for all metrics
  stats_nonparametric.csv            ← Friedman + Mann-Whitney results (normality-violated metrics)
  stats_posthoc.csv                  ← pairwise post-hoc tests
  figures/
    <label>_TP9_spectrogram.png
    <label>_mean_psd.png
    <label>_TP9_fooof.png
    band_ratios_all.png
    pdBSI_all.png
    hjorth_all.png
    entropy_all.png
    group_panel_Band_ratios_and_symmetry_closed_eyes.png
    group_panel_Hjorth_parameters_closed_eyes.png
    group_panel_Entropy_measures_closed_eyes.png
    boxplot_panel_*.png
    effect_sizes_anova.png
```
