"""Generate offline, clearly labelled HabitatPulse demo data.

Environment: 5-minute simulated readings from --start through today (UTC).
Health: daily 15-minute PMC for the first 7 days, then weekly 15-minute PMC.
This is fictional UI demo data, not clinical data or flight telemetry.
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import joblib
import pandas as pd

from db_config import get_connection

ENV_MARKER = "SIMULATED_DEMO_ENV_V1"
HEALTH_MARKER = "SIMULATED_DEMO_HEALTH_V2"
ROOT = Path(__file__).resolve().parent
MODEL = ROOT.parent / "training_outputs" / "environment_iforest_v01.joblib"


def reference_ids(cursor):
    cursor.execute("SELECT id, crew_code FROM crew_members WHERE active=TRUE ORDER BY crew_code")
    crew = [(int(row[0]), str(row[1])) for row in cursor.fetchall()]
    cursor.execute("SELECT id FROM habitat_modules WHERE module_code='HAB-MODULE-B' LIMIT 1")
    module = cursor.fetchone()
    cursor.execute("SELECT id FROM sensor_sources WHERE source_code='SIM-HAB-5MIN' LIMIT 1")
    source = cursor.fetchone()
    if not module or not source or not crew:
        raise RuntimeError("Run sample_data.sql first; HAB-MODULE-B, SIM-HAB-5MIN, and active crew are required.")
    return crew, int(module[0]), int(source[0])


def score_row(model, features, temperature, humidity, co2):
    """Score one row using the feature names used by the RR-28 model."""
    row = {
        "Temp_degC_ISS": temperature,
        "RH_percent_ISS": humidity,
        "CO2_ppm_ISS": co2,
    }
    frame = pd.DataFrame([[row[name] for name in features]], columns=features)
    return float(-model.score_samples(frame)[0])


def generate_environment(cursor, module_id, source_id, start, end, rng):
    if not MODEL.exists():
        raise RuntimeError(f"Model not found: {MODEL}")
    bundle = joblib.load(MODEL)
    threshold = float(bundle["threshold"])
    model = bundle["model"]
    features = bundle["features"]
    cursor.execute("DELETE FROM environment_records WHERE source_id=%s AND is_simulated=TRUE", (source_id,))
    sql = """INSERT INTO environment_records (measured_at_utc,module_id,source_id,is_simulated,
             temperature_c,humidity_percent,co2_ppm,anomaly_score,anomaly_threshold,anomaly_flag,anomaly_model_version)
             VALUES (%s,%s,%s,TRUE,%s,%s,%s,%s,%s,%s,%s)"""
    # The normal anchor below was checked against the RR-28-trained model:
    # its score is below the saved 99th-percentile threshold.  It is therefore
    # suitable for fictional *normal* readings, unlike the old 900 ppm values.
    event_days = {17, 43, 69, 95, max(7, (end.date() - start.date()).days)}
    batch=[]; current=start; stored=0
    while current <= end:
        phase=(current.hour*60+current.minute)/1440*math.tau
        # Calibrated to the RR-28 model's normal training distribution.
        # A 900 ppm / 51% baseline was out-of-distribution and was therefore
        # flagged by the model on every generated row.
        temp=round(22.4+0.12*math.sin(phase)+rng.gauss(0,.05),2)
        humidity=round(38+1.5*math.sin(phase+.7)+rng.gauss(0,.45),1)
        co2=round(3900+170*math.sin(phase-.4)+rng.gauss(0,28),1)
        # Sparse, fictional, multi-signal events.  A two-hour window provides
        # enough adjacent five-minute samples for the UI's persistent-event
        # grouping, without presenting a continuous alarm condition.
        day_offset = (current.date() - start.date()).days
        if day_offset in event_days and current.hour in {9, 10}:
            temp += 1.2; humidity += 11; co2 += 1_100
        score = score_row(model, features, temp, humidity, co2)
        flag = score > threshold
        batch.append((current,module_id,source_id,temp,humidity,co2,score,threshold,flag,bundle.get("model_version","environment-iforest-v0.1")))
        if len(batch)==500:
            cursor.executemany(sql,batch); stored+=len(batch); batch=[]
        current += timedelta(minutes=5)
    if batch: cursor.executemany(sql,batch); stored+=len(batch)
    return stored


def generate_health(cursor, crew, module_id, start_day, end_day, rng):
    inserted=0
    cursor.execute("SELECT id FROM checkins WHERE notes LIKE %s", (f"{HEALTH_MARKER}%",))
    existing={int(row[0]) for row in cursor.fetchall()}
    for offset in range((end_day-start_day).days+1):
        day=start_day+timedelta(days=offset)
        # Mission policy: days 0–6 daily; afterwards one Monday 15-minute PMC.
        if offset>=7 and day.weekday()!=0: continue
        kind="daily" if offset<7 else "weekly"
        for index,(crew_id,crew_code) in enumerate(crew):
            recorded=datetime.combine(day,time(8+(index%2),10+index*7))
            cursor.execute("SELECT id FROM checkins WHERE crew_id=%s AND recorded_at_utc=%s AND notes LIKE %s",(crew_id,recorded,f"{HEALTH_MARKER}%"))
            if cursor.fetchone(): continue
            sleep=round(max(5.2,min(8.8,7.2+rng.gauss(0,.45))),2)
            wellbeing=4 if sleep>=6.2 else 3
            notes=f"{HEALTH_MARKER}; fictional {kind} 15-minute PMC schedule record for {crew_code}; not clinical data."
            cursor.execute("""INSERT INTO checkins (crew_id,recorded_at_utc,module_id,current_mission_task,recent_task_completed,notes,
                overall_wellbeing,fatigue_level,mood_stress_level,sleep_hours,sleep_quality,fluid_intake_ml,appetite,activity_level,exercise_completed,medication_taken)
                VALUES (%s,%s,%s,'Simulated PMC','Simulated exercise',%s,%s,'mild',%s,%s,'fair',%s,'normal','normal',TRUE,'not_applicable')""",
                (crew_id,recorded,module_id,notes,wellbeing,rng.randint(2,3),sleep,rng.randint(1600,2400)))
            checkin_id=int(cursor.lastrowid)
            cursor.execute("INSERT INTO vital_signs (checkin_id,heart_rate_bpm,spo2_percent,respiratory_rate_bpm,body_temperature_c,hrv_ms,weight_kg) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (checkin_id,round(70+rng.gauss(0,4),1),round(98+rng.gauss(0,.4),1),round(15+rng.gauss(0,1),1),round(36.7+rng.gauss(0,.15),2),round(45+rng.gauss(0,6),1),round(71+rng.gauss(0,.2),1)))
            cursor.execute("INSERT INTO safety_reviews (checkin_id,severe_chest_discomfort,severe_breathing_difficulty,loss_of_consciousness,sudden_neurological_change,sudden_severe_headache,rapidly_worsening_symptoms,urgent_human_review_required) VALUES (%s,FALSE,FALSE,FALSE,FALSE,FALSE,FALSE,FALSE)",(checkin_id,))
            # Six sparse fictional event records across the whole demo period.
            # All remaining scheduled PMC rows have no symptom record.
            event_map = {
                (2, "CREW-02"): ("headache", 4, "mild sleep reduction; human review context only"),
                (5, "CREW-04"): ("fatigue", 3, "post-maintenance fatigue pattern; fictional"),
                (16, "CREW-01"): ("sleep_difficulty", 4, "sleep-quality follow-up pattern; fictional"),
                (30, "CREW-03"): ("muscle_or_joint_pain", 3, "exercise-related self-report; fictional"),
                (44, "CREW-05"): ("headache", 5, "environment-time-overlap review example; not causal"),
                (58, "CREW-02"): ("nausea_or_vomiting", 3, "short-duration self-report; fictional"),
            }
            event = event_map.get((offset, crew_code))
            if event:
                symptom, severity, note = event
                cursor.execute("""INSERT INTO symptom_records (checkin_id,symptom_name,severity_0_to_10,onset_at_utc,onset_status,
                    duration_minutes,duration_status,symptom_pattern,progression,mission_task_effect,similar_episode,action_or_medication_taken,note)
                    VALUES (%s,%s,%s,%s,'known',%s,'known','intermittent','stable','some_difficulty','unknown',%s,%s)""",
                    (checkin_id, symptom, severity, recorded-timedelta(hours=2), rng.randint(45,180),
                     'No treatment recommendation generated.', f'{HEALTH_MARKER}; {note}'))
            cursor.execute("INSERT INTO outbox (entity_type,entity_id,status) VALUES ('checkin',%s,'pending_sync')",(checkin_id,)); inserted+=1
    return inserted


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--start",type=date.fromisoformat,default=date(2026,8,1))
    parser.add_argument("--seed",type=int,default=20261114)
    args=parser.parse_args()
    # Generate only through the current UTC time, never through future hours.
    now=datetime.now(timezone.utc).replace(tzinfo=None,second=0,microsecond=0)
    now -= timedelta(minutes=now.minute % 5)
    today=now.date()
    if args.start>today: raise SystemExit("--start cannot be after today")
    rng=random.Random(args.seed)
    with get_connection() as conn:
        cur=conn.cursor(); crew,module_id,source_id=reference_ids(cur)
        env=generate_environment(cur,module_id,source_id,datetime.combine(args.start,time.min),now,rng)
        health=generate_health(cur,crew,module_id,args.start,today,rng); conn.commit()
    print(f"Environment: {env:,} five-minute simulated records ({ENV_MARKER}).")
    print(f"Health: {health:,} simulated scheduled PMC check-ins ({HEALTH_MARKER}).")

if __name__=="__main__": main()
