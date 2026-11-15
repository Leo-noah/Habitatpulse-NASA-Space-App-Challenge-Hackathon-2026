"""Import real or clearly-labelled replay CSV readings into MySQL.

This is a one-time / repeatable importer. It reads a CSV file, scores each
complete row with the already-trained local model, then stores the resulting
records in `environment_records`. The React dashboard never invents readings.

Example:
  python import_environment_csv.py "E:\\Nasa space App\\RR-28_EDA_Telemetry_data.csv" \
    --module HAB-MODULE-B --source RR-28-EDA --historical-replay
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from db_config import get_connection


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT if (ROOT / "training_outputs").exists() else ROOT.parent
MODEL_PATH = PROJECT_ROOT / "training_outputs" / "environment_iforest_v01.joblib"


def get_or_create(cursor, table: str, code_column: str, code: str, *, is_simulated: bool = False) -> int:
    cursor.execute(f"SELECT id FROM {table} WHERE {code_column} = %s", (code,))
    found = cursor.fetchone()
    if found:
        return int(found[0])
    if table == "missions":
        cursor.execute("INSERT INTO missions (mission_code, mission_name) VALUES (%s, %s)", (code, "HabitatPulse prototype mission"))
    elif table == "habitat_modules":
        mission_id = get_or_create(cursor, "missions", "mission_code", "HABITATPULSE-DEMO")
        cursor.execute("INSERT INTO habitat_modules (module_code, module_name, mission_id) VALUES (%s, %s, %s)", (code, code, mission_id))
    elif table == "sensor_sources":
        cursor.execute("INSERT INTO sensor_sources (source_code, source_name, is_simulated) VALUES (%s, %s, %s)", (code, code, is_simulated))
    else:
        raise ValueError("Unsupported lookup table")
    return int(cursor.lastrowid)


def main() -> None:
    parser = argparse.ArgumentParser(description="Store environment CSV rows in HabitatPulse MySQL.")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--module", required=True, help="Example: HAB-MODULE-B")
    parser.add_argument("--source", required=True, help="Example: RR-28-EDA")
    parser.add_argument("--historical-replay", action="store_true", help="Label imported historical data as replay data.")
    parser.add_argument("--limit", type=int, default=2_000, help="Use a small number first for a fast demo.")
    arguments = parser.parse_args()

    if not arguments.csv_file.exists():
        raise SystemExit(f"CSV file not found: {arguments.csv_file}")
    if not MODEL_PATH.exists():
        raise SystemExit(f"Model not found: {MODEL_PATH}")

    frame = pd.read_csv(arguments.csv_file)
    required = ["Controller_Time_GMT", "Temp_degC_ISS", "RH_percent_ISS", "CO2_ppm_ISS"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise SystemExit(f"CSV is missing required columns: {', '.join(missing)}")

    frame["measured_at_utc"] = pd.to_datetime(frame["Controller_Time_GMT"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["measured_at_utc", "Temp_degC_ISS", "RH_percent_ISS", "CO2_ppm_ISS"])
    frame = frame.drop_duplicates(subset=["measured_at_utc"], keep="last").tail(arguments.limit)
    if frame.empty:
        raise SystemExit("No complete rows were found to import.")

    bundle = joblib.load(MODEL_PATH)
    features = bundle["features"]
    scores = -bundle["model"].score_samples(frame[features])
    frame["anomaly_score"] = scores
    frame["anomaly_flag"] = frame["anomaly_score"] > float(bundle["threshold"])

    with get_connection() as connection:
        cursor = connection.cursor()
        module_id = get_or_create(cursor, "habitat_modules", "module_code", arguments.module)
        source_id = get_or_create(cursor, "sensor_sources", "source_code", arguments.source, is_simulated=arguments.historical_replay)
        sql = """
            INSERT INTO environment_records (
              measured_at_utc, module_id, source_id, is_simulated,
              temperature_c, humidity_percent, co2_ppm, anomaly_score,
              anomaly_threshold, anomaly_flag, anomaly_model_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        stored = 0
        for _, row in frame.iterrows():
            timestamp = row["measured_at_utc"].to_pydatetime().astimezone(timezone.utc).replace(tzinfo=None)
            cursor.execute(sql, (
                timestamp, module_id, source_id, arguments.historical_replay,
                float(row["Temp_degC_ISS"]), float(row["RH_percent_ISS"]), float(row["CO2_ppm_ISS"]),
                float(row["anomaly_score"]), float(bundle["threshold"]), bool(row["anomaly_flag"]),
                bundle.get("model_version", "environment-iforest-v0.1"),
            ))
            stored += 1
        connection.commit()

    print(f"Imported {stored} database records from {arguments.csv_file.name}.")
    print("Historical replay is labelled in MySQL; it is not live spacecraft telemetry.")


if __name__ == "__main__":
    main()
