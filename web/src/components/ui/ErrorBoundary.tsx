"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import Link from "next/link";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="mx-auto flex min-h-[50vh] max-w-3xl items-center px-4 py-12 sm:px-6">
          <div className="w-full rounded-lg border border-red-500/30 bg-[#0d0d0d] p-6 sm:p-8">
            <p className="font-mono text-xs uppercase tracking-wide text-red-400/80">
              Application error
            </p>
            <h1 className="mt-2 font-mono text-xl font-semibold text-zinc-100">
              {this.props.fallbackTitle ?? "Something went wrong"}
            </h1>
            <p className="mt-3 font-mono text-sm leading-relaxed text-zinc-400">
              An unexpected error occurred. Your progress is saved locally when
              possible — try reloading this section.
            </p>
            {this.state.error?.message ? (
              <p className="mt-4 rounded border border-zinc-800 bg-black/40 px-3 py-2 font-mono text-xs text-zinc-500">
                {this.state.error.message}
              </p>
            ) : null}
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={this.handleRetry}
                className="min-h-11 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 font-mono text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20"
              >
                Try again
              </button>
              <Link
                href="/dashboard"
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-zinc-700 px-4 py-3 font-mono text-sm text-zinc-300 transition-colors hover:border-zinc-600 hover:text-zinc-100"
              >
                Back to dashboard
              </Link>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}