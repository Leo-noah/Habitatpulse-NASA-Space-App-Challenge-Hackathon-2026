"""HabitatPulse Evidence API (local MySQL + rule-engine adapter).

Run after MYSQL_USER and MYSQL_PASSWORD are set:
    python evidence_api.py

The service reads a symptom-bearing MySQL check-in, converts it into the
healthcare_rule_engine input format, and returns transparent review patterns.
It does not diagnose disease or calculate disease probabilities.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from db_config import get_connection

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from healthcare_rule_engine import evaluate_checkin  # noqa: E402


HOST = "127.0.0.1"
PORT = 8001
ALLOWED_ORIGIN = "http://localhost:5173"

SYMPTOM_NAMES = {
    "nausea_vomiting": "nausea_or_vomiting",
    "nasal_congestion_allergy_symptoms": "nasal_congestion_or_allergy",
    "fever_chills": "fever_or_chills",
    "other_symptom": "other",
}

DETAIL_NAMES = {
    "pain_location": "pain_location",
    "pain_quality": "pain_quality",
    "sudden_peak_within_5_minutes": "sudden_peak_within_5_minutes",
    "worse_during_normal_activity": "routine_activity_worsens_or_is_avoided",
    "light_sensitivity": "light_sensitivity",
    "sound_sensitivity": "sound_sensitivity",
    "nausea_or_vomiting": "nausea_or_vomiting",
    "fever": "fever",
    "new_vision_change": "new_vision_change",
    "new_neurological_change": "new_neurological_change",
    "confusion_or_impaired_consciousness": "impaired_consciousness",
}


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return float(value)
    return value


def as_bool_or_unknown(value: Any) -> bool | str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, Decimal)):
        return bool(value)
    text = str(value).strip().lower()
    if text == "yes":
        return True
    if text == "no":
        return False
    if text == "unknown":
        return "unknown"
    return None


def normal_key(value: str) -> str:
    return value.strip().lower().replace("/", "_").replace(" ", "_").replace("-", "_")


def detail_value(value: Any) -> Any:
    if value is None:
        return None
    parsed = as_bool_or_unknown(value)
    if parsed is not None:
        return parsed
    return value


def latest_symptomatic_checkin(cursor: Any, crew_code: str | None) -> dict[str, Any] | None:
    filters = ["EXISTS (SELECT 1 FROM symptom_records sx WHERE sx.checkin_id = ch.id)"]
    params: list[Any] = []
    if crew_code:
        filters.append("c.crew_code = %s")
        params.append(crew_code)
    cursor.execute(
        f"""SELECT ch.id, c.crew_code, hm.module_code, ch.recorded_at_utc,
                   ch.current_mission_task, ch.recent_task_completed, ch.notes,
                   ch.overall_wellbeing, ch.fatigue_level, ch.mood_stress_level,
                   ch.sleep_hours, ch.sleep_quality, ch.fluid_intake_ml,
                   ch.appetite, ch.activity_level, ch.exercise_completed,
                   ch.medication_taken
            FROM checkins ch
            JOIN crew_members c ON c.id = ch.crew_id
            JOIN habitat_modules hm ON hm.id = ch.module_id
            WHERE {' AND '.join(filters)}
            -- The current prototype engine contains headache-pattern rules.
            -- Prefer a headache record for a useful demo, then fall back to
            -- the most recent symptom-bearing record when none exists.
            ORDER BY CASE WHEN EXISTS (
                SELECT 1 FROM symptom_records hp
                WHERE hp.checkin_id = ch.id AND hp.symptom_name = 'headache'
            ) THEN 0 ELSE 1 END,
            ch.recorded_at_utc DESC
            LIMIT 1""",
        tuple(params),
    )
    return cursor.fetchone()


def load_rule_input(crew_code: str | None) -> dict[str, Any] | None:
    with get_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        checkin = latest_symptomatic_checkin(cursor, crew_code)
        if not checkin:
            cursor.close()
            return None

        checkin_id = int(checkin["id"])
        cursor.execute(
            """SELECT heart_rate_bpm, spo2_percent, respiratory_rate_bpm,
                      body_temperature_c, hrv_ms, weight_kg
               FROM vital_signs WHERE checkin_id = %s LIMIT 1""",
            (checkin_id,),
        )
        vitals = cursor.fetchone() or {}

        cursor.execute("SELECT * FROM safety_reviews WHERE checkin_id = %s LIMIT 1", (checkin_id,))
        safety_row = cursor.fetchone() or {}

        cursor.execute(
            """SELECT id, symptom_name, severity_0_to_10, onset_at_utc,
                      duration_minutes, duration_status, symptom_pattern,
                      progression, mission_task_effect, similar_episode,
                      action_or_medication_taken, note
               FROM symptom_records
               WHERE checkin_id = %s ORDER BY id""",
            (checkin_id,),
        )
        symptoms = []
        for row in cursor.fetchall():
            cursor.execute(
                "SELECT field_name, value_text FROM symptom_detail_answers WHERE symptom_id = %s",
                (row["id"],),
            )
            details = {}
            for answer in cursor.fetchall():
                field = DETAIL_NAMES.get(normal_key(str(answer["field_name"])))
                if field:
                    details[field] = detail_value(answer["value_text"])

            name = SYMPTOM_NAMES.get(str(row["symptom_name"]), str(row["symptom_name"]))
            symptoms.append({
                "name": name,
                "severity_0_to_10": json_value(row["severity_0_to_10"]),
                "onset_at_utc": json_value(row["onset_at_utc"]),
                "duration_minutes": "ongoing" if row["duration_status"] == "ongoing" else json_value(row["duration_minutes"]),
                "pattern": row["symptom_pattern"],
                "progression": row["progression"],
                "mission_task_effect": row["mission_task_effect"],
                "similar_episode_previously": row["similar_episode"],
                "action_or_medication_already_taken": row["action_or_medication_taken"],
                "note": row["note"],
                "details": details,
            })

        cursor.execute(
            """SELECT er.measured_at_utc, ss.source_code, er.is_simulated,
                      er.temperature_c, er.humidity_percent, er.co2_ppm,
                      er.anomaly_flag, er.anomaly_score
               FROM environment_records er
               JOIN sensor_sources ss ON ss.id = er.source_id
               WHERE er.module_id = (SELECT module_id FROM checkins WHERE id = %s)
               ORDER BY ABS(TIMESTAMPDIFF(SECOND, er.measured_at_utc, %s))
               LIMIT 1""",
            (checkin_id, checkin["recorded_at_utc"]),
        )
        environment = cursor.fetchone()
        cursor.close()

    environment_input: dict[str, Any] = {}
    linkage = {}
    if environment:
        observed = environment["measured_at_utc"]
        recorded = checkin["recorded_at_utc"]
        gap_seconds = abs((observed - recorded).total_seconds())
        environment_input = {
            "measured_at_utc": json_value(observed),
            "location_id": checkin["module_code"],
            "source_id": environment["source_code"],
            "is_simulated": bool(environment["is_simulated"]),
            "temperature_c": json_value(environment["temperature_c"]),
            "humidity_percent": json_value(environment["humidity_percent"]),
            "co2_ppm": json_value(environment["co2_ppm"]),
            "anomaly_flag": bool(environment["anomaly_flag"]),
            "anomaly_score": json_value(environment["anomaly_score"]),
        }
        linkage = {
            "crew_exposure_confirmed": False,
            "location_match_confirmed": True,
            "symptom_exposure_time_overlap_confirmed": gap_seconds <= 900,
            "measurement_quality_accepted": True,
        }

    return {
        "crew_id": checkin["crew_code"],
        "recorded_at_utc": json_value(checkin["recorded_at_utc"]),
        "daily_context": {
            "location_id": checkin["module_code"],
            "current_mission_task": checkin["current_mission_task"],
            "recent_task_completed": checkin["recent_task_completed"],
            "notes": checkin["notes"],
            "overall_wellbeing_1_to_5": int(checkin["overall_wellbeing"]),
            "energy_fatigue_level": checkin["fatigue_level"],
            "mood_stress_1_to_5": int(checkin["mood_stress_level"]),
            "sleep_hours": json_value(checkin["sleep_hours"]),
            "sleep_quality": checkin["sleep_quality"],
            "fluid_intake_ml": int(checkin["fluid_intake_ml"]),
            "appetite": checkin["appetite"],
            "activity_level": checkin["activity_level"],
            "exercise_completed": as_bool_or_unknown(checkin["exercise_completed"]),
            "current_medication_taken": checkin["medication_taken"],
        },
        "vitals": {
            "heart_rate_bpm": json_value(vitals.get("heart_rate_bpm")),
            "spo2_percent": json_value(vitals.get("spo2_percent")),
            "respiratory_rate_bpm": json_value(vitals.get("respiratory_rate_bpm")),
            "body_temperature_c": json_value(vitals.get("body_temperature_c")),
            "hrv_ms": json_value(vitals.get("hrv_ms")),
            "weight_kg": json_value(vitals.get("weight_kg")),
            "mission_protocol_review_flags": [],
        },
        "symptoms": symptoms,
        "safety": {
            key: as_bool_or_unknown(safety_row.get(key))
            for key in (
                "severe_chest_discomfort", "severe_breathing_difficulty",
                "loss_of_consciousness", "sudden_neurological_change",
                "sudden_severe_headache", "rapidly_worsening_symptoms",
            )
        },
        "environment": environment_input,
        "environment_linkage": linkage,
    }


def present_cards(report: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    for item in report.get("possible_patterns_for_review", []):
        cards.append({
            "title": item["label"],
            "kind": "screening_pattern",
            "status": item["status"],
            "supports": item["supporting_evidence"],
            "limits": item["not_assessed"] + item["missing_fields"],
        })
    for item in report.get("context_cards", []):
        cards.append({
            "title": item["label"],
            "kind": "context",
            "status": item["status"],
            "supports": item["supporting_evidence"],
            "limits": [item["claim_limit"]],
        })
    return cards[:3]


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: HTTPStatus, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False, default=json_value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(HTTPStatus.OK, {"status": "ok", "service": "HabitatPulse Evidence API"})
            return
        if parsed.path != "/api/v1/evidence/review":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            crew_code = parse_qs(parsed.query).get("crew_code", [None])[0]
            checkin = load_rule_input(crew_code)
            if not checkin:
                self.send_json(HTTPStatus.NOT_FOUND, {
                    "error": "No symptom-bearing check-in is stored for this crew selection.",
                })
                return
            report = evaluate_checkin(checkin)
            self.send_json(HTTPStatus.OK, {
                "status": "ok",
                "data_origin": "local_mysql_database",
                "evaluated_checkin": {
                    "crew_code": checkin["crew_id"],
                    "recorded_at_utc": checkin["recorded_at_utc"],
                    "symptoms": [item["name"] for item in checkin["symptoms"]],
                },
                "cards": present_cards(report),
                "report": report,
            })
        except Exception as error:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})


if __name__ == "__main__":
    print(f"HabitatPulse Evidence API: http://{HOST}:{PORT}/api/v1/evidence/review")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
