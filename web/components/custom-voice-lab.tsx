"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { VoiceProfile } from "@/lib/types";
import { AudioLines, CheckCircle2, Download, ExternalLink, FileAudio, Info, Loader2, ShieldCheck, Sparkles, UploadCloud } from "lucide-react";

type Sample = { id: string; source_name: string; transcript: string; transcript_reviewed: boolean; duration_seconds?: number; is_anchor: boolean };
type Detail = { profile: { id: string; name: string; language: string }; samples: Sample[]; analysis?: { pipeline_stages?: Array<{ id: string; status: string }> } };
type Notify = (title: string, message: string, kind?: "success" | "error" | "info" | "warning") => void;

export default function CustomVoiceLab({ profiles, notify }: { profiles: VoiceProfile[]; notify: Notify }) {
  const [profileId, setProfileId] = useState(profiles[0]?.id || "");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const selected = profiles.find(item => item.id === profileId);
  const reviewed = useMemo(() => detail?.samples.filter(sample => sample.transcript_reviewed && sample.transcript.trim()).length || 0, [detail]);
  const total = detail?.samples.length || 0;
  const ready = total > 0 && reviewed === total;

  useEffect(() => { if (!profileId && profiles[0]) setProfileId(profiles[0].id); }, [profiles, profileId]);
  useEffect(() => {
    let active = true;
    setDetail(null); setError("");
    if (!profileId) return;
    setLoading(true);
    api<Detail>(`/api/v1/profiles/${profileId}/detail`)
      .then(value => { if (active) setDetail(value); })
      .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : "Could not load voice dataset."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [profileId]);

  const exportDataset = async () => {
    if (!profileId || !ready) return;
    setExporting(true);
    try {
      const response = await fetch(`/api/v1/profiles/${profileId}/training-export/qwen3`, { method: "GET", cache: "no-store", credentials: "same-origin" });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.error?.message || payload?.detail || `Export failed (HTTP ${response.status}).`);
      }
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || `ArkByte_Qwen3_Training_${selected?.name || "Voice"}.zip`;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
      notify("Training dataset exported", "Your transcript-reviewed recordings are packaged for the official Qwen3-TTS fine-tuning workflow.", "success");
    } catch (reason) { notify("Dataset export failed", reason instanceof Error ? reason.message : "Unexpected export error.", "error"); }
    finally { setExporting(false); }
  };

  return <div className="benchmark-page">
    <div className="page-heading"><div><div className="eyebrow">CUSTOM SPEAKER ADAPTATION</div><h1>Custom Voice Lab</h1><p>Prepare a speaker-specific dataset, validate transcripts and export it for supported fine-tuning workflows.</p></div><div className="lab-private-pill"><ShieldCheck size={14} /> LOCAL DATASET</div></div>
    <section className="benchmark-hero panel"><div className="benchmark-hero-icon"><AudioLines size={25} /></div><div><h3>Build a reusable custom voice dataset</h3><p>ArkByte prepares clean 24 kHz mono WAV utterances and transcript metadata for Qwen3-TTS single-speaker fine-tuning. This release exports the dataset; it does not run model training or claim a trained model is ready.</p></div><div className="benchmark-hero-badge">TRAINING PREP</div></section>
    <section className="panel" style={{ padding: 24, display: "grid", gap: 18 }}>
      <div className="section-head"><div><h3>1. Select a consenting speaker profile</h3><p>Use recordings of one speaker only, with permission to create and adapt their voice.</p></div><FileAudio size={19} /></div>
      {profiles.length ? <div className="form-field"><label htmlFor="custom-voice-profile">VOICE PROFILE</label><div className="select-wrap"><select id="custom-voice-profile" value={profileId} onChange={event => setProfileId(event.target.value)}>{profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name} · {profile.language} · {profile.sample_count || 0} clips</option>)}</select></div></div> : <div className="lab-empty"><UploadCloud size={24} /><strong>No voice profiles yet</strong><p>Create a profile in Voice Library and add multiple recordings first.</p></div>}
      {loading && <div className="lab-loading"><Loader2 size={17} className="spin" /> Checking dataset…</div>}
      {error && <p className="lab-warning-text">{error}</p>}
      {detail && <>
        <div className="custom-voice-readiness"><div><strong>{total}</strong><span>Recordings enrolled</span></div><div><strong>{reviewed}/{total}</strong><span>Transcripts reviewed</span></div><div><strong>{ready ? "Ready" : "Incomplete"}</strong><span>Export readiness</span></div></div>
        <div className="section-head"><div><h3>2. Review every transcript</h3><p>Auto-generated transcripts are drafts. Listen to each recording and save its exact transcript in Voice Lab before export.</p></div><span className="soft-label">{reviewed} / {total} VERIFIED</span></div>
        <div className="model-list">{detail.samples.map((sample, index) => <div className="model-row custom-voice-sample" key={sample.id}><div><strong>{index + 1}. {sample.source_name}</strong><span>{sample.duration_seconds ? `${sample.duration_seconds.toFixed(1)} sec · ` : ""}{sample.is_anchor ? "Reference anchor · " : ""}{sample.transcript_reviewed ? "Transcript reviewed" : "Transcript needs review"}</span>{sample.transcript && <small>{sample.transcript.slice(0, 180)}{sample.transcript.length > 180 ? "…" : ""}</small>}</div><div className="model-row-status"><i className={sample.transcript_reviewed && sample.transcript.trim() ? "model-live" : "model-experimental"} />{sample.transcript_reviewed && sample.transcript.trim() ? "Verified" : "Review required"}</div></div>)}</div>
        <div className="benchmark-run-row"><span><Info size={14} /> {ready ? "All transcripts are marked reviewed. Export is enabled." : "Open Voice Lab → select the profile → review and save every transcript."}</span><button className="button button-primary" onClick={() => void exportDataset()} disabled={!ready || exporting}>{exporting ? <><Loader2 size={14} className="spin" /> Packaging…</> : <><Download size={14} /> Export training dataset</>}</button></div>
      </>}
    </section>
    <section className="panel benchmark-method"><div className="section-head"><div><h3>3. Fine-tune in the supported training environment</h3><p>Export creates a ZIP containing WAV files, JSONL metadata and a training guide.</p></div><Sparkles size={18} /></div><div className="method-grid"><div><CheckCircle2 size={17} /><strong>ArkByte handles</strong><p>Transcript-review gate, speaker dataset packaging, FFmpeg conversion to mono 24 kHz WAV, reference audio and manifest.</p></div><div><Info size={17} /><strong>External training step</strong><p>Run the official Qwen3-TTS Base fine-tuning scripts in a separate Python environment with compatible CUDA, tokenizer and model weights.</p></div><div><ShieldCheck size={17} /><strong>Validate before use</strong><p>Keep held-out recordings, compare unseen phrases and listen for identity drift, pronunciation errors and overfitting. No exact-match guarantee.</p></div></div><p className="lab-muted">Your RTX 3050 Laptop GPU has 6 GB VRAM. Full fine-tuning may exceed that capacity. Use a supported low-memory/parameter-efficient workflow only if the upstream project documents it; otherwise use a larger GPU or hosted training machine. Keep voice datasets private because they are biometric data.</p><a className="button button-quiet" href="https://github.com/QwenLM/Qwen3-TTS/tree/main/finetuning" target="_blank" rel="noreferrer">Official Qwen3-TTS fine-tuning instructions <ExternalLink size={14} /></a></section>
  </div>;
}
