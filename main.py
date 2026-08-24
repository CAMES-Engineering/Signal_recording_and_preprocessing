import os
import time
import signal
import subprocess as sub

from serial import Serial
from serial.serialutil import SerialException
from serial.tools import list_ports
from multiprocessing import Process, Event

import readchar
import msvcrt

from gsr_worker import record_gsr_to_csv
from eye_worker import record_eyetracking_to_csv


# Default logfile name used for recording experiment events and process
# landmarks.
logfile = "LogFile.txt"


def com_port_listed(port_name):
    """Check whether a specified COM port is currently listed by the system.

    Args:
        port_name: Name of the serial port to search for, for example ``COM6``.

    Returns:
        ``True`` if the port is present in the list of available serial ports;
        otherwise ``False``.
    """
    return any(
        port.device == port_name
        for port in list_ports.comports()
    )


def com_port_openable(port_name, baudrate):
    """Check whether a serial port can be opened successfully.

    The port is opened temporarily using the supplied baud rate and closed
    immediately afterwards.

    Args:
        port_name: Name of the serial port to test.
        baudrate: Baud rate used when opening the serial connection.

    Returns:
        ``True`` if the port can be opened and closed successfully;
        otherwise ``False``.
    """
    try:
        s = Serial(
            port_name,
            baudrate,
            timeout=1
        )

        s.close()

        return True

    except Exception:
        return False


def run_gsr(proc_path, stop_event):
    """Run the GSR recording worker.

    This function serves as the multiprocessing entry point for the GSR
    recording process.

    Args:
        proc_path: Directory in which GSR data should be stored.
        stop_event: Shared multiprocessing event used to signal when recording
            should stop.

    Returns:
        None.
    """
    record_gsr_to_csv(
        duration_seconds=None,
        save_dir=proc_path,
        stop_event=stop_event
    )


def run_eye(proc_path, stop_event, start_time):
    """Run the eye-tracking recording worker.

    This function serves as the multiprocessing entry point for the Tobii
    eye-tracking process.

    Args:
        proc_path: Directory in which eye-tracking data should be stored.
        stop_event: Shared multiprocessing event used to signal when recording
            should stop.
        start_time: Unix timestamp representing the start of the recording
            session.

    Returns:
        None.
    """
    record_eyetracking_to_csv(
        duration_seconds=None,
        output_file="gaze_data.csv",
        license_file="licenseFile",
        save_dir=proc_path,
        stop_event=stop_event,
        log_time=start_time
    )


def run_ffmpeg(camera, save_dir, logfiletxt, start_time):
    """Start an FFmpeg video-recording subprocess.

    Two camera configurations are supported. A ``camera`` value of ``0``
    starts the screen-capture device, while any other value starts the hand
    camera.

    The FFmpeg process records H.264 video at 30 frames per second and writes
    the resulting MP4 file to ``save_dir``.

    Args:
        camera: Camera selector. ``0`` selects the screen-capture device;
            any other value selects the hand camera.
        save_dir: Directory in which the video file should be saved.
        logfiletxt: Writable logfile object used to record the start of the
            video recording.
        start_time: Unix timestamp representing the start of the overall
            recording session.

    Returns:
        The ``subprocess.Popen`` object representing the FFmpeg process.
    """
    if camera == 0:
        # Configure recording from the screen-capture device.
        out_path = os.path.join(
            save_dir,
            "screen.mp4"
        )

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-f", "dshow",
            "-framerate", "30",
            "-i", "video=DVI2USB 3.0 D2S342420",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            out_path,
        ]

        print("Screen recording to:", out_path)

    else:
        # Configure recording from the hand-camera device.
        out_path = os.path.join(
            save_dir,
            "hand.mp4"
        )

        ffmpeg_command = [
            "ffmpeg",
            "-y",
            "-f", "dshow",
            "-framerate", "30",
            "-i", "video=USB-videoenhed",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            out_path,
        ]

        print("Hand camera recording to:", out_path)

    # Start FFmpeg as a separate process group. Creating a separate process
    # group allows CTRL_BREAK_EVENT to be sent later when stopping recording.
    pro = sub.Popen(
        ffmpeg_command,
        shell=True,
        stdout=sub.DEVNULL,
        stderr=sub.DEVNULL,
        creationflags=sub.CREATE_NEW_PROCESS_GROUP
    )

    # Extract the output filename from the complete Windows path.
    name_vid = out_path.split('\\')[-1]

    # Log both the absolute Unix timestamp and the time relative to the start
    # of the recording session.
    logfiletxt.write(
        '%s;%s;%s;\n'
        % (
            time.time(),
            time.time() - start_time,
            f'{name_vid} recording started'
        )
    )

    return pro


def stop_ffmpeg(proc):
    """Stop an FFmpeg recording process.

    The function first attempts a graceful shutdown by sending a Windows
    ``CTRL_BREAK_EVENT``. If that fails, it falls back to terminating the
    process directly.

    Args:
        proc: ``subprocess.Popen`` instance representing the FFmpeg process,
            or ``None``.

    Returns:
        None.
    """
    # Nothing needs to be done when no process was supplied.
    if proc is None:
        return

    try:
        # Attempt a graceful FFmpeg shutdown so the output video can be
        # finalized correctly.
        proc.send_signal(signal.CTRL_BREAK_EVENT)

    except Exception as e:
        print(
            "Error sending CTRL_BREAK_EVENT to ffmpeg:",
            e
        )

        try:
            # Fall back to terminating the process if the graceful stop fails.
            proc.terminate()

        except Exception as e2:
            print(
                "Error terminating ffmpeg:",
                e2
            )


# Execute the complete recording workflow when this file is run directly.
if __name__ == "__main__":

    # -----------------------------------------------------------------------
    # Create a unique directory for this recording procedure
    # -----------------------------------------------------------------------

    count = 0
    datadir = "Data"

    # Begin by attempting to use ``Procedure_0``.
    proc_dir = os.path.join(
        datadir,
        f"Procedure_{count}"
    )

    # Tracks whether the eye-tracking process has been detected as started.
    started = False

    # Increment the procedure number until an unused directory name is found.
    # This prevents a new recording session from overwriting an existing one.
    while os.path.exists(proc_dir):
        count += 1

        proc_dir = os.path.join(
            datadir,
            f"Procedure_{count}"
        )

    # Create the directory that will contain all recordings from this session.
    os.makedirs(
        proc_dir,
        exist_ok=True
    )

    # -----------------------------------------------------------------------
    # Initialize process synchronization and timing
    # -----------------------------------------------------------------------

    # Shared event used to request that the recording worker processes stop.
    stop_event = Event()

    # Record the common session start time so different recordings and log
    # entries can be aligned relative to the same origin.
    start_time = time.time()

    # -----------------------------------------------------------------------
    # Create recording worker processes
    # -----------------------------------------------------------------------

    # Create the GSR recording process. The process is created here but is not
    # started until ``start()`` is called below.
    p_gsr = Process(
        target=run_gsr,
        args=(
            proc_dir,
            stop_event
        ),
        name="GSRProcess"
    )

    # Create the eye-tracking recording process.
    p_eye = Process(
        target=run_eye,
        args=(
            proc_dir,
            stop_event,
            start_time
        ),
        name="EyeProcess"
    )

    # -----------------------------------------------------------------------
    # Initialize the session logfile
    # -----------------------------------------------------------------------

    logfile_path = os.path.join(
        proc_dir,
        logfile
    )

    logfiletxt = open(
        logfile_path,
        'w'
    )

    # Write the logfile header.
    logfiletxt.write(
        '%s;%s;%s;\n'
        % (
            'Timestamp',
            'Relative time',
            'Event/Landmark'
        )
    )

    # Record the start of the overall logging session.
    logfiletxt.write(
        '%s;%s;%s;\n'
        % (
            time.time(),
            0,
            'Logging Started'
        )
    )

    # Group the multiprocessing workers so they can be started and stopped
    # consistently.
    processes = (
        p_gsr,
        p_eye
    )

    # -----------------------------------------------------------------------
    # Start physiological recording processes
    # -----------------------------------------------------------------------

    for p in processes:
        p.start()

    # -----------------------------------------------------------------------
    # Start video recordings
    # -----------------------------------------------------------------------

    # Start the screen-capture recording.
    screen_cam = run_ffmpeg(
        0,
        proc_dir,
        logfiletxt,
        start_time
    )

    # Start the hand-camera recording.
    person_cam = run_ffmpeg(
        1,
        proc_dir,
        logfiletxt,
        start_time
    )

    try:
        # Counters reserved for tracking process restarts.
        #
        # NOTE:
        # These variables are currently initialized but not used elsewhere
        # in this script.
        ecg_restart_count = 0
        gsr_restart_count = 0

        print("Recording started.")
        print("Press q to stop all processes")

        # -------------------------------------------------------------------
        # Main recording-control loop
        # -------------------------------------------------------------------

        while not stop_event.is_set():

            # Check whether a keyboard key is available without blocking the
            # recording-control loop.
            if msvcrt.kbhit():
                key = readchar.readkey()

                # Pressing ``q`` requests that all recording processes stop.
                if key == 'q':
                    print(key)

                    # Setting the multiprocessing event notifies workers such
                    # as the GSR and eye-tracking processes to exit.
                    stop_event.set()

            # Detect the creation of the eye-tracking output file and log the
            # first occurrence as a landmark indicating that the eye-tracking
            # process has started producing data.
            if (
                not started
                and os.path.exists(
                    os.path.join(
                        proc_dir,
                        'gaze_minimal.csv'
                    )
                )
            ):
                logfiletxt.write(
                    '%s;%s;%s;\n'
                    % (
                        time.time(),
                        round(
                            time.time() - start_time,
                            3
                        ),
                        'EyeProcess started'
                    )
                )

                # Ensure the event is logged only once.
                started = True

            # Short sleep prevents this control loop from consuming excessive
            # CPU while polling the keyboard and filesystem.
            time.sleep(0.01)

    except KeyboardInterrupt:
        # Ctrl+C also requests a coordinated shutdown of the worker processes.
        stop_event.set()

    finally:
        # -------------------------------------------------------------------
        # Record the end of the session
        # -------------------------------------------------------------------

        logfiletxt.write(
            '%s;%s;%s;\n'
            % (
                time.time(),
                round(
                    time.time() - start_time,
                    3
                ),
                'Logging ended'
            )
        )

        # -------------------------------------------------------------------
        # Stop video recordings
        # -------------------------------------------------------------------

        stop_ffmpeg(screen_cam)
        stop_ffmpeg(person_cam)

        # -------------------------------------------------------------------
        # Wait for recording workers to stop normally
        # -------------------------------------------------------------------

        for p in processes:
            # Give each worker up to five seconds to exit after the stop event
            # has been set.
            p.join(timeout=5)

        # -------------------------------------------------------------------
        # Force-terminate any worker processes that remain alive
        # -------------------------------------------------------------------

        for p in processes:
            if p.is_alive():
                print(
                    "Force-terminating:",
                    p.name
                )

                p.terminate()
                p.join()

        print("Shutdown complete.")