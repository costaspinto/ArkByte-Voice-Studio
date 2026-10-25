import Link from "next/link";
import { ArrowLeft, SearchX } from "lucide-react";

export default function NotFound() {
  return (
    <main className="fallback-screen">
      <section className="fallback-card">
        <div className="fallback-icon"><SearchX size={24} /></div>
        <p className="eyebrow">404 · NOT FOUND</p>
        <h1>This workspace page does not exist.</h1>
        <p>The link may be outdated or the project may have moved.</p>
        <Link className="button button-primary" href="/"><ArrowLeft size={16} /> Return to Studio</Link>
      </section>
    </main>
  );
}
