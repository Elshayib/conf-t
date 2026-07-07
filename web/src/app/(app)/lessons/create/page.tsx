import { ComingSoonPanel } from "@/components/app/ComingSoonPanel";

export default function CreateLessonPage() {
  return (
    <ComingSoonPanel
      command="conf-t lessons create"
      title="Create a Custom Lesson"
      taskLabel="Task 16"
      description="The custom lesson wizard is coming in Task 16."
    />
  );
}