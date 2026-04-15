# Step-by-Step Guide for EEG Setup with Muse

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

If `preprocess.py` was the digital sieve that cleaned your data, `analysis.ipynb` is the laboratory microscope. It performs the heavy mathematical lifting—extracting features like **spectral entropy**, **Hjorth parameters**, and **aperiodic slopes**—and compiles them into a master spreadsheet.

### 1. What does this script compute?
The notebook extracts a "fingerprint" of brain activity for every recording:

| Category | Features | What it measures |
| :--- | :--- | :--- |
| **Band Power** | Alpha, Beta, Theta, Delta | The "volume" of specific brain rhythms. |
| **Symmetry** | **pdBSI** | How balanced the left (TP9) and right (TP10) hemispheres are. |
| **Complexity** | **Hjorth**, **Entropy** | How irregular or "unpredictable" the brain signal is. |
| **Ratios** | **DAR**, **DTABR** | The balance between slow (Delta/Theta) and fast (Alpha/Beta) waves. |

---

### 2. Statistical Interpretation (ANOVA)
The "Final Boss" of the analysis is the **Mixed ANOVA** (Analysis of Variance). This test determines if your experiment actually worked by comparing your **Research Group** against the **Control Group** across multiple sessions.



#### How to read the `stats_mixed_anova.csv` table:
When you look at the results table, focus on these three values:

1.  **The Source (What caused the change?):**
    * **`group`**: Is there a general difference between people who exercised and those who didn't?
    * **`within`**: Did brainwaves change simply because time passed (Session 1 vs Session 2)?
    * **`group * within` (Interaction)**: **This is the gold standard.** If this is significant, it means the research group changed *differently* than the control group. This is usually what proves your hypothesis.

2.  **`p-adj` (The "Is it real?" value):**
    * **$p < 0.05$**: Statistically significant. There is less than a 5% chance this result happened by luck.
    * **`p-adj` (BH correction)**: We adjust p-values to account for "false positives" because we are testing many brain features at once. **Always trust `p-adj` over raw `p` values.**

3.  **`np2` (Partial Eta-Squared - The "How big is it?" value):**
    * **0.01**: Small effect (a tiny nudge in brain activity).
    * **0.06**: Medium effect (a noticeable shift).
    * **0.14+**: Large effect (a major change in brain state).

---

### 3. Visualizing the Data
The notebook generates several plots in `results/figures/` to help you "see" the brain:

* **Spectrograms:** Heatmaps showing brain power over time. Bright "clouds" at 10Hz indicate strong Alpha waves.
* **FOOOF Plots:** Shows the "aperiodic" background noise of the brain. A steeper slope (orange dashed line) often relates to higher levels of relaxation or lower cognitive load.
* **Group Timelines:** These "dot plots" show every participant's journey. Look for the thin lines connecting dots—if the Research Group lines consistently move up while Control Group lines stay flat, your intervention had an effect!