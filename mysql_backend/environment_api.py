"""HabitatPulse Environment API — database-backed, offline-first.

There are no embedded sensor values. Every value returned to the web app is
read from MySQL's `environment_records` table.

The `window` query parameter is measured backwards from the newest DATABASE
record, so historical replay datasets work without pretending that they are
live telemetry.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from db_config import get_connection


HOST = "127.0.0.1"
PORT = 8000
ALLOWED_ORIGIN = "http://localhost:5173"
WINDOW_HOURS: dict[str, int | None] = {"6h": 6, "24h": 24, "7d": 168, "all": None}


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialise(row: dict[str, Any]) -> dict[str, Any]:
    return {key: json_value(value) for key, value in row.items()}


def to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def metric_summary(records: list[dict[str, Any]], field: str) -> dict[str, float | None]:
    values = [float(item[field]) for item in records if item.get(field) is not None]
    return {"latest": values[-1] if values else None, "minimum": min(values) if values else None, "maximum": max(values) if values else None}


def group_persistent_events(
    records: list[dict[str, Any]],
    minimum_points: int = 2,
    maximum_gap_seconds: int = 900,
) -> list[dict[str, Any]]:
    """Create statistical screening events from time-clustered flagged readings."""

    streams: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for record in records:
        if not bool(record.get("anomaly_flag")):
            continue

        key = (
            str(record.get("module_code") or "unknown-module"),
            str(record.get("source_code") or "unknown-source"),
        )
        streams.setdefault(key, []).append(record)

    events: list[dict[str, Any]] = []

    for stream_records in streams.values():
        stream_records.sort(
            key=lambda item: to_datetime(str(item["observed_at_utc"]))
        )

        group: list[dict[str, Any]] = []
        previous_time: datetime | None = None

        for record in stream_records:
            observed_time = to_datetime(str(record["observed_at_utc"]))

            if (
                previous_time is not None
                and (observed_time - previous_time).total_seconds()
                > maximum_gap_seconds
            ):
                if len(group) >= minimum_points:
                    events.append(group)
                group = []

            group.append(record)
            previous_time = observed_time

        if len(group) >= minimum_points:
            events.append(group)

    result: list[dict[str, Any]] = []

    for group in events:
        start = group[0]
        end = group[-1]

        start_time = to_datetime(str(start["observed_at_utc"]))
        end_time = to_datetime(str(end["observed_at_utc"]))

        peak = max(
            group,
            key=lambda item: float(item.get("anomaly_score") or 0),
        )

        result.append(
            {
                "event_id": f"ENV-{start['id']}-{end['id']}",
                "start_at_utc": start["observed_at_utc"],
                "end_at_utc": end["observed_at_utc"],
                "module_code": end["module_code"],
                "source_code": end["source_code"],
                "observations": len(group),
                "duration_minutes": round(
                    (end_time - start_time).total_seconds() / 60,
                    1,
                ),
                "peak_anomaly_score": float(
                    peak.get("anomaly_score") or 0
                ),
                "peak_at_utc": peak["observed_at_utc"],
                "co2_min_ppm": min(float(item["co2_ppm"]) for item in group),
                "co2_max_ppm": max(float(item["co2_ppm"]) for item in group),
                "temperature_min_c": min(
                    float(item["temperature_c"]) for item in group
                ),
                "temperature_max_c": max(
                    float(item["temperature_c"]) for item in group
                ),
                "humidity_min_percent": min(
                    float(item["humidity_percent"]) for item in group
                ),
                "humidity_max_percent": max(
                    float(item["humidity_percent"]) for item in group
                ),
                "review_status": "statistical_pattern_for_human_review",
            }
        )

    return list(reversed(result[-20:]))


def read_dashboard(module_code: str | None, window: str, limit: int) -> dict[str, Any]:
    if window not in WINDOW_HOURS:
        raise ValueError("window must be one of: 6h, 24h, 7d, all")
    limit = max(100, min(limit, 12_000))
    module_filters: list[str] = []
    module_parameters: list[Any] = []
    if module_code and module_code.lower() not in {"all", "all-modules"}:
        module_filters.append("hm.module_code = %s")
        module_parameters.append(module_code)

    joins = """FROM environment_records er
               JOIN habitat_modules hm ON hm.id = er.module_id
               JOIN sensor_sources ss ON ss.id = er.source_id"""
    select = """SELECT er.id, er.measured_at_utc AS observed_at_utc, hm.module_code,
                       ss.source_code, er.is_simulated, er.temperature_c,
                       er.humidity_percent, er.co2_ppm, er.anomaly_score,
                       er.anomaly_threshold, er.anomaly_flag, er.anomaly_model_version"""
    module_where = f"WHERE {' AND '.join(module_filters)}" if module_filters else ""

    with get_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(f"SELECT MAX(er.measured_at_utc) AS newest_at {joins} {module_where}", tuple(module_parameters))
        newest_at = cursor.fetchone()["newest_at"]

        filters = list(module_filters)
        parameters = list(module_parameters)
        range_start: datetime | None = None
        hours = WINDOW_HOURS[window]
        if newest_at is not None and hours is not None:
            range_start = newest_at - timedelta(hours=hours)
            filters.append("er.measured_at_utc >= %s")
            parameters.append(range_start)
        selected_where = f"WHERE {' AND '.join(filters)}" if filters else ""

        cursor.execute(f"{select} {joins} {selected_where} ORDER BY er.measured_at_utc DESC LIMIT %s", tuple(parameters + [limit]))
        records = [serialise(row) for row in reversed(cursor.fetchall())]
        cursor.execute(f"SELECT COUNT(*) AS total {joins} {module_where}", tuple(module_parameters))
        stored_records = int(cursor.fetchone()["total"])
        cursor.execute(f"SELECT COUNT(*) AS total {joins} {selected_where}", tuple(parameters))
        selected_records = int(cursor.fetchone()["total"])
        cursor.execute(
            "SELECT COUNT(*) AS total FROM ("
            "SELECT er.module_id, er.source_id, er.measured_at_utc "
            f"{joins} {selected_where} "
            "GROUP BY er.module_id, er.source_id, er.measured_at_utc HAVING COUNT(*) > 1"
            ") AS duplicate_rows", tuple(parameters)
        )
        duplicate_groups = int(cursor.fetchone()["total"])
        cursor.execute("SELECT module_code FROM habitat_modules ORDER BY module_code")
        modules = [row["module_code"] for row in cursor.fetchall()]
        cursor.execute(
            """SELECT ss.source_code, COUNT(*) AS records,
                      MIN(er.measured_at_utc) AS first_at_utc,
                      MAX(er.measured_at_utc) AS last_at_utc,
                      MAX(er.is_simulated) AS historical_replay_label
               FROM environment_records er JOIN sensor_sources ss ON ss.id = er.source_id
               GROUP BY ss.source_code ORDER BY records DESC"""
        )
        sources = [serialise(row) for row in cursor.fetchall()]
        cursor.close()

    latest = records[-1] if records else None
    # `all` has no calculated start. Use the first returned database record
    # so the chart can label the beginning and end of its coverage.
    selected_start_label = json_value(range_start) if range_start is not None else (
        records[0]["observed_at_utc"] if records else None
    )
    return {
        "status": "ok",
        "data_origin": "local_mysql_database",
        "message": None if records else "No matching records are stored in MySQL for this filter.",
        "filters": {"module": module_code or "all", "window": window, "limit": limit},
        "coverage": {"newest_record_at_utc": json_value(newest_at), "selected_start_at_utc": selected_start_label, "selected_end_at_utc": json_value(newest_at)},
        "latest": latest,
        "series": records,
        "summary": {"co2_ppm": metric_summary(records, "co2_ppm"), "temperature_c": metric_summary(records, "temperature_c"), "humidity_percent": metric_summary(records, "humidity_percent")},
        "persistent_events": group_persistent_events(records),
        "quality": {"stored_records": stored_records, "records_in_selected_window": selected_records, "chart_points": len(records), "flagged_chart_points": sum(bool(item["anomaly_flag"]) for item in records), "duplicate_timestamp_groups": duplicate_groups, "time_basis": "UTC"},
        "available_modules": modules,
        "sources": sources,
        "notice": "Anomaly flags are statistical screening results, not medical diagnoses, safety-limit exceedances, or proof of cause.",
    }


def answer_bool(value: Any) -> bool | None:
    """Keep unanswered/unknown distinct from No in prototype check-ins."""
    if isinstance(value, bool):
        return value
    if not isinstance(value, str) or value.lower() == "unknown" or not value:
        return None
    if value.lower() == "yes":
        return True
    if value.lower() == "no":
        return False
    return None


def answer_number(value: Any) -> float | None:
    try:
        return float(value) if value not in {None, "", "Unknown", "Ongoing"} else None
    except (TypeError, ValueError):
        return None


def answer_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or value in {"", "Unknown"}:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def value_or(answers: dict[str, Any], key: str, default: Any) -> Any:
    value = answers.get(key)
    return default if value in {None, ""} else value


def read_health_checkins(crew_code: str | None, limit: int) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    filters: list[str] = []
    parameters: list[Any] = []
    if crew_code:
        filters.append("c.crew_code = %s")
        parameters.append(crew_code)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with get_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            f"""SELECT ch.id, c.crew_code, ch.recorded_at_utc, ch.overall_wellbeing,
                       ch.mood_stress_level, ch.sleep_hours, ch.fluid_intake_ml,
                       sr.urgent_human_review_required
                FROM checkins ch
                JOIN crew_members c ON c.id = ch.crew_id
                LEFT JOIN safety_reviews sr ON sr.checkin_id = ch.id
                {where}
                ORDER BY ch.recorded_at_utc DESC LIMIT %s""",
            tuple(parameters + [limit]),
        )
        rows = list(reversed(cursor.fetchall()))
        record_ids = [int(row["id"]) for row in rows]
        symptoms: dict[int, list[str]] = {record_id: [] for record_id in record_ids}
        if record_ids:
            placeholders = ", ".join(["%s"] * len(record_ids))
            cursor.execute(
                f"SELECT checkin_id, symptom_name FROM symptom_records WHERE checkin_id IN ({placeholders}) ORDER BY id",
                tuple(record_ids),
            )
            for row in cursor.fetchall():
                symptoms[int(row["checkin_id"])].append(str(row["symptom_name"]))
        cursor.close()
    records = []
    for row in rows:
        record_id = int(row["id"])
        records.append({
            "id": str(record_id),
            "crewId": row["crew_code"],
            "time": json_value(row["recorded_at_utc"]),
            "wellbeing": int(row["overall_wellbeing"]),
            "mood": int(row["mood_stress_level"]),
            "sleep": float(row["sleep_hours"]),
            "fluid": int(row["fluid_intake_ml"]),
            "symptoms": symptoms[record_id],
            "urgent": bool(row["urgent_human_review_required"]),
        })
    return {"status": "ok", "data_origin": "local_mysql_database", "records": records}


def create_health_checkin(payload: dict[str, Any]) -> dict[str, Any]:
    """Store a form submission; it never diagnoses, prescribes, or approves a task change."""
    crew = payload.get("crew") if isinstance(payload.get("crew"), dict) else {}
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    symptoms = payload.get("symptoms") if isinstance(payload.get("symptoms"), list) else []
    crew_code = crew.get("id")
    module_code = crew.get("module") or "HAB-MODULE-B"
    recorded_at = answer_time(payload.get("checkinTimeUTC")) or datetime.utcnow()
    if not isinstance(crew_code, str) or not crew_code:
        raise ValueError("crew.id is required")
    if not isinstance(module_code, str) or not module_code:
        raise ValueError("crew.module is required")

    overall = answer_number(answers.get("wellbeing.Overall wellbeing"))
    mood = answer_number(answers.get("wellbeing.Mood/stress level"))
    sleep = answer_number(answers.get("wellbeing.Sleep hours"))
    fluid = answer_number(answers.get("wellbeing.Fluid intake (ml)"))
    fatigue = str(value_or(answers, "wellbeing.Energy/fatigue level", "mild")).lower()
    activity = str(value_or(answers, "wellbeing.Activity level", "normal")).lower()
    if overall is None or mood is None or sleep is None or fluid is None:
        raise ValueError("overall wellbeing, mood/stress, sleep hours, and fluid intake are required")
    if fatigue not in {"none", "mild", "moderate", "severe"} or activity not in {"low", "normal", "high"}:
        raise ValueError("fatigue level or activity level is invalid")

    safety_fields = {
        "severe_chest_discomfort": "safety.Severe chest discomfort",
        "severe_breathing_difficulty": "safety.Severe breathing difficulty",
        "loss_of_consciousness": "safety.Loss of consciousness",
        "sudden_neurological_change": "safety.Sudden neurological change",
        "sudden_severe_headache": "safety.Sudden severe headache",
        "rapidly_worsening_symptoms": "safety.Rapidly worsening symptoms",
    }
    safety = {column: answer_bool(answers.get(field)) for column, field in safety_fields.items()}
    urgent = bool(payload.get("urgentReview")) or any(value is True for value in safety.values())

    with get_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id FROM crew_members WHERE crew_code = %s AND active = TRUE", (crew_code,))
        crew_row = cursor.fetchone()
        cursor.execute("SELECT id FROM habitat_modules WHERE module_code = %s", (module_code,))
        module_row = cursor.fetchone()
        if not crew_row:
            raise ValueError(f"Unknown active crew member: {crew_code}")
        if not module_row:
            raise ValueError(f"Unknown habitat module: {module_code}")
        cursor.execute(
            """INSERT INTO checkins (
                 crew_id, recorded_at_utc, module_id, notes, overall_wellbeing,
                 fatigue_level, mood_stress_level, sleep_hours, sleep_quality,
                 fluid_intake_ml, appetite, activity_level, exercise_completed, medication_taken
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                crew_row["id"], recorded_at, module_row["id"],
                "Submitted through HabitatPulse crew check-in UI. Prototype record; human review required for clinical decisions.",
                round(overall), fatigue, round(mood), sleep,
                str(value_or(answers, "wellbeing.Sleep quality", "fair")).lower() if answers.get("wellbeing.Sleep quality") else None,
                round(fluid), str(value_or(answers, "wellbeing.Appetite", "normal")).lower() if answers.get("wellbeing.Appetite") else None,
                activity, answer_bool(answers.get("wellbeing.Exercise completed")),
                str(value_or(answers, "wellbeing.Current medication taken", "not_applicable")).lower().replace(" ", "_"),
            ),
        )
        checkin_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO vital_signs (
                 checkin_id, heart_rate_bpm, spo2_percent, respiratory_rate_bpm,
                 body_temperature_c, hrv_ms, weight_kg
               ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                checkin_id, answer_number(answers.get("vitals.Pulse / heart rate (BPM)")),
                answer_number(answers.get("vitals.Blood oxygen / SpO₂ (%)")),
                answer_number(answers.get("vitals.Respiratory rate (breaths per minute)")),
                answer_number(answers.get("vitals.Body temperature (°C)")),
                answer_number(answers.get("vitals.Heart-rate variability / HRV (optional wearable value)")),
                answer_number(answers.get("vitals.Weight (kg, optional)")),
            ),
        )
        for symptom in symptoms:
            if not isinstance(symptom, str) or symptom == "No current symptoms":
                continue
            prefix = f"{symptom}."
            duration_value = answers.get(prefix + "Duration (minutes)")
            duration_status = "ongoing" if duration_value == "Ongoing" else "known"
            cursor.execute(
                """INSERT INTO symptom_records (
                     checkin_id, symptom_name, severity_0_to_10, onset_at_utc, onset_status,
                     duration_minutes, duration_status, symptom_pattern, progression,
                     mission_task_effect, similar_episode, action_or_medication_taken, note
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    checkin_id, symptom.lower().replace(" / ", "_").replace(" ", "_"),
                    answer_number(answers.get(prefix + "Severity (0–10)")), answer_time(answers.get(prefix + "Onset date/time (UTC)")),
                    "unknown" if answers.get(prefix + "Onset date/time (UTC)") == "Unknown" else "known",
                    answer_number(duration_value), duration_status,
                    answers.get(prefix + "Pattern") or None, answers.get(prefix + "Progression") or None,
                    str(answers.get(prefix + "Effect on mission tasks") or "").lower().replace(" ", "_") or None,
                    str(answers.get(prefix + "Similar episode previously") or "").lower() or None,
                    answers.get(prefix + "Action or medication already taken") or None,
                    answers.get(prefix + "Free-text note") or None,
                ),
            )
            symptom_id = int(cursor.lastrowid)
            for key, value in answers.items():
                if key.startswith(prefix) and key not in {
                    prefix + "Severity (0–10)", prefix + "Onset date/time (UTC)", prefix + "Duration (minutes)",
                    prefix + "Pattern", prefix + "Progression", prefix + "Effect on mission tasks",
                    prefix + "Similar episode previously", prefix + "Action or medication already taken", prefix + "Free-text note",
                } and value not in {None, ""}:
                    cursor.execute(
                        "INSERT INTO symptom_detail_answers (symptom_id, field_name, value_text) VALUES (%s, %s, %s)",
                        (symptom_id, key[len(prefix):], str(value)),
                    )
        cursor.execute(
            """INSERT INTO safety_reviews (
                 checkin_id, severe_chest_discomfort, severe_breathing_difficulty, loss_of_consciousness,
                 sudden_neurological_change, sudden_severe_headache, rapidly_worsening_symptoms,
                 urgent_human_review_required
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (checkin_id, *safety.values(), urgent),
        )
        cursor.execute("INSERT INTO outbox (entity_type, entity_id) VALUES ('checkin', %s)", (checkin_id,))
        connection.commit()
        cursor.close()
    return {"status": "created", "data_origin": "local_mysql_database", "checkin_id": checkin_id, "urgent_human_review_required": urgent}


def read_medication_inventory() -> dict[str, Any]:
    """Return active stock records for medical-officer inventory review.

    This endpoint reports stock only.  It does not prescribe, approve, or
    recommend any medication for a crew member.
    """
    with get_connection() as connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT id, medication_name, form_description,
                      quantity_available, expiry_date
               FROM medication_inventory
               WHERE active = TRUE
               ORDER BY medication_name"""
        )
        rows = cursor.fetchall()
        cursor.close()

    return {
        "status": "ok",
        "data_origin": "local_mysql_database",
        "items": [
            {
                "id": int(row["id"]),
                "medication_name": row["medication_name"],
                "form_description": row["form_description"],
                "quantity_available": int(row["quantity_available"]),
                "expiry_date": json_value(row["expiry_date"]),
            }
            for row in rows
        ],
        "notice": "Inventory listing only; a medical officer must verify approval, expiry, contraindications, and use.",
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: HTTPStatus, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # A browser refresh/Vite hot reload can cancel a request after the
            # database query completed. The client is gone, so there is no
            # error response to send and the local API should keep running.
            return

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(HTTPStatus.OK, {"status": "ok", "service": "HabitatPulse local MySQL API"})
            return
        if parsed.path == "/api/v1/medication-inventory":
            try:
                self.send_json(HTTPStatus.OK, read_medication_inventory())
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        if parsed.path == "/api/v1/health/checkins":
            try:
                query = parse_qs(parsed.query)
                crew_code = query.get("crew_code", [None])[0]
                limit = int(query.get("limit", ["180"])[0])
                self.send_json(HTTPStatus.OK, read_health_checkins(crew_code, limit))
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        if parsed.path != "/api/v1/environment/dashboard":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            query = parse_qs(parsed.query)
            module_code = query.get("module", [None])[0]
            window = query.get("window", ["24h"])[0]
            limit = int(query.get("limit", ["2000"])[0])
            self.send_json(HTTPStatus.OK, read_dashboard(module_code, window, limit))
        except ValueError as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/health/checkins":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("Request body must be between 1 and 1,000,000 bytes")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON object expected")
            self.send_json(HTTPStatus.CREATED, create_health_checkin(payload))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})


if __name__ == "__main__":
    print(f"HabitatPulse environment API: http://{HOST}:{PORT}/api/health")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
