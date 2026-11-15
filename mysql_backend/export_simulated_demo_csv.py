"""Export only clearly-labelled HabitatPulse simulated mission demo data to CSV."""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from db_config import get_connection

OUT = Path(__file__).resolve().parent / "exports"


def value(item: object) -> object:
    if isinstance(item, datetime):
        return item.isoformat(sep=" ")
    if isinstance(item, date):
        return item.isoformat()
    return item


def export(cursor, filename: str, query: str, parameters: tuple[object, ...]) -> int:
    cursor.execute(query, parameters)
    rows = cursor.fetchall()
    columns = [item[0] for item in cursor.description]
    path = OUT / filename
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows([[value(cell) for cell in row] for row in rows])
    return len(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with get_connection() as connection:
        cursor = connection.cursor()
        environment = export(cursor, "simulated_environment_5min.csv", """
            SELECT er.measured_at_utc, hm.module_code, ss.source_code, er.is_simulated,
                   er.temperature_c, er.humidity_percent, er.co2_ppm,
                   er.anomaly_score, er.anomaly_threshold, er.anomaly_flag,
                   er.anomaly_model_version
            FROM environment_records er
            JOIN habitat_modules hm ON hm.id=er.module_id
            JOIN sensor_sources ss ON ss.id=er.source_id
            WHERE ss.source_code='SIM-HAB-5MIN' AND er.is_simulated=TRUE
            ORDER BY er.measured_at_utc
        """, ())
        health = export(cursor, "simulated_health_pmc.csv", """
            SELECT c.crew_code, ch.recorded_at_utc, hm.module_code,
                   ch.overall_wellbeing, ch.fatigue_level, ch.mood_stress_level,
                   ch.sleep_hours, ch.sleep_quality, ch.fluid_intake_ml,
                   vs.heart_rate_bpm, vs.spo2_percent, vs.respiratory_rate_bpm,
                   vs.body_temperature_c, sr.urgent_human_review_required, ch.notes
            FROM checkins ch
            JOIN crew_members c ON c.id=ch.crew_id
            JOIN habitat_modules hm ON hm.id=ch.module_id
            LEFT JOIN vital_signs vs ON vs.checkin_id=ch.id
            LEFT JOIN safety_reviews sr ON sr.checkin_id=ch.id
            WHERE ch.notes LIKE %s
            ORDER BY ch.recorded_at_utc, c.crew_code
        """, ("SIMULATED_DEMO_HEALTH_V2%",))
        cursor.close()
    print(f"simulated_environment_5min.csv: {environment:,} rows")
    print(f"simulated_health_pmc.csv: {health:,} rows")
    print(f"Saved in: {OUT}")


if __name__ == "__main__":
    main()
