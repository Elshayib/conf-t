import { ComingSoonPanel } from "@/components/app/ComingSoonPanel";

export default function StatsPage() {
  return (
    <ComingSoonPanel
      command="conf-t stats"
      title="Progress & Stats"
      taskLabel="Task 14"
      description="Accuracy, attempts, and platform breakdown are coming in Task 14."
    />
  );
}