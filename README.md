# Multi-Modal Physiological & Video Recording

This project records synchronized data from multiple devices during an experimental procedure:

- Tobii eye tracker
- Shimmer GSR sensor
- Screen/video capture device
- Hand camera
- Session event log

The main script starts the different recording components as separate processes, stores the outputs in a procedure-specific folder, and stops all recordings together when the user presses `q` or interrupts the program.

## Project Structure

```text
project/
│
├── main.py
├── eye_worker.py
├── gsr_worker.py
├── licenseFile
├── README.md
│
└── Data/
    ├── Procedure_0/
    ├── Procedure_1/
    └── ...
```

The exact name of the main script may differ, but it is the script responsible for starting the GSR, eye-tracking, and FFmpeg recording processes.

## Requirements

The scripts currently assume a **Windows** environment because they use:

- Windows COM ports such as `COM6`
- `msvcrt`
- FFmpeg's `dshow` input
- `signal.CTRL_BREAK_EVENT`
- Windows DirectShow camera device names

### Python Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Depending on your Tobii installation, the `tobii-research` package may need to be installed using Tobii's own SDK distribution.

The project also requires **FFmpeg** to be installed and available from the command line.

Verify the installation with:

```bash
ffmpeg -version
```

If this command is not recognized, install FFmpeg and add it to the Windows `PATH`.

## Hardware Configuration

### Tobii Eye Tracker

The eye-tracking worker searches for all available Tobii eye trackers using:

```python
tr.find_all_eyetrackers()
```

If multiple trackers are found, the script currently uses the **first device returned by the SDK**.

A Tobii license file is expected at:

```text
licenseFile
```

The main script passes this filename to the eye-tracking worker.

### Shimmer GSR

The GSR device is currently configured to use:

```python
SERIAL_PORT_GSR = "COM6"
```

Change this value in `gsr_worker.py` if the Shimmer device is assigned a different COM port.

The baud rate is taken from:

```python
DEFAULT_BAUDRATE
```

provided by `pyshimmer`.

### Video Devices

Two video sources are recorded using FFmpeg and Windows DirectShow.

The screen/video capture source is currently:

```text
DVI2USB 3.0 D2S342420
```

The hand camera is currently:

```text
USB-videoenhed
```

These device names must match the DirectShow names available on the computer.

You can inspect available FFmpeg DirectShow devices with:

```bash
ffmpeg -list_devices true -f dshow -i dummy
```

Update the corresponding device names in the main script if necessary.

## Running the Experiment

Run the main recording script:

```bash
python main.py
```

A new data directory is created automatically.

For example:

```text
Data/Procedure_0/
```

If `Procedure_0` already exists, the program increments the number:

```text
Data/Procedure_1/
Data/Procedure_2/
Data/Procedure_3/
...
```

This prevents previous sessions from being overwritten.

Once the recording has started, the console displays:

```text
Recording started.
Press q to stop all processes
```

Press:

```text
q
```

to stop the recording session.

`Ctrl+C` can also be used to request shutdown.

## Recorded Files

Each procedure directory contains the data generated during that session.

A typical directory may look like:

```text
Data/
└── Procedure_0/
    ├── gaze_data.csv
    ├── gsr_record.csv
    ├── screen.mp4
    ├── hand.mp4
    └── LogFile.txt
```

## Eye-Tracking Data

The Tobii worker records gaze data to:

```text
gaze_data.csv
```

Each sample includes a system Unix timestamp followed by selected Tobii gaze measurements.

Recorded fields include:

```text
device_time_stamp

left_gaze_origin_validity
right_gaze_origin_validity

left_gaze_origin_in_user_coordinate_system
right_gaze_origin_in_user_coordinate_system

left_gaze_origin_in_trackbox_coordinate_system
right_gaze_origin_in_trackbox_coordinate_system

left_gaze_point_validity
right_gaze_point_validity

left_gaze_point_in_user_coordinate_system
right_gaze_point_in_user_coordinate_system

left_gaze_point_on_display_area
right_gaze_point_on_display_area

left_pupil_validity
right_pupil_validity

left_pupil_diameter
right_pupil_diameter
```

The first CSV column is:

```text
Timestamp Unix
```

which is generated using:

```python
time.time()
```

The remaining columns correspond to values supplied by the Tobii SDK.

Coordinate measurements returned as tuples are converted to lists before being written to the CSV.

The file is periodically flushed to disk to reduce the amount of buffered data that could be lost if the recording is interrupted.

## GSR Data

The Shimmer worker records galvanic skin response data to:

```text
gsr_record.csv
```

The file uses a semicolon (`;`) as its delimiter.

The columns are:

```text
timestamp_s
t_rel_s
gsr_raw
gsr_res_ohm
gsr_cond_uS
```

### `timestamp_s`

Unix timestamp associated with the received sample.

### `t_rel_s`

Time in seconds relative to the first GSR sample.

### `gsr_raw`

Raw GSR value received from the Shimmer device.

### `gsr_res_ohm`

Calculated skin resistance in ohms.

### `gsr_cond_uS`

Calculated skin conductance in microsiemens.

## GSR Conversion

The Shimmer raw GSR value contains:

- a 12-bit ADC measurement
- a 2-bit resistance-range identifier

The ADC value is extracted with:

```python
adc_12 = raw_int & 0x0FFF
```

The resistance range is extracted with:

```python
range_id = (raw_int >> 14) & 0x03
```

The range determines which feedback resistor is used:

```python
RF_TABLE = {
    0: 40200.0,
    1: 287000.0,
    2: 1_000_000.0,
    3: 3_300_000.0,
}
```

The raw ADC measurement is first converted to a voltage, which is then used to estimate skin resistance.

Skin conductance is calculated as:

```text
conductance [µS] = 1,000,000 / resistance [Ω]
```

Invalid measurements are represented internally as `NaN` and written as empty CSV fields when appropriate.

## GSR Reconnection Behavior

The GSR recording loop monitors whether new samples are being received.

If no samples are detected for more than approximately **3 seconds**, the script attempts to recreate the Shimmer connection.

The current sequence is:

1. Close the existing serial connection.
2. Wait 2 seconds.
3. Create a new `ShimmerGSRStreamer`.
4. Reinitialize the Shimmer device.
5. Restart streaming.

This provides basic recovery if the GSR stream stalls during an experiment.

## Video Recordings

Two FFmpeg processes are started.

### Screen / Capture-Card Recording

Output:

```text
screen.mp4
```

Current input:

```text
video=DVI2USB 3.0 D2S342420
```

### Hand Camera

Output:

```text
hand.mp4
```

Current input:

```text
video=USB-videoenhed
```

Both recordings use approximately the following FFmpeg configuration:

```text
30 FPS
H.264 / libx264
veryfast preset
yuv420p pixel format
```

The FFmpeg processes are placed in separate Windows process groups so the main script can attempt to stop them using:

```python
signal.CTRL_BREAK_EVENT
```

If that fails, the program attempts to terminate the FFmpeg process.

## Session Log

Session-level events are recorded in:

```text
LogFile.txt
```

The file is semicolon-separated and begins with:

```text
Timestamp;Relative time;Event/Landmark;
```

Typical entries include:

```text
Logging Started
screen.mp4 recording started
hand.mp4 recording started
EyeProcess started
Logging ended
```

Each entry contains:

1. Absolute Unix timestamp.
2. Time relative to the start of the overall session.
3. Event or landmark description.

This log can be used later to approximately align the different recordings.

## Process Architecture

The program uses Python's `multiprocessing` module.

Two worker processes are created:

```text
GSRProcess
EyeProcess
```

Conceptually, the application runs as:

```text
Main process
│
├── GSRProcess
│   └── Shimmer GSR recording
│
├── EyeProcess
│   └── Tobii eye-tracking recording
│
├── FFmpeg process
│   └── Screen capture
│
└── FFmpeg process
    └── Hand camera
```

A shared:

```python
multiprocessing.Event
```

is used to request that the Python recording workers stop.

When `q` is pressed, the main process calls:

```python
stop_event.set()
```

The GSR and eye-tracking loops detect this event and begin shutting down.

## Shutdown Procedure

When the recording ends, the main script:

1. Writes `Logging ended` to the logfile.
2. Signals both FFmpeg processes to stop.
3. Waits up to five seconds for each Python worker.
4. Checks whether any worker is still running.
5. Force-terminates workers that did not exit normally.
6. Prints:

```text
Shutdown complete.
```

## Important Configuration Values

Before using the system on another computer, check at least the following settings.

### `gsr_worker.py`

```python
SERIAL_PORT_GSR = "COM6"
```

### Eye-Tracking Worker

```python
license_file="licenseFile"
```

Ensure the license file is located where the script expects it.

### Main Recording Script

Check the FFmpeg DirectShow device names:

```text
DVI2USB 3.0 D2S342420
USB-videoenhed
```

These names are system-specific.

## Timing and Synchronization

The project records timestamps using the computer's system clock:

```python
time.time()
```

This is used throughout the eye-tracking, GSR, video-log, and session-log components.

The main process also records a common session start time:

```python
start_time = time.time()
```

Log entries can therefore contain both:

```text
absolute timestamp
relative session time
```

GSR additionally calculates time relative to its first recorded sample.

Because the devices and FFmpeg processes operate independently, the timestamps should be treated as software-level synchronization markers rather than hardware-triggered synchronization.

## Known Assumptions

The current implementation assumes that:

- The system is running Windows.
- FFmpeg is installed and available through `PATH`.
- The configured DirectShow video devices exist.
- The Shimmer GSR device is available on the configured COM port.
- A compatible Tobii eye tracker is connected.
- The Tobii license file is available when required.
- The main script supplies a valid `stop_event` to both recording workers.
- The first Tobii tracker discovered is the correct one to use.

## Troubleshooting

### No Eye Tracker Found

If the console displays:

```text
No eye tracker found!
```

Verify that:

- the Tobii device is connected,
- Tobii software/drivers are installed,
- the device is visible to the Tobii SDK.

### Tobii License Error

If you see:

```text
Could not apply license:
```

or:

```text
Tobii license failed:
```

verify that the configured `licenseFile` exists and is valid for the connected device.

### GSR Does Not Connect

Check that the configured port is correct:

```python
SERIAL_PORT_GSR = "COM6"
```

You can inspect available Windows COM ports in Device Manager.

### GSR Repeatedly Reconnects

Messages such as:

```text
[GSR] stopping old streamer
[GSR] creating new streamer
[GSR] starting new streamer
```

mean that no new samples were received for more than three seconds.

Check:

- Bluetooth connectivity
- Shimmer battery level
- COM-port stability
- whether another application is using the serial port

### FFmpeg Video Is Not Created

Verify the device names using:

```bash
ffmpeg -list_devices true -f dshow -i dummy
```

Then update the DirectShow device names in the main script.

### Existing Procedure Directories

The program does not overwrite previous procedure folders.

If:

```text
Data/Procedure_0
```

already exists, the next available numbered directory is selected automatically.

## Example Output

After one successful session, the project may contain:

```text
Data/
└── Procedure_4/
    ├── gaze_data.csv
    ├── gsr_record.csv
    ├── screen.mp4
    ├── hand.mp4
    └── LogFile.txt
```

These files collectively provide eye-tracking, physiological, video, and timing information for the recorded procedure.