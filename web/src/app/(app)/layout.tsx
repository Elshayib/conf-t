import { AppShell } from "@/components/app/AppShell";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

export const dynamic = "force-dynamic";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <ErrorBoundary>{children}</ErrorBoundary>
    </AppShell>
  );
}