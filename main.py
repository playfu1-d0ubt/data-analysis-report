import pandas as pd
import matplotlib.pyplot as plt
import os

os.makedirs("charts", exist_ok=True)

imu_names = ["humerus", "radius", "carpus", "digitus"]

imus = {}
for name in imu_names:
    imus[name] = pd.read_csv(f"sample_data/{name}.csv")

robot = pd.read_csv("sample_data/robot-triangle-150.csv")

quat_cols = ["QUATERNION_0", "QUATERNION_1", "QUATERNION_2", "QUATERNION_3"]

for name in imu_names:
    df = imus[name].drop(columns=["MAC", "IMU"] + quat_cols)
    df["t"] = (df["TIME"] - df["TIME"].iloc[0]) / 1e6   # seconds from start
    imus[name] = df

print("\nData quality")
for name, df in imus.items():
    dt = df["t"].diff().dropna()
    missing = (df["INDEX"].diff().dropna() > 1).sum()
    print(f"{name}: {len(df)} rows, {df['t'].iloc[-1]:.1f}s long, "
          f"{1 / dt.mean():.1f} Hz, biggest gap {dt.max() * 1000:.0f} ms, "
          f"{missing} jumps in INDEX")

adxl_cols = ["ACCEL_ADXL355_0", "ACCEL_ADXL355_1", "ACCEL_ADXL355_2"]
bmi_cols = ["ACCEL_BMI160_0", "ACCEL_BMI160_1", "ACCEL_BMI160_2"]

print("\nAccelerometer agreement")
for name, df in imus.items():
    adxl_mag = (df[adxl_cols] ** 2).sum(axis=1) ** 0.5
    bmi_mag = (df[bmi_cols] ** 2).sum(axis=1) ** 0.5
    corr = adxl_mag.corr(bmi_mag)
    print(f"{name}: ADXL355 avg {adxl_mag.mean():.2f}, BMI160 avg {bmi_mag.mean():.2f}, "
          f"difference {bmi_mag.mean() - adxl_mag.mean():+.2f}, correlation {corr:.3f}")

gyro_cols = ["GYRO_0", "GYRO_1", "GYRO_2"]

print("\nHow much each segment moves")
for name, df in imus.items():
    adxl_mag = (df[adxl_cols] ** 2).sum(axis=1) ** 0.5
    gyro_mag = (df[gyro_cols] ** 2).sum(axis=1) ** 0.5
    print(f"{name}: accel spread {adxl_mag.std():.3f}, "
          f"avg gyro {gyro_mag.mean():.3f}, max gyro {gyro_mag.max():.3f}")

fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
for ax, name in zip(axes, ["humerus", "radius"]):
    df = imus[name]
    ax.plot(df["t"], (df[adxl_cols] ** 2).sum(axis=1) ** 0.5, label="ADXL355", linewidth=0.8)
    ax.plot(df["t"], (df[bmi_cols] ** 2).sum(axis=1) ** 0.5, label="BMI160", linewidth=0.8)
    ax.set_title(f"{name}: acceleration magnitude")
    ax.set_ylabel("m/s²")
    ax.legend()
axes[-1].set_xlabel("Time (s)")
fig.tight_layout()
fig.savefig("charts/accel_agreement.png", dpi=150)
print("Saved charts/accel_agreement.png")

print("\nSpike check")
for name, df in imus.items():
    adxl_mag = (df[adxl_cols] ** 2).sum(axis=1) ** 0.5
    bmi_mag = (df[bmi_cols] ** 2).sum(axis=1) ** 0.5

    peak = adxl_mag.idxmax()
    print(f"{name}: ADXL355 peak {adxl_mag.max():.1f} at {df.loc[peak, 't']:.1f}s "
          f"(median {adxl_mag.median():.2f})")

    # keep only rows where both sensors are within 5 of their medians
    calm = ((adxl_mag - adxl_mag.median()).abs() < 5) & ((bmi_mag - bmi_mag.median()).abs() < 5)
    print(f"   removed {(~calm).sum()} rows; correlation {adxl_mag.corr(bmi_mag):.3f} "
          f"-> {adxl_mag[calm].corr(bmi_mag[calm]):.3f}; "
          f"ADXL355 spread {adxl_mag.std():.3f} -> {adxl_mag[calm].std():.3f}")

print("\nSmoothed agreement and timing offset")
for name, df in imus.items():
    adxl_mag = (df[adxl_cols] ** 2).sum(axis=1) ** 0.5
    bmi_mag = (df[bmi_cols] ** 2).sum(axis=1) ** 0.5

    a = adxl_mag.rolling(10, center=True).mean()   # average of 10 readings = 0.1 s
    b = bmi_mag.rolling(10, center=True).mean()

    best_lag, best_corr = 0, -2
    for lag in range(-20, 21):                     # shift BMI160 by up to 20 readings
        c = a.corr(b.shift(lag))
        if c > best_corr:
            best_lag, best_corr = lag, c

    print(f"{name}: smoothed correlation {a.corr(b):.3f}; "
          f"best {best_corr:.3f} at shift {best_lag} readings ({best_lag * 10} ms)")

print("\nPer-axis comparison (smoothed)")
for name, df in imus.items():
    print(name)
    for i in range(3):
        a = df[adxl_cols[i]].rolling(10, center=True).mean()
        b = df[bmi_cols[i]].rolling(10, center=True).mean()
        print(f"   axis {i}: correlation {a.corr(b):.3f}, "
              f"average offset (BMI160 - ADXL355) {(b - a).mean():+.2f}")