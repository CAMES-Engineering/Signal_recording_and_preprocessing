import tobii_research as tr
import time
import csv
import os


# Gaze data fields to record from the Tobii eye tracker.
#
# Each tuple contains:
#   1. The key used in the gaze-data dictionary returned by the Tobii SDK.
#   2. The expected number of values associated with that measurement.
#
# NOTE:
# The second tuple value is currently descriptive metadata only and is not
# used by the recording logic below.
gaze_stuff = [
    ('device_time_stamp', 1),

    ('left_gaze_origin_validity', 1),
    ('right_gaze_origin_validity', 1),

    ('left_gaze_origin_in_user_coordinate_system', 3),
    ('right_gaze_origin_in_user_coordinate_system', 3),

    ('left_gaze_origin_in_trackbox_coordinate_system', 3),
    ('right_gaze_origin_in_trackbox_coordinate_system', 3),

    ('left_gaze_point_validity', 1),
    ('right_gaze_point_validity', 1),

    ('left_gaze_point_in_user_coordinate_system', 3),
    ('right_gaze_point_in_user_coordinate_system', 3),

    ('left_gaze_point_on_display_area', 2),
    ('right_gaze_point_on_display_area', 2),

    ('left_pupil_validity', 1),
    ('right_pupil_validity', 1),

    ('left_pupil_diameter', 1),
    ('right_pupil_diameter', 1)
]


def record_eyetracking_to_csv(
    duration_seconds=None,
    output_file="gaze_recording.csv",
    license_file=None,
    save_dir=None,
    stop_event=None,
    log_time=None
):
    """Record Tobii eye-tracking gaze data to a CSV file.

    The function discovers connected Tobii eye trackers, selects the first
    available tracker, optionally applies a license, subscribes to gaze-data
    events, and writes the received measurements to a CSV file.

    Recording continues until either ``stop_event`` is set, the optional
    recording duration is reached, or a ``KeyboardInterrupt`` occurs.

    Args:
        duration_seconds: Recording duration in seconds.
        output_file: Name of the CSV file used for storing gaze data.
        license_file: Optional path to a Tobii license file. Only needed for non research tobii devices
        save_dir: Directory in which the output CSV file is stored.
        stop_event: Event object with an ``is_set()`` method. Recording
            stops when this event becomes set.
        log_time: Reserved parameter. Currently unused.

    Returns:
        None.
    """
    # Construct the complete path for the gaze-data CSV file.
    save_path = os.path.join(save_dir, output_file)

    # Discover all Tobii eye trackers currently available to the SDK.
    trackers = tr.find_all_eyetrackers()
    print("Eye trackers found:", trackers)

    # Construct the intended log-file path.
    # NOTE: This variable is currently not used elsewhere in the function.
    logfile = os.path.join(save_dir, 'LogFile.txt')

    # Recording cannot proceed if no eye tracker is connected.
    if len(trackers) == 0:
        print("No eye tracker found!")
        return

    # Use the first available eye tracker.
    tracker = trackers[0]
    print("Using Tobii tracker at:", tracker.address)

    # Apply the Tobii license when a license file has been supplied.
    if license_file:
        try:
            # License files must be read as binary data.
            with open(license_file, "rb") as f:
                lic = f.read()

            # The SDK returns validation results for licenses that fail.
            res = tracker.apply_licenses(lic)

            if len(res) == 0:
                print("Tobii license applied successfully.")
            else:
                print("Tobii license failed:", res[0].validation_result)

        except Exception as e:
            # Keep the existing behavior: report license errors without
            # terminating the recording function.
            print("Could not apply license:", e)
    else:
        print("No license file installed")

    # Build the CSV header. The local Unix timestamp is stored first,
    # followed by all requested Tobii gaze-data fields.
    header = []
    header.append('Timestamp Unix')

    for i in gaze_stuff:
        header.append(i[0])

    # Open the output file once and keep it open for the entire recording.
    csv_file = open(save_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)

    # Write column names before gaze-data samples are recorded.
    writer.writerow(header)

    print("Writing minimal gaze data to:", save_path)

    # Count callback invocations so the file can periodically be flushed.
    count = 0

    def gaze_callback(g):
        """Write one gaze-data sample received from the Tobii SDK.

        Args:
            g: Dictionary containing a single gaze-data sample. Keys correspond
                to the fields requested in ``gaze_stuff``.

        Returns:
            None.
        """
        nonlocal count

        # Create one CSV row for the current gaze sample.
        row = []

        # Record the system Unix timestamp at the moment the callback runs.
        row.append(time.time())

        # Extract each configured gaze-data field from the SDK dictionary.
        for s in gaze_stuff:
            d = g[s[0]]

            # Coordinate values returned by the SDK are tuples. They are
            # converted to lists before being passed to the CSV writer.
            if isinstance(d, tuple):
                row.append(list(d))
                # print(d)
            else:
                row.append(d)

        # print(row)

        # Write the complete gaze sample to the CSV file.
        writer.writerow(row)

        # Periodically flush buffered data to disk. This reduces the amount
        # of unwritten data that could be lost if recording is interrupted.
        if count % 200 == 0:
            csv_file.flush()

        count += 1

    # Subscribe the callback to Tobii gaze-data events.
    # ``as_dictionary=True`` ensures each sample is supplied as a dictionary.
    tracker.subscribe_to(
        tr.EYETRACKER_GAZE_DATA,
        gaze_callback,
        as_dictionary=True
    )

    print(
        "Eye tracking recording started. duration_seconds =",
        duration_seconds
    )
    print(
        "Press CTRL+C in this process to stop "
        "(if running standalone)."
    )

    # Store the recording start time for optional duration-based stopping.
    start_time = time.time()

    try:
        # Continue recording until the external stop event is set.
        while not stop_event.is_set():
            # Avoid continuously polling the stop condition at full CPU usage.
            time.sleep(0.2)

            # If a maximum recording duration was supplied, stop when it has
            # elapsed.
            if duration_seconds is not None:
                if (time.time() - start_time) >= duration_seconds:
                    print("Eye tracking: duration reached, stopping.")
                    break

    except KeyboardInterrupt:
        # Allow standalone recordings to be terminated with Ctrl+C.
        print("Eye tracking: KeyboardInterrupt, stopping.")

    finally:
        # Cleanup must occur regardless of whether recording ended normally,
        # reached its duration limit, or was interrupted.
        print("Eye tracking: unsubscribing and closing CSV.")

        # Measure how long the unsubscribe operation takes.
        first = time.time()

        # Stop the SDK from sending additional gaze-data callbacks.
        tracker.unsubscribe_from(
            tr.EYETRACKER_GAZE_DATA,
            gaze_callback
        )

        print(time.time() - first)

        # Close the CSV file so all remaining buffered data is written.
        csv_file.close()

        print("Eye tracking CSV saved:", save_path)


# Run a standalone recording when this file is executed directly rather than
# imported as a module.
if __name__ == "__main__":
    record_eyetracking_to_csv(
        duration_seconds=None,
        output_file="gaze_recording.csv",
        license_file="licenseFile",
        save_dir=""
    )