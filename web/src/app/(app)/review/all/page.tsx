import { ComingSoonPanel } from "@/components/app/ComingSoonPanel";

export default function ReviewAllPage() {
  return (
    <ComingSoonPanel
      command="conf-t review --all"
      title="Review All Failed Commands"
      taskLabel="Task 13"
      description="The full failed-command queue review flow is coming in Task 13."
    />
  );
}