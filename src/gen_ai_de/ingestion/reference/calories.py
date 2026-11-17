# Install dependencies as needed:
# pip install kagglehub[pandas-datasets]
from pathlib import Path

import kagglehub
import pandas as pd
from kagglehub import KaggleDatasetAdapter

from gen_ai_de.config import get_settings

# Set the path to the file you'd like to load
file_path = "exercise_dataset.csv"

# Load the latest version
df = kagglehub.load_dataset(
    KaggleDatasetAdapter.PANDAS,
    "aadhavvignesh/calories-burned-during-exercise-and-activities",
    file_path,
    # Provide any additional arguments like
    # sql_query or pandas_kwargs. See the
    # documenation for more information:
    # https://github.com/Kaggle/kagglehub/blob/main/README.md#kaggledatasetadapterpandas
)

calories_per_kg = df[["Activity, Exercise or Sport (1 hour)", "Calories per kg"]]

print("First 5 records:", calories_per_kg.head())

file_path2 = "checkin_checkout_history_updated.csv"

# Load the latest version
df2 = kagglehub.load_dataset(
    KaggleDatasetAdapter.PANDAS,
    "mexwell/gym-check-ins-and-user-metadata",
    file_path2,
    # Provide any additional arguments like
    # sql_query or pandas_kwargs. See the
    # documenation for more information:
    # https://github.com/Kaggle/kagglehub/blob/main/README.md#kaggledatasetadapterpandas
)

calories_total = df2[["workout_type", "calories_burned"]]

print("First 5 records:", calories_total.head())

met_data = pd.read_csv(Path(__file__).parent / "met.csv", dtype={"activity_code": str})

print("First 5 records:", met_data.head())

out_dir = get_settings().data_dir / "reference"
out_dir.mkdir(parents=True, exist_ok=True)
df.to_csv(out_dir / "calories_per_kg.csv", index=False)
df2.to_csv(out_dir / "calories_total.csv", index=False)
