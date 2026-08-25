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
