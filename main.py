"""Analysis of robot-arm IMU data (OpenAXES dataset).

Four IMUs are strapped to the segments of a UR5 robot arm. Each one has two
accelerometers (ADXL355 and BMI160) and a gyroscope. This script checks the
data quality, compares the two accelerometers, and shows that their apparent
disagreement comes from per-axis calibration offsets.

Put the CSV files in sample_data/ and run: python main.py
"""

import os

import matplotlib.pyplot as plt
import pandas as pd

DATA_DIR = "sample_data"
CHART_DIR = "charts"
IMU_NAMES = ["humerus", "radius", "carpus", "digitus"]  # named after arm bones

QUAT_COLS = ["QUATERNION_0", "QUATERNION_1", "QUATERNION_2", "QUATERNION_3"]
ADXL_COLS = ["ACCEL_ADXL355_0", "ACCEL_ADXL355_1", "ACCEL_ADXL355_2"]
BMI_COLS = ["ACCEL_BMI160_0", "ACCEL_BMI160_1", "ACCEL_BMI160_2"]
GYRO_COLS = ["GYRO_0", "GYRO_1", "GYRO_2"]

SMOOTH_WINDOW = 10   # readings to average: 0.1 s at 100 Hz
SPIKE_LIMIT = 5      # how far from the median counts as a spike (m/s^2)


def magnitude(readings):
    """Total strength of a 3-axis reading, ignoring direction."""
    return (readings ** 2).sum(axis=1) ** 0.5


def load_imus():
    """Load each IMU file, drop unusable columns, add a time-in-seconds column."""
    imus = {}
    for name in IMU_NAMES:
        df = pd.read_csv(f"{DATA_DIR}/{name}.csv")
        # the quaternions are zero in every row, so they carry no information
        df = df.drop(columns=["MAC", "IMU"] + QUAT_COLS)
        df["t"] = (df["TIME"] - df["TIME"].iloc[0]) / 1e6  # microseconds -> seconds
        imus[name] = df
    return imus


def smoothed_accels(df):
    """Average each axis over SMOOTH_WINDOW readings, for both accelerometers.

    Smoothing each axis first and taking the magnitude afterwards removes more
    noise than the other way round. Columns are renamed 0, 1, 2 so the two
    sensors line up.
    """
    a = df[ADXL_COLS].rolling(SMOOTH_WINDOW, center=True).mean()
    b = df[BMI_COLS].rolling(SMOOTH_WINDOW, center=True).mean()
    a.columns = b.columns = [0, 1, 2]
    return a, b


def remove_offset(a, b):
    """Shift the BMI160 readings by their average per-axis difference from the ADXL355."""
    return b - (b - a).mean()

def check_data_quality(imus):
    print("\nData quality")
    for name, df in imus.items():
        dt = df["t"].diff().dropna()
        missing = (df["INDEX"].diff().dropna() > 1).sum()
        print(f"{name}: {len(df)} rows, {df['t'].iloc[-1]:.1f}s long, "
              f"{1 / dt.mean():.1f} Hz, biggest gap {dt.max() * 1000:.0f} ms, "
              f"{missing} jumps in INDEX")


def compare_raw_accels(imus):
    print("\nAccelerometer agreement")
    for name, df in imus.items():
        adxl_mag = magnitude(df[ADXL_COLS])
        bmi_mag = magnitude(df[BMI_COLS])
        print(f"{name}: ADXL355 avg {adxl_mag.mean():.2f}, BMI160 avg {bmi_mag.mean():.2f}, "
              f"difference {bmi_mag.mean() - adxl_mag.mean():+.2f}, "
              f"correlation {adxl_mag.corr(bmi_mag):.3f}")


def movement_summary(imus):
    print("\nHow much each segment moves")
    for name, df in imus.items():
        gyro_mag = magnitude(df[GYRO_COLS])
        print(f"{name}: accel spread {magnitude(df[ADXL_COLS]).std():.3f}, "
              f"avg gyro {gyro_mag.mean():.3f}, max gyro {gyro_mag.max():.3f}")

def find_spikes(imus):
    print("\nSpike check")
    for name, df in imus.items():
        adxl_mag = magnitude(df[ADXL_COLS])
        bmi_mag = magnitude(df[BMI_COLS])

        peak = adxl_mag.idxmax()
        print(f"{name}: ADXL355 peak {adxl_mag.max():.1f} at {df.loc[peak, 't']:.1f}s "
              f"(median {adxl_mag.median():.2f})")

        # keep only rows where both sensors are close to their medians
        calm = (((adxl_mag - adxl_mag.median()).abs() < SPIKE_LIMIT)
                & ((bmi_mag - bmi_mag.median()).abs() < SPIKE_LIMIT))
        print(f"   removed {(~calm).sum()} rows; "
              f"correlation {adxl_mag.corr(bmi_mag):.3f} -> {adxl_mag[calm].corr(bmi_mag[calm]):.3f}; "
              f"ADXL355 spread {adxl_mag.std():.3f} -> {adxl_mag[calm].std():.3f}")


def smoothed_agreement(imus):
    print("\nSmoothed agreement and timing offset")
    for name, df in imus.items():
        a = magnitude(df[ADXL_COLS]).rolling(SMOOTH_WINDOW, center=True).mean()
        b = magnitude(df[BMI_COLS]).rolling(SMOOTH_WINDOW, center=True).mean()

        best_lag, best_corr = 0, -2
        for lag in range(-20, 21):  # shift the BMI160 by up to 20 readings
            c = a.corr(b.shift(lag))
            if c > best_corr:
                best_lag, best_corr = lag, c

        print(f"{name}: smoothed correlation {a.corr(b):.3f}; "
              f"best {best_corr:.3f} at shift {best_lag} readings ({best_lag * 10} ms)")

def per_axis_comparison(imus):
    print("\nPer-axis comparison (smoothed)")
    for name, df in imus.items():
        a, b = smoothed_accels(df)
        print(name)
        for i in range(3):
            print(f"   axis {i}: correlation {a[i].corr(b[i]):.3f}, "
                  f"average offset (BMI160 - ADXL355) {(b[i] - a[i]).mean():+.2f}")


def offset_correction(imus):
    print("\nMagnitude agreement before/after removing per-axis offset (smoothed)")
    for name, df in imus.items():
        a, b = smoothed_accels(df)
        b_fixed = remove_offset(a, b)

        a_mag, b_mag, fixed_mag = magnitude(a), magnitude(b), magnitude(b_fixed)
        print(f"{name}: correlation {a_mag.corr(b_mag):.3f} -> {a_mag.corr(fixed_mag):.3f}; "
              f"average difference {(b_mag - a_mag).mean():+.2f} -> {(fixed_mag - a_mag).mean():+.2f}")

def plot_raw_agreement(imus):
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for ax, name in zip(axes, ["humerus", "radius"]):
        df = imus[name]
        ax.plot(df["t"], magnitude(df[ADXL_COLS]), label="ADXL355", linewidth=0.8)
        ax.plot(df["t"], magnitude(df[BMI_COLS]), label="BMI160", linewidth=0.8)
        ax.set_title(f"{name}: acceleration magnitude")
        ax.set_ylabel("m/s²")
        ax.legend()
    axes[-1].set_xlabel("Time (s)")
    fig.tight_layout()
    fig.savefig(f"{CHART_DIR}/accel_agreement.png", dpi=150)
    print(f"Saved {CHART_DIR}/accel_agreement.png")


def plot_offset_fix(imus, name="radius"):
    df = imus[name]
    a, b = smoothed_accels(df)
    panels = [("Before offset correction", b), ("After offset correction", remove_offset(a, b))]

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for ax, (title, bmi) in zip(axes, panels):
        ax.plot(df["t"], magnitude(a), label="ADXL355")
        ax.plot(df["t"], magnitude(bmi), label="BMI160")
        ax.set_title(f"{name}: {title}")
        ax.set_ylabel("m/s²")
        ax.legend()
    axes[-1].set_xlabel("Time (s)")
    fig.tight_layout()
    fig.savefig(f"{CHART_DIR}/{name}_before_after.png", dpi=150)
    print(f"Saved {CHART_DIR}/{name}_before_after.png")


def main():
    os.makedirs(CHART_DIR, exist_ok=True)
    imus = load_imus()

    check_data_quality(imus)
    compare_raw_accels(imus)
    movement_summary(imus)
    find_spikes(imus)
    smoothed_agreement(imus)
    per_axis_comparison(imus)
    offset_correction(imus)

    plot_raw_agreement(imus)
    plot_offset_fix(imus)


if __name__ == "__main__":
    main()