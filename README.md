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
conda create --name muse -c conda-forge -c defaults python=3.10 ipykernel pandas numpy pywavelets matplotlib scipy pip -y
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


## 3. Automating Your Experiment [eeg_setup.py](eeg_setup.py) 

The `eeg_setup.py` script is designed to handle folder creation and recording for multiple participants. 

### What does this script actually do?
It acts as both an **Organizer** and a **Recording Assistant**:
1. **The Organizer:** It instantly builds a massive, perfectly organized folder tree for your entire study. It creates a dedicated space for every participant, session, and condition.
2. **The Assistant:** When you are ready to record, it asks you a few simple questions (e.g., "Which participant is this?" and "Is this pre- or post-experiment?"). It then automatically launches the Muse recording and saves the `.csv` file directly into the correct folder with a neat timestamp. 

### How to use it:

Open your terminal, make sure you are in the same folder as the script, and use one of these two commands:

**1. To just create the folders (Do this first):**
```bash
python eeg_setup.py --setup-only
```
*This will generate an `eeg_study/` folder containing subfolders for all your participants, sessions, and conditions without starting any recordings.*

**2. To run an actual recording session:**
```bash
python eeg_setup.py
```
*The script will greet you and ask for the Participant Number, Session Number and if it is pre or post recording. It will then automatically guide you through recording the "eyes open" and "eyes closed" conditions, saving the data exactly where it belongs.*

### What YOU can change:
If you open the `eeg_setup.py` file in any text editor, you will see a block of settings near the top. You can safely change the numbers inside this code to fit your specific experiment:

* **`N_PARTICIPANTS = 5`**: Change the the total number of people participating in your study. 
* **`N_SESSIONS = 3`**: Change if your participants are doing more or fewer sessions.
* **`RECORDING_SECS = 120`**: This controls how long the Muse records data for each condition. `120` means 120 seconds (2 minutes).
* **`BASE_DIR = "eeg_study"`**: This is the name of the master folder the script will create.


## 4. Cleaning and Processing the Data [preprocess.py](preprocess.py)

After you have recorded your EEG data, you are left with raw `.csv` files. While these contain your brainwave readings, they aren't quite ready for scientific analysis yet. They lack important metadata (like who the participant is) and are full of background noise.

The `preprocess.py` script acts as your automated data cleaner. It takes the messy `.csv` files, cleans them up, attaches the participant's information, and converts them into `.fif` files, which are the standard format used by professional EEG analysis software (like MNE-Python).

### What does this script actually do?
1. **Reads the `participants.csv` file:** It looks at a master spreadsheet you create to find information about the participant (e.g., age, sex, handedness) and attaches this data directly to the EEG recording.
2. **Finds the Right Data:** It automatically digs into your `eeg_study` folder to find the most recent `.csv` recording for the specific participant and session you ask for.
3. **Converts to `.fif` format:** It transforms the raw `.csv` data into a `raw.fif` file, securely saving it in the `raw/` folder you created earlier.
4. **Applies Filters (The Cleaning Process):** It acts like a digital sieve to remove noise.
   * **Notch Filter:** Removes the exact frequency of the electrical hum from the power lines in your building (set to 50 Hz and 100 Hz).
   * **Bandpass Filter:** Removes extremely slow signals (like sweat or slow movement) and extremely fast signals (like muscle clenches), keeping only the brainwave frequencies we care about (between 0.5 Hz and 35 Hz). Removes extremely slow signals (like sweat or slow movement) and extremely fast signals (like muscle clenches), keeping only the brainwave frequencies we care about (between 0.5 Hz and 35 Hz). (In studies we usually take 0.5 - 35 Hz or 1 - 40 Hz)
5. **Generates Quality Reports:** It draws several visual graphs before and after filtering, saving them as images so you can prove the data is clean.
6. **Saves the Final Product:** It saves this newly cleaned data as a `filtered.fif` file in your `filtered/` folder.

### Before you run it:
You **must** create a file named `participants.csv` in the same folder as this script. This file needs to contain the details of the people in your study. It should look exactly like this:

```csv
id, his_id, first_name, sex, birthday, hand
1, P01, Alice, 2, 1995-05-14, 1
2, P02, Bob, 1, 1998-11-20, 1
```
*(Key: Sex: 0 = Unknown, 1 = Male, 2 = Female\
Hand: 0 = Unknown, 1 = Right, 2 = Left, 3 = Both).*

### How to use it:
Open your terminal and run the script, providing it with the specifics of the file you want to process. 

**Basic Usage:**
To process Participant 1, Session 1, for the "pre" (before task) "open_eyes" condition:
```bash
python preprocess.py --participant 1 --session 1 --timing pre --condition open_eyes
```
*(You can also use the shorthand letters: `-p 1 -s 1 -t pre -c open_eyes`)*

**Dealing with Bad Sensors:**
If you noticed during recording that the `AF7` sensor had a terrible connection and was just recording noise, you can tell the script to mark it as a "bad channel" so it doesn't ruin your analysis:
```bash
python preprocess.py -p 1 -s 1 -t pre -c open_eyes --bad-channels AF7
```

**Running Quickly Without Graphs:**
If you are processing 50 files and don't want to wait for it to draw and save graphs for every single one, you can tell it to skip the visual plots:
```bash
python preprocess.py -p 1 -s 1 -t pre -c open_eyes --skip-plots
```

### What YOU can change:
If you open the `preprocess.py` file, you can tweak these settings at the top to match your location and study goals:

* **`EXPERIMENTER = " "`**: Change this to your name!
* **`NOTCH_FREQS = [50.0, 100.0]`**: This removes power line noise. If you are doing this study in North America, change this to `[60.0, 120.0]` because their power grid runs at a different frequency than Europe. 
* **`BANDPASS = (0.5, 35.0)`**: This defines the window of frequencies you keep. `0.5` removes slow drifts, and `35.0` removes fast muscle noise. If you specifically need to study higher-frequency Gamma waves, you might need to raise `35.0` to something like `50.0`.

> **IMPORTANT NOTE: DO NOT PANIC!** > The `analysis.ipynb` script is the "final boss" of this project. **It will be made available to all participants AFTER the Brainhack.**  
> *Why?* Because during the event, your primary mission is to try and analise file by yourself. In case it won't work we prepared the ready script for the end of Brainhack.

***

## 5. Analyzing the Results [analysis.ipynb](analysis.ipynb)

If `preprocess.py` was the digital sieve that cleaned your data, `analysis.ipynb` is the laboratory microscope that lets you actually see what the brain was doing. 

Brainwaves are a messy mixture of different frequencies, noises, and patterns all happening at once. This massive notebook does the heavy mathematical lifting to pull those signals apart so we can measure specific brain states and compare them.

### What does this script actually do?
This notebook automatically scans your entire `eeg_study` folder, processes every single recording it finds, and performs four main jobs:

1. **Calculates Brainwave "Bands" (The Classics):** It separates your data into the famous brainwave categories you might have heard of:
   * **Delta (1-3 Hz):** Deep sleep / unconsciousness.
   * **Theta (4-7 Hz):** Drowsiness / deep relaxation.
   * **Alpha (8-13 Hz):** Relaxed, awake state (usually spikes when you close your eyes!).
   * **Beta (14-20 Hz):** Active thinking and focus.

2. **Extracts Advanced Brain Metrics (The Cool Stuff):**
   It doesn't just look at basic waves; it uses advanced math to calculate:
   * **Brain Symmetry (pdBSI):** Checks if your left brain (TP9) and right brain (TP10) are doing the same thing, or if one side is dominating.
   * **Complexity & Entropy:** Measures how "unpredictable" or chaotic the brainwaves are. 
   * **FOOOF (Aperiodic noise):** Separates the actual oscillating brainwaves from the background electrical "noise" of the brain itself.
   * **Ratios (DAR & DTABR):** Compares slow waves to fast waves, which is often used in research to measure fatigue or cognitive load.

3. **Builds the Master Spreadsheet:**
   It takes all these hundreds of calculations for every single participant and session, and elegantly packages them into one giant, easy-to-read CSV file called `per_recording_metrics.csv` in your `results/` folder.

4. **Draws the Graphs:**
   It generates a massive gallery of scientific plots (saving them to `results/figures/`). This includes:
   * **Spectrograms:** Heatmaps of brain activity over time.
   * **Radar Charts:** Web-like charts showing the balance of a participant's brainwaves.
   * **Pre/Post Comparisons:** Line graphs showing exactly how a participant's brain changed between their first recording and their last recording.

---

### What YOU will be able to change (Once it's released):
When you finally get this notebook, you don't need to understand all the complex math to use it. You can control the entire script using a simple "filter" section at the very top of the file:

* **Filter by Participant:** If you only want to analyze your own data (let's say you are Participant 3), you can change `FILTER_PARTICIPANTS = None` to `FILTER_PARTICI1PANTS = [3]`. 
* **Filter by Condition:**
  If you only want to generate graphs for the "eyes closed" test, you can change `FILTER_CONDITIONS = None` to `FILTER_CONDITIONS = ['closed_eyes']`.
* **Tweaking the Bands:**
  If you read a paper that defines the "Alpha" band slightly differently (e.g., 8-12 Hz instead of 8-13 Hz), you can simply change the numbers in the `BANDS = {...}` dictionary at the top, and the entire notebook will recalculate everything using your new rules!