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

print(f"robot: {len(robot)} rows")
print(robot.describe().T[["min", "max"]])