"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function AppError({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    // Keep the message generic in the UI. Next.js logs the detailed error server-side.
    console.error("ArkByte Voice Studio UI error", error.digest || error.name);
  }, [error]);

  return (
    <main className="fallback-screen">
      <section className="fallback-card" role="alert">
        <div className="fallback-icon"><AlertTriangle size={24} /></div>
        <p className="eyebrow">RECOVERABLE APPLICATION ERROR</p>
        <h1>Something interrupted this workspace.</h1>
        <p>The page could not finish rendering. Your saved projects and voice data are stored by the local service and are not removed by this recovery action.</p>
        {error.digest ? <code className="fallback-code">Reference: {error.digest}</code> : null}
        <button className="button button-primary" onClick={reset}><RefreshCw size={16} /> Try again</button>
      </section>
    </main>
  );
}
