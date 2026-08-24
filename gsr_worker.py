import time
import os
import csv
import math
from collections import deque
from serial import Serial
import numpy as np
from pyshimmer import (
    ShimmerBluetooth,
    DEFAULT_BAUDRATE,
    DataPacket,
    EChannelType,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Serial port used by the Shimmer GSR device.
SERIAL_PORT_GSR = "COM6"

# Default baud rate defined by the pyshimmer package.
BAUD = DEFAULT_BAUDRATE

# Default filename for recorded GSR data.
CSV_FILENAME_GSR = "gsr_record.csv"


# ---------------------------------------------------------------------------
# GSR conversion constants
# ---------------------------------------------------------------------------

# Feedback resistance values used by the Shimmer GSR sensor.
#
# The Shimmer GSR raw signal contains a range identifier that selects one
# of these resistor values. The selected resistance is required when
# converting the raw ADC value into skin resistance.
RF_TABLE = {
    0: 40200.0,
    1: 287000.0,
    2: 1_000_000.0,
    3: 3_300_000.0,
}

def decode_gsr_raw(raw: int) -> tuple[int, int]:
    """Decode a Shimmer GSR raw value into ADC and range components.

    The raw GSR value contains both the 12-bit ADC measurement and a
    two-bit resistance-range identifier.

    Args:
        raw: Raw integer value received from the Shimmer GSR channel.

    Returns:
        A tuple containing:
            - The 12-bit ADC value.
            - The resistance range identifier.
    """
    # Ensure the raw value is represented as a Python integer before applying
    # bitwise operations.
    raw_int = int(raw)

    # The lower 12 bits contain the ADC measurement.
    adc_12 = raw_int & 0x0FFF

    # Bits 14 and 15 contain the GSR resistance-range identifier.
    range_id = (raw_int >> 14) & 0x03

    return adc_12, range_id


def gsr_raw_to_resistance_ohm(raw: float | int) -> float:
    """Convert a raw Shimmer GSR measurement to resistance in ohms.

    Args:
        raw: Raw GSR value obtained from the Shimmer device.

    Returns:
        Estimated skin resistance in ohms. ``math.nan`` is returned when
        the input is invalid or when a valid resistance cannot be calculated.
    """
    # Missing or NaN input cannot be converted to a meaningful resistance.
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return math.nan

    # Decode the ADC value and resistor range embedded in the raw sample.
    adc_12, range_id = decode_gsr_raw(raw)

    # Retrieve the feedback resistor associated with the encoded range.
    Rf = RF_TABLE.get(range_id)

    if Rf is None:
        return math.nan

    # Convert the 12-bit ADC count to voltage.
    v_per_bit = 3.0 / 4095.0
    v_adc = adc_12 * v_per_bit

    # Reference voltage used in the resistance calculation.
    v_ref = 0.5

    # Rearranged voltage-divider relationship used to estimate resistance.
    denom = (v_adc / v_ref) - 1.0

    # A non-positive denominator would not produce a valid resistance.
    if denom <= 0:
        return math.nan

    Rs = Rf / denom

    return Rs


def resistance_to_conductance_uS(Rs_ohm: float) -> float:
    """Convert resistance in ohms to conductance in microsiemens.

    Args:
        Rs_ohm: Skin resistance in ohms.

    Returns:
        Skin conductance in microsiemens. ``math.nan`` is returned when the
        supplied resistance is non-finite or non-positive.
    """
    # Conductance cannot be calculated for invalid or non-positive resistance.
    if not math.isfinite(Rs_ohm) or Rs_ohm <= 0:
        return math.nan

    # Convert Siemens to microsiemens by multiplying by 1e6.
    return 1e6 / Rs_ohm


class ShimmerGSRStreamer:
    """Manage streaming of GSR data from a Shimmer Bluetooth device.

    The class owns the serial connection and Shimmer device instance,
    receives asynchronous packets through a callback, converts raw GSR
    measurements to resistance and conductance, and stores processed samples
    in an internal queue until they are retrieved by ``get_samples()``.
    """

    def __init__(self, port: str, baud: int = BAUD):
        """Initialize the Shimmer GSR streamer.

        Args:
            port: Serial port associated with the Shimmer device.
            baud: Serial communication baud rate.
        """
        # Open the serial connection used by the Shimmer Bluetooth interface.
        self.ser = Serial(port, baud, timeout=1)

        # Create the pyshimmer device wrapper around the serial connection.
        self.dev = ShimmerBluetooth(self.ser)

        # Queue containing processed GSR samples waiting to be consumed.
        self._q = deque()

        # Internal state indicating whether streaming has been started.
        self._running = False

        # Tracks whether the first data packet has been received.
        self._first_packet_seen = False

    def _on_packet(self, pkt: DataPacket):
        """Process one data packet received from the Shimmer device.

        Args:
            pkt: Data packet supplied by the pyshimmer streaming callback.

        Returns:
            None.
        """
        # Use the system Unix timestamp as the timestamp for this packet.
        now = time.time()

        # Perform one-time handling when the first packet arrives.
        if not self._first_packet_seen:
            self._first_packet_seen = True

            try:
                # self.ser.timeout = 1.0
                print("[GSR] First packet received")

            except Exception as e:
                print("[GSR] Could not change serial timeout:", e)

        def safe(ch):
            """Safely retrieve a channel value from the packet.

            Args:
                ch: Shimmer channel identifier.

            Returns:
                The channel value, or ``None`` if it cannot be retrieved.
            """
            try:
                return pkt[ch]
            except Exception:
                return None

        # Retrieve the raw GSR channel from the incoming data packet.
        gsr_raw_val = safe(EChannelType.GSR_RAW)

        def as_arr(x):
            """Convert a packet value to a NumPy array.

            Args:
                x: Scalar, sequence, NumPy array, or ``None``.

            Returns:
                NumPy array containing the supplied value or values.
            """
            # Represent missing data using NaN so downstream numerical
            # processing can proceed consistently.
            if x is None:
                return np.array([math.nan])

            # Preserve sequences as arrays.
            if isinstance(x, (list, tuple, np.ndarray)):
                return np.asarray(x)

            # Wrap scalar values in a one-element array.
            return np.array([x])

        # Normalize the raw GSR value into array form.
        raw_arr = as_arr(gsr_raw_val)

        # Compute resistance for every raw GSR value in the packet.
        res_arr = np.array(
            [gsr_raw_to_resistance_ohm(v) for v in raw_arr],
            dtype=float
        )

        # Compute conductance from the calculated resistance values.
        cond_arr = np.array(
            [resistance_to_conductance_uS(R) for R in res_arr],
            dtype=float
        )

        # Number of GSR samples represented by this packet.
        n = len(raw_arr)

        # Add each processed sample to the internal queue.
        for i in range(n):
            raw = raw_arr[i]
            Rs = res_arr[i]
            G = cond_arr[i]

            self._q.append(
                (
                    now,
                    None
                    if (isinstance(raw, float) and math.isnan(raw))
                    else float(raw),
                    None
                    if (not math.isfinite(Rs))
                    else float(Rs),
                    None
                    if (not math.isfinite(G))
                    else float(G),
                )
            )

    def start(self):
        """Initialize the Shimmer device and begin streaming GSR data."""
        # Initialize communication with the physical device.
        self.dev.initialize()

        print("GSR connected to:", self.dev.get_device_name())

        # Register the callback that processes incoming data packets.
        self.dev.add_stream_callback(self._on_packet)

        # Begin receiving data from the Shimmer device.
        self.dev.start_streaming()

        self._running = True

    def stop(self):
        """Stop streaming and close the Shimmer connection.

        Each cleanup operation is attempted independently so failure in one
        operation does not prevent the remaining cleanup steps.
        """
        self._running = False

        # Stop the device's active data stream.
        try:
            self.dev.stop_streaming()
        except Exception as e:
            print("[GSR] stop_streaming failed:", e)

        # Shut down the pyshimmer device connection.
        try:
            self.dev.shutdown()
        except Exception as e:
            print("[GSR] shutdown failed:", e)

        # Close the underlying serial connection.
        try:
            self.ser.close()
        except Exception as e:
            print("[GSR] serial close failed:", e)

    def get_samples(self, max_items=2048):
        """Retrieve queued GSR samples.

        Args:
            max_items: Maximum number of queued samples to retrieve.

        Returns:
            List of samples removed from the internal queue. Each sample
            contains timestamp, raw GSR value, resistance, and conductance.
        """
        items = []

        # Remove samples from the queue until either the queue is empty or the
        # requested maximum number of items has been reached.
        for _ in range(max_items):
            if not self._q:
                break

            items.append(self._q.popleft())

        return items


def record_gsr_to_csv(
    duration_seconds: float | None = None,
    save_dir: str | None = None,
    stop_event=None
):
    """Record Shimmer GSR measurements to a CSV file.

    The function creates a Shimmer GSR streamer, receives raw GSR samples,
    converts them to resistance and conductance, and writes the resulting
    measurements to a semicolon-delimited CSV file.

    Recording continues until ``stop_event`` is set or the optional recording
    duration has elapsed. If no packets are received for more than three
    seconds, the serial connection and streamer are recreated.

    Args:
        duration_seconds: Optional maximum recording duration in seconds.
            If ``None``, no duration-based stopping condition is used.
        save_dir: Optional directory in which the CSV file should be stored.
            If ``None``, the default filename is used in the current working
            directory.
        stop_event: Event-like object exposing an ``is_set()`` method.
            Recording stops when this event becomes set.

    Returns:
        None.
    """
    # Build the output path using the supplied directory when available.
    if save_dir != None:
        save_path = os.path.join(save_dir, CSV_FILENAME_GSR)
    else:
        save_path = CSV_FILENAME_GSR

    streamer = None

    print(f"[GSR] Recording to {save_path}...")

    # Create the initial Shimmer streaming connection.
    streamer = ShimmerGSRStreamer(SERIAL_PORT_GSR, BAUD)

    # Open the output CSV file and configure semicolon-separated output.
    csv_file = open(save_path, "w", newline="")
    writer = csv.writer(csv_file, delimiter=';')

    # Write the CSV column names before recording samples.
    writer.writerow(
        [
            "timestamp_s",
            "t_rel_s",
            "gsr_raw",
            "gsr_res_ohm",
            "gsr_cond_uS",
        ]
    )


    # Timestamp of the first recorded GSR sample. This is used to calculate
    # relative sample timestamps.
    t0 = None

    # Wall-clock time at which the recording session begins.
    t_start = time.time()


    try:
        # Track the most recent time at which data was successfully retrieved.
        # This is used to detect a stalled GSR stream.
        last_packet_time = time.time()

        # Initialize the device and begin receiving samples.
        streamer.start()

        # Continue recording until the externally supplied stop event is set.
        while not stop_event.is_set():

            # Stop when the requested recording duration has elapsed.
            if (
                duration_seconds is not None
                and (time.time() - t_start) >= duration_seconds
            ):
                print("[GSR] Duration reached, stopping.")
                break

            # Retrieve any samples currently waiting in the streamer's queue.
            samples = streamer.get_samples()

            if samples:
                # Fresh samples indicate that the device is still streaming.
                last_packet_time = time.time()

            else:
                # If no data has arrived for more than three seconds, recreate
                # the streamer in an attempt to restore the connection.
                if time.time() - last_packet_time > 3:
                    print("[GSR] stopping old streamer")

                    # try:
                    #     streamer.stop()
                    # except Exception as e:
                    #     print("[GSR] stop failed:", e)

                    # Close the existing serial connection before recreating
                    # the streamer.
                    try:
                        streamer.ser.close()
                    except:
                        pass

                    streamer = None

                    # Delay before attempting to reconnect.
                    time.sleep(2)

                    print("[GSR] creating new streamer")

                    # Create a fresh Shimmer connection.
                    streamer = ShimmerGSRStreamer(
                        SERIAL_PORT_GSR,
                        BAUD
                    )

                    print("[GSR] starting new streamer")

                    # Initialize the new device connection and resume streaming.
                    streamer.start()

                    print("[GSR] restart complete")

                    # Reset the timeout reference after reconnection.
                    last_packet_time = time.time()

                    print("streamer started")

            # Write each retrieved GSR sample to the CSV file.
            for ts, raw, res, cond in samples:
                # Use the first sample timestamp as the relative-time origin.
                if t0 is None:
                    t0 = ts

                t_rel = ts - t0

                # Empty fields are written for unavailable measurements.
                writer.writerow(
                    [
                        f"{ts:.6f}",
                        f"{t_rel:.6f}",
                        "" if raw is None else f"{raw:.6f}",
                        "" if res is None else f"{res:.6f}",
                        "" if cond is None else f"{cond:.6f}",
                    ]
                )

            # Flush after each processing cycle so recently recorded samples
            # are written to disk promptly.
            csv_file.flush()

            # Brief delay to avoid continuously polling the queue at full CPU.
            time.sleep(0.02)

    except:
        # Preserve the existing behavior of treating any exception as a reason
        # to stop recording.
        print("[GSR] Stopped due to exception.")

        streamer.stop()
        csv_file.close()

    finally:
        # Attempt cleanup regardless of whether recording ended normally or
        # because an exception occurred.
        try:
            streamer.stop()
            csv_file.close()

            print(f"[GSR] Saved to {save_path}")

        except:
            # The resources may already have been stopped or closed by the
            # exception handler above.
            print("already stopped")


# Start a standalone GSR recording when this module is executed directly.
if __name__ == "__main__":
    record_gsr_to_csv(
        duration_seconds=None,
        save_dir=""
    )