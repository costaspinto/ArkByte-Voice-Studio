"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, AudioLines, CheckCircle2, Cpu, Info, Loader2, Play, ShieldAlert, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { HistoryItem, VoiceProfile } from "@/lib/types";

type Notify = (title: string, message: string, kind?: "success" | "error" | "info" | "warning") => void;
type ModelInfo = { id: string; name: string; package: string; role: string; status: string; integrated: boolean };
type ModelRegistry = { models: ModelInfo[]; active_model: string; note: string; speaker_identity?: { id: string; name: string; installed: boolean; weights_cached: boolean; status: string; first_use_download: boolean }; transcription?: { id: string; name: string; installed: boolean; model_size: string; loaded: boolean; status: string; first_use_download: boolean; note: string } };
type Benchmark = {
  history_id: string; profile_id: string; profile_name: string; acoustic_proxy_score: number | null;
  comparisons: Array<{ label: string; available: boolean; reference_median?: number; generated?: number; difference?: number; unit?: string; proxy_score?: number; note?: string }>;
  interpretation: string; next_step: string;
};
type Sample = { id: string; is_anchor: boolean; source_name: string; duration_seconds: number };
type ProfileDetail = { samples: Sample[] };

export default function BenchmarkLab({ profiles, history, notify }: { profiles: VoiceProfile[]; history: HistoryItem[]; notify: Notify }) {
  const [registry, setRegistry] = useState<ModelRegistry | null>(null);
  const [selectedHistory, setSelectedHistory] = useState("");
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [registryError, setRegistryError] = useState("");
  const [identityResult, setIdentityResult] = useState<{ model: string; device: string; reference_count: number; centroid_cosine_similarity: number; per_reference_cosine: number[]; score_interpretation: string } | null>(null);
  const [identityBusy, setIdentityBusy] = useState(false);

  const candidates = useMemo(() => history.filter(item => item.profile_id && item.audio_url), [history]);
  const selected = candidates.find(item => item.id === selectedHistory);

  useEffect(() => {
    api<ModelRegistry>("/api/v1/models").then(setRegistry).catch(error => setRegistryError(error instanceof Error ? error.message : "Model registry unavailable."));
  }, []);

  useEffect(() => {
    let active = true;
    setBenchmark(null); setDetail(null); setIdentityResult(null);
    if (!selected?.profile_id) return;
    api<ProfileDetail>(`/api/v1/profiles/${selected.profile_id}/detail`)
      .then(value => { if (active) setDetail(value); })
      .catch(error => { if (active) notify("Could not load reference sample", error instanceof Error ? error.message : "Profile unavailable.", "error"); });
    return () => { active = false; };
  }, [selected?.id, selected?.profile_id, notify]);

  const runBenchmark = async () => {
    if (!selectedHistory) return;
    setBusy(true);
    try {
      const result = await api<{ benchmark: Benchmark }>(`/api/v1/benchmarks/${selectedHistory}`, { method: "POST" });
      setBenchmark(result.benchmark);
    } catch (error) { notify("Benchmark failed", error instanceof Error ? error.message : "Could not analyse the output.", "error"); }
    finally { setBusy(false); }
  };

  const runIdentityComparison = async () => {
    if (!selectedHistory) return;
    setIdentityBusy(true);
    try {
      const result = await api<{ speaker_identity: NonNullable<typeof identityResult> }>(`/api/v1/benchmarks/${selectedHistory}/speaker-identity`, { method: "POST" });
      setIdentityResult(result.speaker_identity);
    } catch (error) { notify("Speaker comparison unavailable", error instanceof Error ? error.message : "Check the optional ECAPA installation and model cache.", "error"); }
    finally { setIdentityBusy(false); }
  };

  const anchor = detail?.samples.find(sample => sample.is_anchor);

  return <div className="benchmark-page">
    <div className="page-heading"><div><div className="eyebrow">VOICE QUALITY & MODEL VALIDATION</div><h1>Benchmark Studio</h1><p>Compare generated audio against the enrolled speaker dataset and inspect model availability.</p></div><div className="lab-private-pill"><Activity size={14} /> LOCAL EVALUATION</div></div>
    <section className="benchmark-hero panel"><div className="benchmark-hero-icon"><AudioLines size={25} /></div><div><h3>Measure differences, not promises</h3><p>This build calculates acoustic-profile proxies from pitch, level, spectral brightness and speech occupancy. These are not neural speaker-similarity scores and cannot certify accent accuracy.</p></div><div className="benchmark-hero-badge">PROXY METRICS</div></section>

    <div className="benchmark-grid">
      <section className="panel benchmark-compare-card">
        <div className="section-head"><div><h3>Reference vs generated audio</h3><p>Choose a saved generation that belongs to an enrolled voice profile.</p></div><span className="soft-label">A/B LISTENING</span></div>
        <div className="form-field"><label>GENERATION</label><div className="select-wrap"><select value={selectedHistory} onChange={event => setSelectedHistory(event.target.value)}><option value="">Choose generated audio…</option>{candidates.map(item => <option key={item.id} value={item.id}>{item.profile_name} · {item.script_preview.slice(0, 70)}</option>)}</select></div></div>
        {selected ? <div className="ab-audio-grid">
          <div className="ab-audio-card"><div className="ab-audio-label"><span className="ab-dot ref" /> ORIGINAL REFERENCE</div>{anchor ? <><strong>{anchor.source_name}</strong><span>{Math.round(anchor.duration_seconds)} sec · selected anchor</span><audio controls preload="none" src={`/api/v1/profile-samples/${anchor.id}/audio`} /></> : <p>No multi-recording reference dataset is available for this profile.</p>}</div>
          <div className="ab-audio-card"><div className="ab-audio-label"><span className="ab-dot generated" /> GENERATED OUTPUT</div><strong>{selected.profile_name}</strong><span>{selected.script_preview}</span><audio controls preload="none" src={selected.audio_url || undefined} /></div>
        </div> : <div className="lab-empty"><Play size={24} /><strong>Choose a completed generation</strong><p>Generate audio in Script Studio first. The generation must be linked to an enrolled voice profile.</p></div>}
        <div className="benchmark-run-row"><span><Info size={14} /> Benchmark compares the output with the profile's sample medians.</span><button className="button button-primary" onClick={() => void runBenchmark()} disabled={busy || !selectedHistory || !anchor}>{busy ? <><Loader2 size={14} className="spin" /> Analysing…</> : <><Sparkles size={14} /> Run benchmark</>}</button></div>
      </section>

      <section className="panel model-registry-card">
        <div className="section-head"><div><h3>Model registry</h3><p>Actual runtime integration status.</p></div><Cpu size={18} /></div>
        {registryError ? <p className="lab-warning-text">{registryError}</p> : !registry ? <div className="lab-loading"><Loader2 size={17} className="spin" /> Checking installed models…</div> : <>
          {registry.models.map(model => <div className="model-row" key={model.id}><div><strong>{model.name}</strong><span>{model.role}</span></div><div className="model-row-status"><i className={model.integrated ? "model-live" : "model-experimental"} />{model.status === "installed" && model.integrated ? "Installed · integrated" : model.integrated ? "Adapter ready · install package" : model.status === "installed" ? "Installed · not integrated" : "Research candidate"}</div></div>)}
          {registry.transcription && <div className="model-row"><div><strong>{registry.transcription.name}</strong><span>Draft transcripts for Voice Lab; user review is required before training export.</span></div><div className="model-row-status"><i className={registry.transcription.installed ? "model-live" : "model-experimental"} />{registry.transcription.installed ? `Available · ${registry.transcription.model_size}` : "Optional dependency missing"}</div></div>}
          <p className="model-registry-note">{registry.note}</p>
        </>}
      </section>
    </div>

    {benchmark && <section className="panel benchmark-results">
      <div className="section-head"><div><div className="eyebrow">BENCHMARK RESULT</div><h3>{benchmark.profile_name}</h3><p>Acoustic comparisons for the selected generation.</p></div><div className="benchmark-score"><strong>{benchmark.acoustic_proxy_score === null ? "—" : `${benchmark.acoustic_proxy_score}`}</strong><span>/ 100 proxy</span></div></div>
      <div className="benchmark-metric-list">{benchmark.comparisons.map(metric => <div className="benchmark-metric-row" key={metric.label}><div><strong>{metric.label}</strong><span>{metric.available ? `Reference ${metric.reference_median} · Generated ${metric.generated} ${metric.unit}` : metric.note}</span></div>{metric.available ? <div className="benchmark-metric-score"><strong>{metric.proxy_score}</strong><span>proxy</span></div> : <span className="soft-label">N/A</span>}</div>)}</div>
      <div className="benchmark-caveat"><ShieldAlert size={17} /><div><strong>Interpretation limit</strong><p>{benchmark.interpretation}</p><small>{benchmark.next_step}</small></div></div>
    </section>}

    <section className="panel ecapa-card">
      <div className="section-head"><div><h3>Neural speaker-embedding comparison</h3><p>Optional ECAPA-TDNN comparison of the generated output against the enrolled reference recordings.</p></div><span className="soft-label">MODEL-BASED SCORE</span></div>
      <div className="ecapa-status-row"><div><strong>{registry?.speaker_identity?.name || "SpeechBrain ECAPA-TDNN"}</strong><span>{registry?.speaker_identity?.status === "ready" ? "Pretrained weights cached" : registry?.speaker_identity?.installed ? "Installed · first run may download pretrained weights" : "Optional dependency not installed"}</span></div><button className="button button-primary" type="button" onClick={() => void runIdentityComparison()} disabled={!selectedHistory || identityBusy || !registry?.speaker_identity?.installed}>{identityBusy ? <><Loader2 size={14} className="spin" /> Comparing…</> : <><Activity size={14} /> Run identity comparison</>}</button></div>
      {!registry?.speaker_identity?.installed && <p className="lab-muted">Optional setup: see <code>service/requirements-speaker-id.txt</code>. Verify matching PyTorch and torchaudio versions first; a separate test environment is safest.</p>}
      {registry?.transcription && <p className="lab-muted">Local draft transcription: <code>service/requirements-transcription.txt</code>. The first run downloads the selected Faster-Whisper model into ArkByte's private cache. Check transcripts and press Save transcript before exporting training data.</p>}
      {identityResult && <div className="ecapa-result"><div className="ecapa-score"><strong>{identityResult.centroid_cosine_similarity.toFixed(4)}</strong><span>cosine similarity</span></div><div><strong>{identityResult.reference_count} reference recordings · {identityResult.device}</strong><p>{identityResult.score_interpretation}</p><small>Model: {identityResult.model}</small></div></div>}
    </section>

    <section className="benchmark-method panel"><div className="section-head"><div><h3>What is still needed for true identity evaluation?</h3><p>These are explicitly not marked complete in this build.</p></div><Info size={18} /></div><div className="method-grid"><div><CheckCircle2 size={17} /><strong>Implemented now</strong><p>Multi-recording enrolment, acoustic recording diagnostics, reference-anchor selection, transcript storage and repeatable acoustic proxy comparisons.</p></div><div><Activity size={17} /><strong>Next model integration</strong><p>ECAPA-TDNN is available as an optional model adapter when SpeechBrain and weights are installed. Phoneme-level alignment, held-out pronunciation tests and blinded human evaluation remain necessary.</p></div><div><Cpu size={17} /><strong>Experimental TTS engines</strong><p>VoxCPM 2 is an optional generation adapter. Qwen3-TTS single-speaker training-data export is implemented; fine-tuning and inference remain in the official separate environment.</p></div></div></section>
  </div>;
}
