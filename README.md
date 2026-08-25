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

### Generating Heatmaps

After a recording session, you can visualize the gaze data by generating a cumulative heatmap video:

```bash
python make_heatmap.py
```
