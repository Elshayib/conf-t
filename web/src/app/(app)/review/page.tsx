import { ComingSoonPanel } from "@/components/app/ComingSoonPanel";

export default function ReviewPage() {
  return (
    <ComingSoonPanel
      command="conf-t review"
      title="Daily Review"
      taskLabel="Task 13"
      description="Spaced repetition for due commands is coming in Task 13."
    />
  );
}