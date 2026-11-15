"""Export readable HabitatPulse MySQL tables to separate CSV files.

Run from mysql_backend after MYSQL_PASSWORD is set in this terminal:
  python export_database_to_csv.py

CSV files are written to mysql_backend/exports/. They contain only local
prototype data and are not automatically uploaded anywhere.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from db_config import get_connection


OUTPUT_DIRECTORY = Path(__file__).resolve().parent / "exports"

EXPORTS: dict[str, str] = {
    "01_missions.csv": """
        SELECT id, mission_code, mission_name, created_at_utc
        FROM missions ORDER BY id
    """,
    "02_crew_members.csv": """
        SELECT c.id, c.crew_code, c.display_name, m.mission_code, c.active, c.created_at_utc
        FROM crew_members c LEFT JOIN missions m ON m.id = c.mission_id
        ORDER BY c.id
    """,
    "03_habitat_modules.csv": """
        SELECT hm.id, hm.module_code, hm.module_name, m.mission_code
        FROM habitat_modules hm LEFT JOIN missions m ON m.id = hm.mission_id
        ORDER BY hm.id
    """,
    "04_sensor_sources.csv": """
        SELECT id, source_code, source_name, is_simulated
        FROM sensor_sources ORDER BY id
    """,
    "05_environment_records.csv": """
        SELECT er.id, er.measured_at_utc, hm.module_code, ss.source_code,
               er.is_simulated, er.temperature_c, er.humidity_percent, er.co2_ppm,
               er.anomaly_score, er.anomaly_threshold, er.anomaly_flag, er.anomaly_model_version,
               er.saved_at_utc
        FROM environment_records er
        JOIN habitat_modules hm ON hm.id = er.module_id
        JOIN sensor_sources ss ON ss.id = er.source_id
        ORDER BY er.measured_at_utc
    """,
    "06_checkins.csv": """
        SELECT ch.id, c.crew_code, c.display_name, ch.recorded_at_utc, hm.module_code,
               ch.current_mission_task, ch.recent_task_completed, ch.overall_wellbeing,
               ch.fatigue_level, ch.mood_stress_level, ch.sleep_hours, ch.sleep_quality,
               ch.fluid_intake_ml, ch.appetite, ch.activity_level, ch.exercise_completed,
               ch.medication_taken, ch.notes, ch.created_at_utc
        FROM checkins ch
        JOIN crew_members c ON c.id = ch.crew_id
        JOIN habitat_modules hm ON hm.id = ch.module_id
        ORDER BY ch.recorded_at_utc
    """,
    "06b_crew_health_timeline.csv": """
        SELECT ch.id AS checkin_id, c.crew_code, c.display_name, ch.recorded_at_utc,
               hm.module_code, ch.overall_wellbeing, ch.fatigue_level,
               ch.mood_stress_level, ch.sleep_hours, ch.sleep_quality,
               ch.fluid_intake_ml, ch.activity_level, ch.exercise_completed,
               vs.heart_rate_bpm, vs.spo2_percent, vs.respiratory_rate_bpm,
               vs.body_temperature_c, vs.hrv_ms, vs.weight_kg
        FROM checkins ch
        JOIN crew_members c ON c.id = ch.crew_id
        JOIN habitat_modules hm ON hm.id = ch.module_id
        LEFT JOIN vital_signs vs ON vs.checkin_id = ch.id
        ORDER BY c.crew_code, ch.recorded_at_utc
    """,
    "07_vital_signs.csv": """
        SELECT vs.checkin_id, c.crew_code, ch.recorded_at_utc,
               vs.heart_rate_bpm, vs.spo2_percent, vs.respiratory_rate_bpm,
               vs.body_temperature_c, vs.blood_pressure_systolic,
               vs.blood_pressure_diastolic, vs.hrv_ms, vs.weight_kg
        FROM vital_signs vs
        JOIN checkins ch ON ch.id = vs.checkin_id
        JOIN crew_members c ON c.id = ch.crew_id
        ORDER BY ch.recorded_at_utc
    """,
    "08_symptoms.csv": """
        SELECT sr.id, sr.checkin_id, c.crew_code, ch.recorded_at_utc AS checkin_time_utc,
               sr.symptom_name, sr.severity_0_to_10, sr.onset_at_utc, sr.onset_status,
               sr.duration_minutes, sr.duration_status, sr.symptom_pattern, sr.progression,
               sr.mission_task_effect, sr.similar_episode, sr.action_or_medication_taken, sr.note
        FROM symptom_records sr
        JOIN checkins ch ON ch.id = sr.checkin_id
        JOIN crew_members c ON c.id = ch.crew_id
        ORDER BY ch.recorded_at_utc
    """,
    "09_symptom_detail_answers.csv": """
        SELECT sda.id, sda.symptom_id, c.crew_code, sr.symptom_name,
               sda.field_name, sda.value_text, sda.value_number, sda.value_boolean
        FROM symptom_detail_answers sda
        JOIN symptom_records sr ON sr.id = sda.symptom_id
        JOIN checkins ch ON ch.id = sr.checkin_id
        JOIN crew_members c ON c.id = ch.crew_id
        ORDER BY sda.id
    """,
    "10_safety_reviews.csv": """
        SELECT sr.checkin_id, c.crew_code, ch.recorded_at_utc,
               sr.severe_chest_discomfort, sr.severe_breathing_difficulty,
               sr.loss_of_consciousness, sr.sudden_neurological_change,
               sr.sudden_severe_headache, sr.rapidly_worsening_symptoms,
               sr.urgent_human_review_required
        FROM safety_reviews sr
        JOIN checkins ch ON ch.id = sr.checkin_id
        JOIN crew_members c ON c.id = ch.crew_id
        ORDER BY ch.recorded_at_utc
    """,
    "11_health_reports.csv": """
        SELECT hr.id, hr.report_code, c.crew_code, ch.recorded_at_utc AS checkin_time_utc,
               hr.workflow_status, hr.ruleset_version, hr.created_at_utc, hr.medical_review_required
        FROM health_reports hr
        JOIN checkins ch ON ch.id = hr.checkin_id
        JOIN crew_members c ON c.id = ch.crew_id
        ORDER BY hr.created_at_utc
    """,
    "12_report_evidence.csv": """
        SELECT re.id, hr.report_code, re.evidence_type, re.label, re.status,
               re.source_reference, re.note, re.environment_record_id
        FROM report_evidence re
        JOIN health_reports hr ON hr.id = re.report_id
        ORDER BY re.id
    """,
    "13_medication_inventory.csv": """
        SELECT id, medication_name, form_description, quantity_available, expiry_date, active
        FROM medication_inventory ORDER BY id
    """,
    "14_medication_review_requests.csv": """
        SELECT mrr.id, c.crew_code, mi.medication_name, mrr.request_reason, mrr.status,
               mrr.requested_at_utc, mrr.reviewer_note
        FROM medication_review_requests mrr
        JOIN checkins ch ON ch.id = mrr.checkin_id
        JOIN crew_members c ON c.id = ch.crew_id
        LEFT JOIN medication_inventory mi ON mi.id = mrr.inventory_id
        ORDER BY mrr.requested_at_utc
    """,
    "15_task_delay_requests.csv": """
        SELECT tdr.id, c.crew_code, tdr.task_name, tdr.medical_reason_summary,
               tdr.status, tdr.requested_at_utc, tdr.reviewer_note
        FROM task_delay_requests tdr
        JOIN checkins ch ON ch.id = tdr.checkin_id
        JOIN crew_members c ON c.id = ch.crew_id
        ORDER BY tdr.requested_at_utc
    """,
    "16_outbox.csv": """
        SELECT id, entity_type, entity_id, status, created_at_utc, sent_at_utc,
               confirmed_at_utc, last_error
        FROM outbox ORDER BY created_at_utc
    """,
}


def csv_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def export_one(cursor, filename: str, query: str) -> int:
    cursor.execute(query)
    headings = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    destination = OUTPUT_DIRECTORY / filename
    with destination.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headings)
        writer.writerows([[csv_value(value) for value in row] for row in rows])
    return len(rows)


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    with get_connection() as connection:
        cursor = connection.cursor()
        for filename, query in EXPORTS.items():
            count = export_one(cursor, filename, query)
            print(f"{filename}: {count:,} rows")
    print(f"\nDone. Open this folder: {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()
