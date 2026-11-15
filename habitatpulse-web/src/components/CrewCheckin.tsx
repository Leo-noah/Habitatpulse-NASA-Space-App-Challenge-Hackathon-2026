import DemoCheckin, { type DemoRecord } from "./DemoCheckin";

type CrewMember = {
  id: string;
  name: string;
  role: string;
};

type CrewCheckinProps = {
  onSaved?: (record: DemoRecord) => void;
};

const DEFAULT_CREW: CrewMember = {
  id: "CREW-01",
  name: "Alex Morgan",
  role: "Mission Specialist",
};

export default function CrewCheckin({ onSaved }: CrewCheckinProps) {
  return (
    <section className="crew-checkin-page">
      <div className="page-intro">
        <h2>Crew check-in</h2>
      </div>

      <DemoCheckin
        crewId={DEFAULT_CREW.id}
        crewName={DEFAULT_CREW.name}
        module="HAB-MODULE-B"
        onSaved={onSaved}
      />

      <div className="overview-footnote">
        ⓘ This is a prototype check-in form. It does not diagnose illness,
        prescribe medicine, or approve mission-task changes.
      </div>
    </section>
  );
}