import { ComingSoonPanel } from "@/components/app/ComingSoonPanel";

export default function ResetProgressPage() {
  return (
    <ComingSoonPanel
      command="conf-t reset"
      title="Reset All Progress"
      taskLabel="Task 15"
      description="Progress reset with confirmation is coming in Task 15."
    />
  );
}