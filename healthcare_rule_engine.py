"""HabitatPulse healthcare rule engine (prototype / simulation only).

This module is deliberately a decision-support tool, not a diagnostic or
prescribing system. It combines a crew check-in, optional vital signs, and
environment context into a transparent report for a human medical reviewer.

Run:
    python healthcare_rule_engine.py sample_checkin.json
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RULESET = {
    "name": "HabitatPulse Health Review",
    "version": "0.2-draft",
    "status": "draft_not_clinically_reviewed",
    "validated_for_spaceflight": False,
    "produces_diagnoses": False,
    "produces_disease_probabilities": False,
}

DISCLAIMER = (
    "Prototype decision support only. This report does not diagnose disease, "
    "prescribe medication, or replace an authorized medical reviewer."
)

ALLOWED_SYMPTOMS = {
    "no_current_symptoms", "headache", "dizziness", "nausea_or_vomiting", "fatigue",
    "sleep_difficulty", "breathing_discomfort", "chest_discomfort",
    "palpitations", "muscle_or_joint_pain", "back_pain", "vision_change",
    "nasal_congestion_or_allergy", "fever_or_chills",
    "mood_or_concentration_difficulty", "other",
}
ALLOWED_TRENDS = {"improving", "stable", "worsening"}
ALLOWED_PATTERNS = {"constant", "intermittent"}
ALLOWED_TASK_EFFECTS = {"none", "some_difficulty", "unable_to_perform_safely"}
ALLOWED_YES_NO_UNKNOWN = {True, False, "unknown"}
ALLOWED_ACTIVITY_LEVELS = {"low", "normal", "high"}
ALLOWED_SLEEP_QUALITY = {"poor", "fair", "good"}
ALLOWED_APPETITE = {"reduced", "normal", "increased"}
ALLOWED_FATIGUE = {"none", "mild", "moderate", "severe"}

# These keys describe the final form. They are intentionally not clinical
# rules: values are retained for a future authorized medical review.
DETAIL_SECTIONS = {
    "headache": "headache_details",
    "dizziness": "dizziness_details",
    "nausea_or_vomiting": "nausea_vomiting_details",
    "fatigue": "fatigue_details",
    "sleep_difficulty": "sleep_difficulty_details",
    "breathing_discomfort": "breathing_discomfort_details",
    "chest_discomfort": "chest_discomfort_details",
    "palpitations": "palpitations_details",
    "muscle_or_joint_pain": "muscle_joint_pain_details",
    "back_pain": "back_pain_details",
    "vision_change": "vision_change_details",
    "nasal_congestion_or_allergy": "nasal_allergy_details",
    "fever_or_chills": "fever_chills_details",
    "mood_or_concentration_difficulty": "mood_concentration_details",
    "other": "other_symptom_details",
}


def get_path(data: dict[str, Any], path: str, default: Any = None) -> Any:
    """Read a dotted path without converting missing answers to False."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def evidence(field: str, observed: Any, meaning: str) -> dict[str, Any]:
    return {"field": field, "observed": observed, "meaning": meaning}


def between(value: Any, low: float, high: float) -> bool:
    """Return True only for a numeric value in an inclusive range."""
    return isinstance(value, (int, float)) and low <= value <= high


def normalized_text(value: Any) -> Any:
    """Normalize UI labels such as 'Both sides' for internal comparison."""
    if not isinstance(value, str):
        return value
    return value.strip().lower().replace(" ", "_").replace("/", "_")


def symptom_record(checkin: dict[str, Any], name: str) -> dict[str, Any] | None:
    """Return a selected symptom from the final list-based check-in format."""
    symptoms = checkin.get("symptoms", [])
    if not isinstance(symptoms, list):
        return None
    for symptom in symptoms:
        if isinstance(symptom, dict) and symptom.get("name") == name:
            return symptom
    return None


def headache_record(checkin: dict[str, Any]) -> dict[str, Any]:
    """Support both the legacy top-level headache block and final symptom list.

    The final form stores common fields once in the selected symptom and puts
    headache-only fields in ``details``. This helper combines them so rules do
    not force the frontend to duplicate the same answers.
    """
    legacy = checkin.get("headache")
    if isinstance(legacy, dict):
        return legacy
    symptom = symptom_record(checkin, "headache")
    if not symptom:
        return {"present": False}
    details = symptom.get("details", {})
    details = details if isinstance(details, dict) else {}
    return {
        **details,
        "present": True,
        "severity_0_to_10": symptom.get("severity_0_to_10"),
        "onset_at_utc": symptom.get("onset_at_utc"),
        "duration_minutes": symptom.get("duration_minutes"),
        "trend": symptom.get("progression", symptom.get("trend")),
        "previous_similar_headaches": symptom.get("similar_episode_previously"),
        "note": symptom.get("note"),
    }


def build_input_quality(checkin: dict[str, Any]) -> dict[str, Any]:
    """Validate the full Crew Check-in form without modifying answers."""
    required = [
        "crew_id",
        "recorded_at_utc",
        "daily_context.location_id",
        "daily_context.overall_wellbeing_1_to_5",
        "daily_context.energy_fatigue_level",
        "daily_context.mood_stress_1_to_5",
        "daily_context.sleep_hours",
        "daily_context.fluid_intake_ml",
        "daily_context.activity_level",
    ]
    missing = [field for field in required if get_path(checkin, field) in (None, "")]
    invalid = []
    daily = checkin.get("daily_context", {})

    if daily.get("overall_wellbeing_1_to_5") is not None and not between(daily.get("overall_wellbeing_1_to_5"), 1, 5):
        invalid.append("daily_context.overall_wellbeing_1_to_5")
    if daily.get("mood_stress_1_to_5") is not None and not between(daily.get("mood_stress_1_to_5"), 1, 5):
        invalid.append("daily_context.mood_stress_1_to_5")
    if daily.get("energy_fatigue_level") is not None and daily.get("energy_fatigue_level") not in ALLOWED_FATIGUE:
        invalid.append("daily_context.energy_fatigue_level")
    if daily.get("activity_level") is not None and daily.get("activity_level") not in ALLOWED_ACTIVITY_LEVELS:
        invalid.append("daily_context.activity_level")
    if daily.get("sleep_quality") is not None and daily.get("sleep_quality") not in ALLOWED_SLEEP_QUALITY:
        invalid.append("daily_context.sleep_quality")
    if daily.get("appetite") is not None and daily.get("appetite") not in ALLOWED_APPETITE:
        invalid.append("daily_context.appetite")

    raw_symptoms = checkin.get("symptoms", [])
    if not isinstance(raw_symptoms, list):
        raw_symptoms = []
        invalid.append("symptoms")

    symptom_issues = []
    selected_names: list[str] = []
    for index, symptom in enumerate(raw_symptoms):
        prefix = f"symptoms[{index}]"
        if not isinstance(symptom, dict):
            symptom_issues.append(f"{prefix} must be an object")
            continue
        name = symptom.get("name")
        selected_names.append(name)
        if name not in ALLOWED_SYMPTOMS:
            symptom_issues.append(f"{prefix}.name is unsupported or missing")
            continue
        if name == "no_current_symptoms":
            continue
        if not between(symptom.get("severity_0_to_10"), 0, 10):
            symptom_issues.append(f"{prefix}.severity_0_to_10 is missing or invalid")
        onset = symptom.get("onset_at_utc")
        if onset in (None, ""):
            symptom_issues.append(f"{prefix}.onset_at_utc is missing")
        if name == "headache" and onset == "unknown":
            symptom_issues.append(f"{prefix}.onset_at_utc cannot be unknown for headache")
        duration = symptom.get("duration_minutes")
        if not isinstance(duration, (int, float)) and duration != "ongoing":
            symptom_issues.append(f"{prefix}.duration_minutes must be a number or ongoing")
        if name == "headache" and duration == "ongoing":
            # Ongoing is acceptable when an onset time is supplied; the UI can
            # calculate elapsed time later without inventing a duration.
            pass
        progression = symptom.get("progression", symptom.get("trend"))
        if progression not in ALLOWED_TRENDS:
            symptom_issues.append(f"{prefix}.progression must be improving, stable, or worsening")
        if symptom.get("pattern") is not None and symptom.get("pattern") not in ALLOWED_PATTERNS:
            symptom_issues.append(f"{prefix}.pattern must be constant or intermittent")
        effect = symptom.get("mission_task_effect")
        if effect is not None and effect not in ALLOWED_TASK_EFFECTS:
            symptom_issues.append(f"{prefix}.mission_task_effect is invalid")
        previous = symptom.get("similar_episode_previously")
        if previous is not None and previous not in ALLOWED_YES_NO_UNKNOWN:
            symptom_issues.append(f"{prefix}.similar_episode_previously must be yes, no, or unknown")
        if symptom.get("details") is not None and not isinstance(symptom.get("details"), dict):
            symptom_issues.append(f"{prefix}.details must be an object")

    if "no_current_symptoms" in selected_names and len(selected_names) != 1:
        symptom_issues.append("no_current_symptoms is exclusive and cannot be selected with another symptom")

    return {
        "missing_required_fields": missing,
        "invalid_fields": invalid,
        "symptom_input_issues": symptom_issues,
        "is_simulated": get_path(checkin, "environment.is_simulated", False),
    }


def build_symptom_summary(checkin: dict[str, Any]) -> dict[str, Any]:
    """Preserve symptom details exactly as reported; do not diagnose."""
    raw_symptoms = checkin.get("symptoms", [])
    if not isinstance(raw_symptoms, list):
        raw_symptoms = []

    selected = []
    for symptom in raw_symptoms:
        if isinstance(symptom, dict):
            selected.append({
                "name": symptom.get("name"),
                "detail_section": DETAIL_SECTIONS.get(symptom.get("name")),
                "severity_0_to_10": symptom.get("severity_0_to_10"),
                "onset_at_utc": symptom.get("onset_at_utc"),
                "duration_minutes": symptom.get("duration_minutes"),
                "pattern": symptom.get("pattern"),
                "progression": symptom.get("progression", symptom.get("trend")),
                "mission_task_effect": symptom.get("mission_task_effect"),
                "similar_episode_previously": symptom.get("similar_episode_previously"),
                "action_or_medication_already_taken": symptom.get("action_or_medication_already_taken"),
                "note": symptom.get("note"),
                "details": symptom.get("details", {}),
            })

    names = {item.get("name") for item in selected}
    if get_path(checkin, "headache.present") is True and "headache" not in names:
        selected.append({
            "name": "headache",
            "severity_0_to_10": get_path(checkin, "headache.severity_0_to_10"),
            "onset_at_utc": get_path(checkin, "headache.onset_at_utc"),
            "duration_minutes": get_path(checkin, "headache.duration_minutes"),
            "trend": get_path(checkin, "headache.trend"),
            "note": get_path(checkin, "headache.note"),
        })

    return {
        "selected_symptoms": selected,
        "count": len(selected),
        "note": "Symptoms are reported observations, not diagnoses.",
    }


def build_red_flag_review(checkin: dict[str, Any]) -> dict[str, Any]:
    """Check final-form Section G only; no hidden clinical escalation rules."""
    questions = {
        "safety.severe_chest_discomfort": "Severe chest discomfort was reported.",
        "safety.severe_breathing_difficulty": "Severe breathing difficulty was reported.",
        "safety.loss_of_consciousness": "Loss of consciousness was reported.",
        "safety.sudden_neurological_change": "Sudden neurological change was reported.",
        "safety.sudden_severe_headache": "Sudden severe headache was reported.",
        "safety.rapidly_worsening_symptoms": "Rapidly worsening symptoms were reported.",
    }

    triggered, unknown = [], []
    for field, message in questions.items():
        value = get_path(checkin, field)
        if value is True:
            triggered.append({"rule_id": "SAFETY_" + field.upper().replace(".", "_"), "message": message})
        elif value is None:
            unknown.append(field)

    return {
        "status": "urgent_human_review_required" if triggered else "no_reported_red_flag",
        "triggered_rules": triggered,
        "unknown_fields": unknown,
        "note": "A negative result only means no selected red flag was reported.",
    }


def build_vital_sign_review(checkin: dict[str, Any]) -> dict[str, Any]:
    """Preserve vitals and use only externally/mission-configured review flags.

    The engine intentionally does not declare a universal healthy range for
    astronauts. A validated mission protocol or device may supply a flag.
    """
    vitals = checkin.get("vitals", {})
    fields = [
        "heart_rate_bpm",
        "spo2_percent",
        "respiratory_rate_bpm",
        "body_temperature_c",
        "blood_pressure_systolic",
        "blood_pressure_diastolic",
        "hrv_ms",
        "weight_kg",
    ]
    recorded = {field: vitals.get(field) for field in fields if vitals.get(field) is not None}
    invalid = [field for field, value in recorded.items() if not isinstance(value, (int, float))]
    flags = vitals.get("mission_protocol_review_flags", [])
    if not isinstance(flags, list):
        flags = ["vitals.mission_protocol_review_flags must be a list"]

    return {
        "status": "human_review_required" if flags or invalid else "recorded_no_engine_threshold_applied",
        "recorded_vitals": recorded,
        "mission_protocol_review_flags": flags,
        "invalid_fields": invalid,
        "note": "Values are recorded. This prototype applies no independent clinical threshold."
    }


def build_environment_attachment(checkin: dict[str, Any]) -> dict[str, Any]:
    """Describe the sensor attachment without fabricating missing data."""
    environment = checkin.get("environment")
    if not isinstance(environment, dict) or not environment:
        return {
            "status": "environmental_data_unavailable",
            "message": "Environmental data unavailable.",
            "is_simulated": None,
        }

    required_attachment_fields = ["measured_at_utc", "location_id", "source_id"]
    missing = [field for field in required_attachment_fields if environment.get(field) in (None, "")]
    linkage = checkin.get("environment_linkage", {})
    linkage = linkage if isinstance(linkage, dict) else {}
    return {
        "status": "attached" if not missing else "partially_attached",
        "temperature_c": environment.get("temperature_c"),
        "humidity_percent": environment.get("humidity_percent"),
        "co2_ppm": environment.get("co2_ppm"),
        "anomaly_flag": environment.get("anomaly_flag"),
        "anomaly_score": environment.get("anomaly_score"),
        "sensor_location_id": environment.get("location_id"),
        "sensor_timestamp_utc": environment.get("measured_at_utc"),
        "source_id": environment.get("source_id"),
        "is_simulated": environment.get("is_simulated"),
        "missing_attachment_fields": missing,
        "time_overlap_confirmed": linkage.get("symptom_exposure_time_overlap_confirmed"),
        "location_match_confirmed": linkage.get("location_match_confirmed"),
        "note": "Anomaly status is an environmental observation, not proof of a health cause.",
    }


def build_headache_patterns(
    checkin: dict[str, Any],
    red_flags: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return partial evidence cards, never a diagnosis or probability."""
    headache = headache_record(checkin)

    if headache.get("present") is not True or red_flags["triggered_rules"]:
        return []

    cards: list[dict[str, Any]] = []

    migraine_support: list[dict[str, Any]] = []
    migraine_conflicts: list[dict[str, Any]] = []
    migraine_missing: list[str] = []

    expected_migraine = {
        "pain_location": "unilateral",
        "pain_quality": "pulsating",
        "routine_activity_worsens_or_is_avoided": True,
    }

    for field, expected in expected_migraine.items():
        value = normalized_text(headache.get(field))

        if field == "pain_location" and value in {"left", "right"}:
            value = "unilateral"
        elif field == "pain_location" and value == "both_sides":
            value = "bilateral"

        if value is None:
            migraine_missing.append(f"headache.{field}")
        elif value == expected:
            migraine_support.append(
                evidence(
                    f"headache.{field}",
                    value,
                    "Matches this limited reference feature.",
                )
            )
        else:
            migraine_conflicts.append(
                evidence(
                    f"headache.{field}",
                    value,
                    "Differs from this limited reference feature.",
                )
            )

    associated = headache.get("associated_symptoms")

    if associated is None:
        associated = [
            name
            for name, field in {
                "nausea": "nausea_or_vomiting",
                "light_sensitivity": "light_sensitivity",
                "sound_sensitivity": "sound_sensitivity",
            }.items()
            if headache.get(field) is True
        ]

    if associated is None:
        migraine_missing.append("headache.associated_symptoms")
    elif any(
        item in associated
        for item in ["nausea", "vomiting", "light_sensitivity", "sound_sensitivity"]
    ):
        migraine_support.append(
            evidence(
                "headache.associated_symptoms",
                associated,
                "Associated symptom group reported.",
            )
        )

    cards.append({
        "rule_id": "HA_PATTERN_MIGRAINE_001",
        "label": "Migraine-like pattern",
        "status": "partial_evidence_only",
        "supporting_evidence": migraine_support,
        "conflicting_evidence": migraine_conflicts,
        "missing_fields": migraine_missing,
        "not_assessed": [
            "Full episode duration and recurrence criteria",
            "Other headache causes",
            "Treatment response",
            "Complete clinical examination",
        ],
        "source_id": "NICE_CG150_TABLE1",
        "clinically_reviewed": False,
    })

    tension_support: list[dict[str, Any]] = []
    tension_conflicts: list[dict[str, Any]] = []
    tension_missing: list[str] = []

    expected_tension = {
        "pain_location": "bilateral",
        "pain_quality": "pressure_or_tightening",
        "routine_activity_worsens_or_is_avoided": False,
    }

    for field, expected in expected_tension.items():
        value = normalized_text(headache.get(field))

        if field == "pain_location" and value in {"left", "right"}:
            value = "unilateral"
        elif field == "pain_location" and value == "both_sides":
            value = "bilateral"
        elif field == "pain_quality" and value in {"pressure", "tightening"}:
            value = "pressure_or_tightening"

        if value is None:
            tension_missing.append(f"headache.{field}")
        elif value == expected:
            tension_support.append(
                evidence(
                    f"headache.{field}",
                    value,
                    "Matches this limited reference feature.",
                )
            )
        else:
            tension_conflicts.append(
                evidence(
                    f"headache.{field}",
                    value,
                    "Differs from this limited reference feature.",
                )
            )

    cards.append({
        "rule_id": "HA_PATTERN_TENSION_001",
        "label": "Tension-type-like pattern",
        "status": "partial_evidence_only",
        "supporting_evidence": tension_support,
        "conflicting_evidence": tension_conflicts,
        "missing_fields": tension_missing,
        "not_assessed": [
            "Full episode duration and recurrence criteria",
            "Other headache causes",
            "Treatment response",
            "Complete clinical examination",
        ],
        "source_id": "NICE_CG150_TABLE1",
        "clinically_reviewed": False,
    })

    return cards


def build_context_cards(checkin: dict[str, Any]) -> list[dict[str, Any]]:
    """Build transparent context cards from reported facts, not causal claims."""
    cards: list[dict[str, Any]] = []
    headache_present = headache_record(checkin).get("present") is True
    context = checkin.get("daily_context", {})
    environment = checkin.get("environment", {})

    if headache_present and context.get("fluid_intake_ml") is not None:
        cards.append({
            "rule_id": "CONTEXT_HYDRATION_001",
            "label": "Hydration context",
            "status": "context_available",
            "supporting_evidence": [evidence("daily_context.fluid_intake_ml", context["fluid_intake_ml"], "Reported fluid intake is available for review.")],
            "claim_limit": "This does not establish dehydration or a cause of headache.",
        })

    if headache_present and context.get("sleep_hours") is not None:
        cards.append({
            "rule_id": "CONTEXT_SLEEP_001",
            "label": "Sleep context",
            "status": "context_available",
            "supporting_evidence": [evidence("daily_context.sleep_hours", context["sleep_hours"], "Reported sleep duration is available for review.")],
            "claim_limit": "This does not establish a sleep-related cause.",
        })

    linkage_fields = [
        "crew_exposure_confirmed",
        "location_match_confirmed",
        "symptom_exposure_time_overlap_confirmed",
        "measurement_quality_accepted",
    ]
    linkage = checkin.get("environment_linkage", {})
    complete_linkage = all(linkage.get(field) is True for field in linkage_fields)
    if headache_present and complete_linkage and environment.get("anomaly_flag") is True:
        cards.append({
            "rule_id": "CONTEXT_ENVIRONMENT_001",
            "label": "Environmental context",
            "status": "context_available_for_review",
            "supporting_evidence": [
                evidence("environment.anomaly_flag", True, "An environmental pattern was flagged by the anomaly model."),
                evidence("environment.co2_ppm", environment.get("co2_ppm"), "CO₂ measurement linked to the review time and location."),
                evidence("environment.location_id", environment.get("location_id"), "Sensor location matches reported crew location."),
            ],
            "claim_limit": "Association is not causation. Review other explanations and sensor quality.",
        })
    return cards


def build_actions(checkin: dict[str, Any], red_flags: dict[str, Any], context_cards: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return safe workflow actions, not treatment or medicine instructions."""
    if red_flags["triggered_rules"]:
        return [
            {"priority": "urgent", "action": "Request immediate authorized medical review.", "approval": "medical_reviewer_required"},
            {"priority": "urgent", "action": "Consider task pause or delay through the mission leader workflow.", "approval": "leader_or_medical_reviewer_required"},
        ]

    actions = [
        {"priority": "routine", "action": "Review the check-in and repeat it if symptoms change.", "approval": "not_required"},
        {"priority": "routine", "action": "Use authorized mission procedures for rest, hydration, or activity adjustment when appropriate.", "approval": "mission_protocol_required"},
    ]
    if any(card["rule_id"] == "CONTEXT_ENVIRONMENT_001" for card in context_cards):
        actions.append({
            "priority": "review", "action": "Verify sensor quality and request habitat/environment review through approved procedures.",
            "approval": "mission_protocol_required",
        })
    actions.append({
        "priority": "review", "action": "Medication decisions require an authorized medical reviewer and inventory protocol.",
        "approval": "medical_reviewer_required",
    })
    return actions


def evaluate_checkin(checkin: dict[str, Any]) -> dict[str, Any]:
    """Create one transparent, serializable HabitatPulse review report."""
    input_quality = build_input_quality(checkin)
    symptom_summary = build_symptom_summary(checkin)
    red_flags = build_red_flag_review(checkin)
    vital_review = build_vital_sign_review(checkin)
    environment_attachment = build_environment_attachment(checkin)
    pattern_cards = build_headache_patterns(checkin, red_flags)
    context_cards = build_context_cards(checkin)
    actions = build_actions(checkin, red_flags, context_cards)

    workflow_status = "draft_evidence_ready_for_review"
    if red_flags["triggered_rules"]:
        workflow_status = "medical_review_required"
    elif (
        input_quality["missing_required_fields"]
        or input_quality["invalid_fields"]
        or input_quality["symptom_input_issues"]
        or red_flags["unknown_fields"]
    ):
        workflow_status = "additional_review_answers_required"

    return {
        "report_id": f"HP-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ruleset": deepcopy(RULESET),
        "crew_id": checkin.get("crew_id"),
        "checkin_recorded_at_utc": checkin.get("recorded_at_utc"),
        "basic_information": {
            "crew_id": checkin.get("crew_id"),
            "recorded_at_utc": checkin.get("recorded_at_utc"),
            "location_id": get_path(checkin, "daily_context.location_id"),
            "current_mission_task": get_path(checkin, "daily_context.current_mission_task"),
            "recent_task_completed": get_path(checkin, "daily_context.recent_task_completed"),
            "notes": get_path(checkin, "daily_context.notes"),
        },
        "general_wellbeing": {
            "overall_wellbeing_1_to_5": get_path(checkin, "daily_context.overall_wellbeing_1_to_5"),
            "energy_fatigue_level": get_path(checkin, "daily_context.energy_fatigue_level"),
            "mood_stress_1_to_5": get_path(checkin, "daily_context.mood_stress_1_to_5"),
            "sleep_hours": get_path(checkin, "daily_context.sleep_hours"),
            "sleep_quality": get_path(checkin, "daily_context.sleep_quality"),
            "fluid_intake_ml": get_path(checkin, "daily_context.fluid_intake_ml"),
            "appetite": get_path(checkin, "daily_context.appetite"),
            "activity_level": get_path(checkin, "daily_context.activity_level"),
            "exercise_completed": get_path(checkin, "daily_context.exercise_completed"),
            "current_medication_taken": get_path(checkin, "daily_context.current_medication_taken"),
        },
        "workflow_status": workflow_status,
        "disclaimer": DISCLAIMER,
        "input_quality": {**input_quality, "unknown_safety_fields": red_flags["unknown_fields"]},
        "red_flag_review": red_flags,
        "vital_sign_review": vital_review,
        "symptom_summary": symptom_summary,
        "environment_attachment": environment_attachment,
        "possible_patterns_for_review": pattern_cards,
        "context_cards": context_cards,
        "recommended_next_actions": actions,
        "medicine_recommendation": {
            "status": "not_generated",
            "reason": "The engine does not select medication or dose.",
            "approval_required": True,
        },
        "task_delay": {
            "status": "consider_human_review",
            "automatic_decision": False,
            "reason": "Task changes require mission-leader or authorized medical review.",
        },
    }


def main() -> None:
    # Windows consoles may default to CP1252 and cannot print labels such as CO₂.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("Usage: python healthcare_rule_engine.py sample_checkin.json")
        raise SystemExit(1)
    input_path = Path(sys.argv[1])
    checkin = json.loads(input_path.read_text(encoding="utf-8"))
    report = evaluate_checkin(checkin)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
