import pandas as pd

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