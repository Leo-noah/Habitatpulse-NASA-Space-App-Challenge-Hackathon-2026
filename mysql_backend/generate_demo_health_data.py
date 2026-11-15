"""Create clearly labelled simulated crew-health history for HabitatPulse UI demos.

This script DOES NOT create medical training data and must not be used to train,
validate, or claim performance for a clinical model. It creates fictional,
prototype-only check-ins so the Crew Check-ins, Evidence, Reports, and trend
charts have enough rows to demonstrate their interface.

Run from mysql_backend after setting MYSQL_PASSWORD in this terminal:
  python generate_demo_health_data.py --days 90

It creates at most one generated check-in per crew member per day/time, so it
can be run again without duplicating those fixed simulated records.
"""

from __future__ import annotations

import argparse
import math
import random
from datetime import date, datetime, time, timedelta

from db_config import get_connection


MARKER = "SIMULATED_DEMO_HEALTH_V1"


def scalar(cursor, query: str, values: tuple[object, ...] = ()) -> int | None:
    cursor.execute(query, values)
    row = cursor.fetchone()
    return int(row[0]) if row else None


def get_reference_ids(cursor) -> tuple[list[tuple[int, str]], int]:
    cursor.execute("SELECT id, crew_code FROM crew_members WHERE active = TRUE ORDER BY crew_code")
    crew = [(int(row[0]), str(row[1])) for row in cursor.fetchall()]
    if not crew:
        raise RuntimeError("No active crew members found. Run sample_data.sql first.")

    module_id = scalar(cursor, "SELECT id FROM habitat_modules WHERE module_code = 'HAB-MODULE-B' LIMIT 1")
    if module_id is None:
        raise RuntimeError("HAB-MODULE-B was not found. Run sample_data.sql first.")
    return crew, module_id


def checkin_exists(cursor, crew_id: int, recorded_at: datetime) -> int | None:
    return scalar(
        cursor,
        "SELECT id FROM checkins WHERE crew_id = %s AND recorded_at_utc = %s AND notes LIKE %s LIMIT 1",
        (crew_id, recorded_at, f"{MARKER}%"),
    )


def add_checkin(cursor, crew_id: int, crew_code: str, module_id: int, recorded_at: datetime, day_index: int, rng: random.Random) -> tuple[int, bool]:
    existing = checkin_exists(cursor, crew_id, recorded_at)
    if existing is not None:
        return existing, False

    weekly = math.sin((day_index / 7) * math.tau)
    sleep_hours = round(max(4.5, min(9.0, 7.25 + 0.45 * weekly + rng.gauss(0, 0.45))), 2)
    fatigue_score = 1 if sleep_hours >= 6.4 else 2
    fatigue = "none" if fatigue_score == 1 and rng.random() > 0.30 else "mild"
    if sleep_hours < 5.7 and rng.random() < 0.35:
        fatigue = "moderate"

    wellbeing = 4 if fatigue in {"none", "mild"} else 3
    stress = max(1, min(5, round(2.5 + rng.gauss(0, 0.7))))
    fluid = int(max(900, min(3000, 1900 + rng.gauss(0, 260))))
    activity = "normal" if rng.random() < 0.78 else ("high" if rng.random() < 0.5 else "low")
    sleep_quality = "good" if sleep_hours >= 7.3 else ("fair" if sleep_hours >= 6 else "poor")

    cursor.execute(
        """INSERT INTO checkins (
             crew_id, recorded_at_utc, module_id, current_mission_task, recent_task_completed, notes,
             overall_wellbeing, fatigue_level, mood_stress_level, sleep_hours, sleep_quality,
             fluid_intake_ml, appetite, activity_level, exercise_completed, medication_taken
           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            crew_id, recorded_at, module_id, "Simulated scheduled maintenance", "Simulated daily exercise",
            f"{MARKER}; fictional UI-chart record for {crew_code}. Not clinical or real crew data.",
            wellbeing, fatigue, stress, sleep_hours, sleep_quality, fluid, "normal", activity,
            activity != "low", "not_applicable",
        ),
    )
    checkin_id = int(cursor.lastrowid)

    heart_rate = round(max(52, min(104, 70 + (3 if fatigue == "moderate" else 0) + rng.gauss(0, 5))), 1)
    spo2 = round(max(95.5, min(100, 98.2 + rng.gauss(0, 0.45))), 1)
    respiratory_rate = round(max(10, min(22, 15 + rng.gauss(0, 1.3))), 1)
    body_temperature = round(max(36.0, min(37.6, 36.75 + rng.gauss(0, 0.22))), 2)
    cursor.execute(
        """INSERT INTO vital_signs (
             checkin_id, heart_rate_bpm, spo2_percent, respiratory_rate_bpm,
             body_temperature_c, blood_pressure_systolic, blood_pressure_diastolic, hrv_ms, weight_kg
           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (checkin_id, heart_rate, spo2, respiratory_rate, body_temperature, 118 + rng.randint(-7, 7), 76 + rng.randint(-5, 5), round(45 + rng.gauss(0, 8), 1), round(71 + rng.gauss(0, 0.25), 1)),
    )

    cursor.execute(
        """INSERT INTO safety_reviews (
             checkin_id, severe_chest_discomfort, severe_breathing_difficulty, loss_of_consciousness,
             sudden_neurological_change, sudden_severe_headache, rapidly_worsening_symptoms,
             urgent_human_review_required
           ) VALUES (%s, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE)""",
        (checkin_id,),
    )
    return checkin_id, True


def add_optional_symptoms_and_report(cursor, checkin_id: int, crew_code: str, recorded_at: datetime, rng: random.Random) -> tuple[int, int]:
    """Add a limited number of non-diagnostic symptom records for graph/filter demos."""
    symptoms_added = 0
    reports_added = 0
    symptom_name: str | None = None
    severity = 0
    if rng.random() < 0.16:
        symptom_name = rng.choice(["headache", "fatigue", "sleep_difficulty", "muscle_or_joint_pain"])
        severity = rng.randint(1, 4)

    if symptom_name is None:
        return symptoms_added, reports_added

    onset = recorded_at - timedelta(minutes=rng.randint(30, 240))
    cursor.execute(
        """INSERT INTO symptom_records (
             checkin_id, symptom_name, severity_0_to_10, onset_at_utc, onset_status,
             duration_minutes, duration_status, symptom_pattern, progression,
             mission_task_effect, similar_episode, action_or_medication_taken, note
           ) VALUES (%s, %s, %s, %s, 'known', %s, 'ongoing', 'constant', 'stable',
                     'some_difficulty', 'unknown', 'No treatment recommendation generated.', %s)""",
        (checkin_id, symptom_name, severity, onset, rng.randint(30, 180), f"{MARKER}; fictional symptom for UI demonstration only."),
    )
    symptom_id = int(cursor.lastrowid)
    symptoms_added += 1

    if symptom_name == "headache":
        for field, value in (("pain_location", "whole_head"), ("pain_quality", "pressure")):
            cursor.execute("INSERT INTO symptom_detail_answers (symptom_id, field_name, value_text) VALUES (%s, %s, %s)", (symptom_id, field, value))
        for field in ("light_sensitivity", "new_neurological_change", "confusion_or_impaired_consciousness"):
            cursor.execute("INSERT INTO symptom_detail_answers (symptom_id, field_name, value_boolean) VALUES (%s, %s, FALSE)", (symptom_id, field))

    report_code = f"HP-SIM-{crew_code}-{recorded_at:%Y%m%d}"
    cursor.execute(
        """INSERT INTO health_reports (
             report_code, checkin_id, workflow_status, ruleset_version, created_at_utc, medical_review_required
           ) VALUES (%s, %s, 'draft_not_clinically_reviewed', '0.1-draft', %s, FALSE)""",
        (report_code, checkin_id, recorded_at + timedelta(minutes=2)),
    )
    report_id = int(cursor.lastrowid)
    cursor.execute(
        """INSERT INTO report_evidence (report_id, evidence_type, label, status, source_reference, note)
           VALUES (%s, 'symptom', %s, 'simulated_demo_only', 'simulated_health_generator',
                   'Fictional record. It is not a diagnosis, prediction, or clinical recommendation.')""",
        (report_id, f"{symptom_name} recorded"),
    )
    cursor.execute("INSERT INTO outbox (entity_type, entity_id, status) VALUES ('health_report', %s, 'pending_sync')", (report_id,))
    reports_added += 1
    return symptoms_added, reports_added


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate simulated HabitatPulse health-chart data")
    parser.add_argument("--days", type=int, default=90, help="Number of daily check-ins per active crew member (default: 90)")
    parser.add_argument("--seed", type=int, default=20261114, help="Random seed for repeatable prototype data")
    arguments = parser.parse_args()
    if not 7 <= arguments.days <= 365:
        raise SystemExit("--days must be between 7 and 365")

    rng = random.Random(arguments.seed)
    inserted_checkins = inserted_symptoms = inserted_reports = skipped = 0
    start_day = date.today() - timedelta(days=arguments.days - 1)

    with get_connection() as connection:
        cursor = connection.cursor()
        crew, module_id = get_reference_ids(cursor)

        for day_index in range(arguments.days):
            current_day = start_day + timedelta(days=day_index)
            for crew_index, (crew_id, crew_code) in enumerate(crew):
                recorded_at = datetime.combine(current_day, time(6 + (crew_index % 2), 20 + crew_index * 7))
                checkin_id, created = add_checkin(cursor, crew_id, crew_code, module_id, recorded_at, day_index, rng)
                if not created:
                    skipped += 1
                    continue
                inserted_checkins += 1
                symptoms, reports = add_optional_symptoms_and_report(cursor, checkin_id, crew_code, recorded_at, rng)
                inserted_symptoms += symptoms
                inserted_reports += reports
                cursor.execute("INSERT INTO outbox (entity_type, entity_id, status) VALUES ('checkin', %s, 'pending_sync')", (checkin_id,))

        connection.commit()

    print("Simulated health demo data complete.")
    print(f"Created check-ins: {inserted_checkins}")
    print(f"Created vital-sign rows: {inserted_checkins}")
    print(f"Created symptom rows: {inserted_symptoms}")
    print(f"Created draft report rows: {inserted_reports}")
    print(f"Skipped existing generated check-ins: {skipped}")
    print("All generated check-ins contain SIMULATED_DEMO_HEALTH_V1 in notes.")


if __name__ == "__main__":
    main()
