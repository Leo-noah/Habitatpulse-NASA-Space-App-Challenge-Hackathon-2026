"""Insert one clearly labelled Crew-01 screening demo event.

This script never deletes normal historical check-ins.  Running it repeatedly
updates the same dedicated demo record so that the event remains the newest
Crew-01 record shown by the Evidence page.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from db_config import get_connection


MARKER = "SIMULATED_DEMO_HEALTH_V3_CREW01_EVIDENCE"


def main() -> None:
    recorded_at = datetime.utcnow().replace(microsecond=0)

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM crew_members WHERE crew_code = %s LIMIT 1",
            ("CREW-01",),
        )
        crew = cursor.fetchone()

        cursor.execute(
            "SELECT id FROM habitat_modules WHERE module_code = %s LIMIT 1",
            ("HAB-MODULE-B",),
        )
        module = cursor.fetchone()

        if not crew or not module:
            raise RuntimeError(
                "CREW-01 or HAB-MODULE-B is missing. Run sample_data.sql first."
            )

        crew_id = int(crew[0])
        module_id = int(module[0])

        # Reuse one dedicated demo row rather than adding duplicates each time.
        cursor.execute(
            "SELECT id FROM checkins WHERE notes LIKE %s ORDER BY id DESC LIMIT 1",
            (f"{MARKER}%",),
        )
        existing = cursor.fetchone()

        notes = (
            f"{MARKER}; fictional controlled screening scenario; "
            "not clinical data and not a diagnosis."
        )

        if existing:
            checkin_id = int(existing[0])
            cursor.execute(
                """UPDATE checkins
                   SET recorded_at_utc=%s, notes=%s, overall_wellbeing=2,
                       fatigue_level='moderate', mood_stress_level=2,
                       sleep_hours=5.00, sleep_quality='poor',
                       fluid_intake_ml=1200, appetite='normal',
                       activity_level='low', exercise_completed=FALSE,
                       medication_taken='not_applicable'
                   WHERE id=%s""",
                (recorded_at, notes, checkin_id),
            )
            cursor.execute("DELETE FROM symptom_records WHERE checkin_id=%s", (checkin_id,))
            cursor.execute("DELETE FROM vital_signs WHERE checkin_id=%s", (checkin_id,))
            cursor.execute("DELETE FROM safety_reviews WHERE checkin_id=%s", (checkin_id,))
        else:
            cursor.execute(
                """INSERT INTO checkins (
                     crew_id, recorded_at_utc, module_id, current_mission_task,
                     recent_task_completed, notes, overall_wellbeing,
                     fatigue_level, mood_stress_level, sleep_hours, sleep_quality,
                     fluid_intake_ml, appetite, activity_level, exercise_completed,
                     medication_taken
                   ) VALUES (
                     %s, %s, %s, 'Simulated evidence demonstration',
                     'Simulated scheduled task', %s, 2, 'moderate', 2, 5.00,
                     'poor', 1200, 'normal', 'low', FALSE, 'not_applicable'
                   )""",
                (crew_id, recorded_at, module_id, notes),
            )
            checkin_id = int(cursor.lastrowid)

        cursor.execute(
            """INSERT INTO vital_signs (
                 checkin_id, heart_rate_bpm, spo2_percent, respiratory_rate_bpm,
                 body_temperature_c, hrv_ms, weight_kg
               ) VALUES (%s, 78.0, 98.0, 16.0, 36.8, 41.0, 71.0)""",
            (checkin_id,),
        )

        symptoms = [
            ("headache", 5, "intermittent", "stable", 90),
            ("fatigue", 4, "intermittent", "stable", 240),
        ]

        for name, severity, pattern, progression, duration in symptoms:
            cursor.execute(
                """INSERT INTO symptom_records (
                     checkin_id, symptom_name, severity_0_to_10, onset_at_utc,
                     onset_status, duration_minutes, duration_status,
                     symptom_pattern, progression, mission_task_effect,
                     similar_episode, action_or_medication_taken, note
                   ) VALUES (
                     %s, %s, %s, %s, 'known', %s, 'known', %s, %s,
                     'some_difficulty', 'unknown',
                     'No treatment recommendation generated.', %s
                   )""",
                (
                    checkin_id,
                    name,
                    severity,
                    recorded_at - timedelta(minutes=duration),
                    duration,
                    pattern,
                    progression,
                    f"{MARKER}; fictional {name} report for UI demonstration only.",
                ),
            )

        cursor.execute(
            """INSERT INTO safety_reviews (
                 checkin_id, severe_chest_discomfort, severe_breathing_difficulty,
                 loss_of_consciousness, sudden_neurological_change,
                 sudden_severe_headache, rapidly_worsening_symptoms,
                 urgent_human_review_required
               ) VALUES (%s, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE)""",
            (checkin_id,),
        )

        cursor.execute(
            "INSERT INTO outbox (entity_type, entity_id, status) VALUES ('checkin', %s, 'pending_sync')",
            (checkin_id,),
        )

        connection.commit()
        cursor.close()

    print(f"Created/updated Crew-01 evidence demo check-in: id={checkin_id}")
    print("Contains: headache, fatigue, wellbeing 2/5, sleep 5.0 h.")
    print("Label: SIMULATED_DEMO_HEALTH_V3_CREW01_EVIDENCE")


if __name__ == "__main__":
    main()
