export default function Loading() {
  return (
    <main className="fallback-screen" aria-busy="true" aria-live="polite">
      <section className="fallback-card loading-card">
        <div className="loading-mark" />
        <p className="eyebrow">ARKBYTE VOICE STUDIO</p>
        <h1>Preparing your workspace…</h1>
        <p>Loading the local creator interface.</p>
      </section>
    </main>
  );
}
