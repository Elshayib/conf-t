import Link from "next/link";
import { getLandingStats } from "@/lib/lessons/index";

export const dynamic = "force-static";

const PLATFORM_STYLES: Record<
  string,
  {
    border: string;
    accent: string;
    badge: string;
    glow: string;
    description: string;
    highlight?: string;
  }
> = {
  Cisco: {
    border: "border-cyan-500/40",
    accent: "text-cyan-400",
    badge: "bg-cyan-500/15 text-cyan-300",
    glow: "shadow-cyan-500/10",
    description:
      "CCNA-depth routing, switching, VLANs, ACLs, and first-hop redundancy — real IOS syntax.",
    highlight: "CCNA",
  },
  Linux: {
    border: "border-amber-500/30",
    accent: "text-amber-400",
    badge: "bg-amber-500/10 text-amber-300",
    glow: "shadow-amber-500/5",
    description:
      "Bash, systemd, networking, and file permissions on real Linux shells.",
  },
  PowerShell: {
    border: "border-blue-500/30",
    accent: "text-blue-400",
    badge: "bg-blue-500/10 text-blue-300",
    glow: "shadow-blue-500/5",
    description:
      "Cmdlet pipelines, remoting, and Windows automation from the prompt.",
  },
  Git: {
    border: "border-orange-500/30",
    accent: "text-orange-400",
    badge: "bg-orange-500/10 text-orange-300",
    glow: "shadow-orange-500/5",
    description:
      "Branching, merging, rebasing, and recovery — muscle memory for version control.",
  },
  Docker: {
    border: "border-sky-500/30",
    accent: "text-sky-400",
    badge: "bg-sky-500/10 text-sky-300",
    glow: "shadow-sky-500/5",
    description:
      "Images, containers, networks, and compose — hands-on container workflows.",
  },
};

const DEFAULT_PLATFORM_STYLE = {
  border: "border-emerald-500/30",
  accent: "text-emerald-400",
  badge: "bg-emerald-500/10 text-emerald-300",
  glow: "shadow-emerald-500/5",
  description: "Practice real commands in an interactive terminal.",
};

function StatItem({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <p className="font-mono text-2xl font-semibold text-emerald-400 sm:text-3xl">
        {value}
      </p>
      <p className="mt-1 font-mono text-xs uppercase tracking-wider text-zinc-500">
        {label}
      </p>
    </div>
  );
}

export default function LandingPage() {
  const stats = getLandingStats();

  return (
    <div className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(16,185,129,0.08)_0%,_transparent_50%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <section className="relative mx-auto max-w-6xl px-4 pb-16 pt-16 sm:px-6 sm:pt-24">
        <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
          <div>
            <p className="font-mono text-xs text-emerald-500/80">
              $ conf-t --welcome
            </p>
            <h1 className="mt-4 font-mono text-3xl font-bold leading-tight tracking-tight text-zinc-50 sm:text-4xl lg:text-5xl">
              10 minutes a day to master{" "}
              <span className="text-emerald-400">real CLI</span>
            </h1>
            <p className="mt-5 max-w-xl font-mono text-sm leading-relaxed text-zinc-400 sm:text-base">
              CCNA-level Cisco depth with multi-platform breadth. Type actual
              commands in a terminal — not multiple choice. Build muscle memory
              for the prompts you&apos;ll use on the job.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Link
                href="/platforms/cisco"
                className="inline-flex h-11 items-center justify-center rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-6 font-mono text-sm font-medium text-cyan-300 transition-colors hover:border-cyan-500/60 hover:bg-cyan-500/20"
              >
                Browse Lessons →
              </Link>
              <Link
                href="/signup"
                className="inline-flex h-11 items-center justify-center rounded-lg bg-emerald-500 px-6 font-mono text-sm font-medium text-[#0a0a0a] transition-colors hover:bg-emerald-400"
              >
                Get Started
              </Link>
            </div>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-[#0d0d0d] shadow-2xl shadow-black/50">
            <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3">
              <span className="h-3 w-3 rounded-full bg-red-500/80" />
              <span className="h-3 w-3 rounded-full bg-amber-500/80" />
              <span className="h-3 w-3 rounded-full bg-emerald-500/80" />
              <span className="ml-2 font-mono text-xs text-zinc-600">
                conf-t practice
              </span>
            </div>
            <div className="space-y-2 p-5 font-mono text-sm leading-relaxed">
              <p>
                <span className="text-emerald-500">user@conf-t</span>
                <span className="text-zinc-600">:</span>
                <span className="text-cyan-400">~</span>
                <span className="text-zinc-600">$ </span>
                <span className="text-zinc-300">conf-t practice cisco_vlan</span>
              </p>
              <p className="text-zinc-500">
                # Create VLAN 10 named SALES on a Cisco switch
              </p>
              <p>
                <span className="text-emerald-500">Switch(config)</span>
                <span className="text-zinc-600"># </span>
                <span className="text-zinc-300">vlan 10</span>
              </p>
              <p>
                <span className="text-emerald-500">Switch(config-vlan)</span>
                <span className="text-zinc-600"># </span>
                <span className="text-zinc-300">name SALES</span>
                <span className="ml-2 text-emerald-400">✓</span>
              </p>
              <p className="pt-2 text-xs text-zinc-600">
                640 tasks across 5 platforms — spaced repetition keeps it
                sticky.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="relative border-y border-zinc-800/80 bg-[#0d0d0d]/60">
        <div className="mx-auto grid max-w-6xl grid-cols-3 gap-6 px-4 py-10 sm:px-6">
          <StatItem value={String(stats.lessonCount)} label="Lessons" />
          <StatItem value={String(stats.taskCount)} label="Tasks" />
          <StatItem value={String(stats.platformCount)} label="Platforms" />
        </div>
      </section>

      <section className="relative mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
        <div className="mb-10 text-center">
          <p className="font-mono text-xs text-emerald-500/80">
            $ conf-t platforms --list
          </p>
          <h2 className="mt-3 font-mono text-2xl font-semibold text-zinc-100 sm:text-3xl">
            One curriculum, five platforms
          </h2>
          <p className="mx-auto mt-3 max-w-2xl font-mono text-sm text-zinc-500">
            Start with Cisco for CCNA depth, then branch into Linux, Git,
            Docker, and PowerShell.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {stats.platforms.map((platform) => {
            const styles =
              PLATFORM_STYLES[platform.name] ?? DEFAULT_PLATFORM_STYLE;
            const isCisco = platform.name === "Cisco";

            return (
              <Link
                key={platform.name}
                href={`/platforms/${platform.slug}`}
                className={`group rounded-lg border bg-[#0d0d0d] p-5 transition-all hover:bg-zinc-900/40 ${styles.border} ${
                  isCisco
                    ? "shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-500/20 lg:col-span-1"
                    : `shadow-md ${styles.glow}`
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block rounded px-2 py-0.5 font-mono text-xs ${styles.badge}`}
                  >
                    {platform.name}
                  </span>
                  {styles.highlight ? (
                    <span className="rounded bg-cyan-500/20 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-cyan-300">
                      {styles.highlight}
                    </span>
                  ) : null}
                </div>
                <p
                  className={`mt-3 font-mono text-lg font-semibold ${styles.accent}`}
                >
                  {platform.lessonCount} lesson
                  {platform.lessonCount === 1 ? "" : "s"}
                </p>
                <p className="mt-1 font-mono text-xs text-zinc-500">
                  {platform.taskCount} tasks
                </p>
                <p className="mt-3 font-mono text-xs leading-relaxed text-zinc-500 group-hover:text-zinc-400">
                  {styles.description}
                </p>
                <p className="mt-4 font-mono text-xs text-zinc-600 group-hover:text-emerald-500/80">
                  Browse {platform.name} lessons →
                </p>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="relative border-t border-zinc-800/80 bg-[#0d0d0d]/40">
        <div className="mx-auto max-w-6xl px-4 py-16 text-center sm:px-6 sm:py-20">
          <p className="font-mono text-xs text-emerald-500/80">
            $ conf-t signup --free
          </p>
          <h2 className="mt-3 font-mono text-2xl font-semibold text-zinc-100">
            Ready to build CLI muscle memory?
          </h2>
          <p className="mx-auto mt-3 max-w-lg font-mono text-sm text-zinc-500">
            Free to start. Practice real commands with spaced repetition and
            track progress across every platform.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/signup"
              className="inline-flex h-11 items-center justify-center rounded-lg bg-emerald-500 px-8 font-mono text-sm font-medium text-[#0a0a0a] transition-colors hover:bg-emerald-400"
            >
              Get Started — it&apos;s free
            </Link>
            <Link
              href="/platforms/cisco"
              className="inline-flex h-11 items-center justify-center rounded-lg border border-zinc-700 px-8 font-mono text-sm text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-200"
            >
              Browse Cisco lessons
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}