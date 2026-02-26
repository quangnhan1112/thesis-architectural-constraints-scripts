import shutil
from pathlib import Path
import pandas as pd

SOURCE = Path(r"D:\Desktop\SF100\repos")
TARGET = Path(r"D:\Desktop\thesis_dataset")
TARGET.mkdir(exist_ok=True)

folders = sorted([f for f in SOURCE.iterdir() if f.is_dir()])

mapping = []

for i, folder in enumerate(folders, start=1):
    new_id = f"sf_{str(i).zfill(3)}"
    new_path = TARGET / new_id

    shutil.copytree(folder, new_path)

    mapping.append({
        "repo_id": new_id,
        "original_name": folder.name,
        "source": "sf100"
    })

df = pd.DataFrame(mapping)
df.to_csv(TARGET / "sf100_mapping.csv", index=False)

print("SF100 prepared.")
