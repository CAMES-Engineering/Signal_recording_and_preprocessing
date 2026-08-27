# Signal Recording and Preprocessing

This repository contains tools for the synchronized recording and preprocessing of multimodal physiological signals and video streams. It is designed to capture data from Shimmer sensors (GSR/ECG), Tobii eye-trackers, and multiple video sources simultaneously.

## Features

- **Multimodal Data Acquisition**: Records Galvanic Skin Response (GSR), eye-tracking data, and multiple video streams concurrently.
- **Multiprocessing Architecture**: Utilizes Python's `multiprocessing` to handle high-frequency data streams in parallel, ensuring accurate timing and preventing bottlenecks.
- **Automated Video Capture**: Integrates with FFmpeg for low-overhead, hardware-accelerated video recording (e.g., screen capture and a hand/environment camera).
- **Synchronized Logging**: Maintains a centralized log file (`LogFile.txt`) that timestamps all recording events and hardware landmarks, allowing for precise data alignment during analysis.
- **Heatmap Generation**: Includes a script (`make_heatmap.py`) for generating cumulative heatmap videos from recorded gaze data.
- **Preprocessing Pipelines**: Includes dedicated modules for preprocessing eye-tracking and GSR data.

## Hardware Requirements

To utilize the full capabilities of the default recording script (`main.py`), the following hardware is required:
- Shimmer3 sensors (for GSR / ECG data collection).
- Tobii Eye Tracker.
- Video capture devices (e.g., a screen capture card like DVI2USB 3.0 and a secondary USB webcam).

*Note: Device names in `main.py` (such as the FFmpeg video input names) may need to be modified to match your specific hardware setup.*

## Software Dependencies

The project relies on Python and external tools for data acquisition.

1. Ensure **FFmpeg** is installed on your system and added to your system's PATH.
2. Install the required Python packages:

```bash
pip install -r requirements.txt
```

Key Python dependencies include:
- `pyshimmer` for Shimmer device communication
- `tobii-research` for Tobii eye-tracker integration
- `numpy` & `pandas` for data handling
- `pyserial` for serial port management
- `opencv-python` (cv2) for heatmap generation

## Usage

### Recording Data

To start a new recording session:

1. Ensure all hardware devices are connected and powered on.
2. Run the main recording script:

```bash
python main.py
```

3. The script will automatically create a new timestamped directory (e.g., `Data/Procedure_0/`) for the session and start all sensors and cameras.
4. **Press `q`** in the terminal to gracefully stop all recordings and finalize the files.

### Data Output

For each session, the following files will typically be generated in the `Data/Procedure_X/` folder:
- `gaze_data.csv` (or `gaze_minimal.csv`): Raw eye-tracking data.
- `screen.mp4` / `hand.mp4`: Recorded video streams.
- `LogFile.txt`: The session synchronization log.
- Associated GSR/ECG CSV files.

### Event Annotation
Session recordings were annotated post-collection using the ELAN annotation tool. 
For each participant, a `.txt` marker file specifies the start and end times (in seconds from recording onset) of each task, exploration period, and feedback 
phase. These markers are used in subsequent preprocessing to segment physiological signals into task-relevant windows and to identify exploration periods for feature 
extraction.

### Eye-Tracking Preprocessing
Raw gaze data (`gaze_data.csv`) is preprocessed through the following steps:

1. **Gaze Marking** — Event marker files are aligned to the gaze data using 
   Unix timestamps, and each gaze sample is labelled with its corresponding 
   task and exploration period.
2. **Fixation and Saccade Detection** — Fixations are detected using the I2MC 
   algorithm. Saccades are subsequently extracted from inter-fixation intervals 
   using a main-sequence-based classification criterion; only forward saccades 
   are retained.
3. **Pupil Preprocessing** — The raw pupil signal is cleaned through validity 
   masking, blink detection with temporal padding, binocular averaging, spike 
   removal, linear interpolation of short gaps, and Savitzky-Golay smoothing.
4. **Feature Extraction** — Eye-tracking features are extracted exclusively from 
   exploration periods and aggregated per task per participant. Features are 
   z-scored within each participant to account for individual differences.

### GSR Preprocessing
Raw GSR signals are preprocessed through spike suppression, low-pass filtering, task-based segmentation, and per-task baseline correction. Tonic and phasic 
components are decomposed using the cvxEDA algorithm. Features are extracted from exploration periods and z-scored within each participant.

### Generating Heatmaps

After a recording session, you can visualize the gaze data by generating a cumulative heatmap video:

```bash
python make_heatmap.py
```
## Deposited Data

The data supporting this study are available at: https://doi.org/10.5281/zenodo.20553390

### Raw Data (P01–P20)
Each participant folder contains the raw outputs from a single recording session:
- `gsr_record.csv` — raw GSR recording from the Shimmer3 GSR+ device
- `gaze_data.csv` — raw gaze data recorded at 90 Hz from the Tobii Eye Tracker 4C
- `screen.mp4` — screen recording used for ELAN task annotation

Three participants are excluded from eye-tracking analyses: P10 (gaze validity below the 75% threshold), P11 and P13 (device malfunction). Six task-participant combinations are excluded from GSR analyses due to recording interruptions or signal instability. Full exclusion details are provided in the manuscript.

### eye_features.csv
Preprocessed task-level eye-tracking features for 17 participants across 9 tasks (148 participant-task rows). Each row corresponds to one participant-task observation extracted from exploration periods. Raw and within-participant z-scored values are provided for each feature; z-scored columns are indicated by the `_z` suffix.

| Column | Description |
|--------|-------------|
| participant | Anonymized participant ID (P01–P20) |
| task_label | Task identifier (see Task Label Mapping below) |
| task_duration_s | Exploration duration (seconds) |
| pupil_mean_bc | Baseline-corrected mean pupil diameter (mm) |
| pupil_slope | Linear slope of pupil diameter over exploration period |
| blink_time_frac | Fraction of exploration time spent blinking |
| blink_per_min | Blink rate (blinks/min) |
| pupil_valid_pct | Percentage of valid pupil samples |
| fix_count | Number of fixations |
| fix_rate_hz | Fixation rate (Hz) |
| fix_dur_mean_s | Mean fixation duration (seconds) |
| fix_dur_std_s | Standard deviation of fixation duration (seconds) |
| fix_dur_total_s | Total fixation time (seconds) |
| sac_count | Number of forward saccades |
| sac_rate_hz | Forward saccade rate (Hz) |
| sac_amp_mean_px | Mean forward saccade amplitude (pixels) |
| sac_amp_std_px | Standard deviation of forward saccade amplitude (pixels) |

### gsr_features.csv
Preprocessed task-level GSR features for all 20 participants across 9 tasks (154 participant-task rows). Each row corresponds to one participant-task observation extracted from exploration periods, with per-task median baseline correction applied using the 60-second window preceding task onset. Raw and within-participant z-scored values are provided for each feature; z-scored columns are indicated by the `_z` suffix.

| Column | Description |
|--------|-------------|
| participant | Anonymized participant ID (P01–P20) |
| task_id | Task identifier (see Task Label Mapping below) |
| n_explorations | Number of exploration sub-periods within the task |
| total_duration_s | Total exploration duration (seconds) |
| tonic_mean_uS | Mean tonic EDA conductance (µS) |
| tonic_slope | Linear slope of tonic conductance over exploration period |
| scr_count | Number of discrete SCRs detected |
| scr_rate | SCR rate (SCRs per second) |
| scr_amp_mean | Mean SCR amplitude (µS) |
| scr_amp_sum | Summed SCR amplitude (µS) |
| bc_mean_uS | Baseline-corrected mean conductance (µS) |

### Task Label Mapping

| Task Label | Module | Description |
|------------|--------|-------------|
| task1_5_2 | Obstetrics 20 Weeks | Abdominal circumference measurement |
| task1_6_2 | Obstetrics 20 Weeks | Femur length measurement |
| task2_2_1 | Obstetrics Fetal Growth | Head circumference and biparietal diameter |
| task2_5_1 | Obstetrics Fetal Growth | Femur length measurement |
| task3_1_1 | Fetal Anomaly Survey | Biparietal diameter and head circumference |
| task3_3_1 | Fetal Anomaly Survey | Transcerebellar view |
| task3_4_2 | Fetal Anomaly Survey | Abdominal circumference measurement |
| task3_8_2 | Fetal Anomaly Survey | Fetal kidneys |
| task3_8_3 | Fetal Anomaly Survey | Femur length measurement |
