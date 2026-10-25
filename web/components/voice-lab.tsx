"use client";

import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { Activity, AudioLines, CheckCircle2, ChevronDown, Download, FileAudio, Loader2, LockKeyhole, Mic2, Plus, Save, ShieldCheck, Star, Trash2, Upload, Waves } from "lucide-react";
import { api } from "@/lib/api";
import type { VoiceProfile } from "@/lib/types";

type Notify = (title: string, message: string, kind?: "success" | "error" | "info" | "warning") => void;
type Sample = {
  id: string; source_name: string; transcript: string; transcript_reviewed: boolean; is_anchor: boolean; created_at: string;
  duration_seconds: number; quality_score: number; quality_grade: string; rms_dbfs: number;
  clipping_ratio: number; silence_ratio: number; pitch_median_hz: number | null;
  spectral_centroid_hz: number | null; warnings: string[];
};
type Pronunciation = { id: string; term: string; say_as: string; notes: string };
type ProfileDetail = {
  profile: { id: string; name: string; language: string };
  samples: Sample[];
  analysis: {
    sample_count: number; target_sample_count: number; enrollment_completion: number;
    total_recording_seconds: number; median_quality_score: number; median_pitch_hz: number | null;
    median_rms_dbfs: number | null; median_spectral_centroid_hz: number | null;
    accent_notes: string; pronunciation_notes: string; accent_classification: string;
    identity_embedding: { status: string; note: string };
    pipeline_stages: Array<{ id: string; name: string; status: string; detail: string }>;
  } | null;
  pronunciations: Pronunciation[];
};

const LANGUAGES = ["English", "Hindi", "Portuguese", "Spanish", "French", "German", "Italian", "Japanese", "Korean", "Chinese", "Arabic", "Russian", "Dutch", "Polish", "Turkish", "Danish", "Greek", "Finnish", "Hebrew", "Malay", "Norwegian", "Swahili", "Swedish"];
const ACCEPT = ".wav,.mp3,.m4a,.flac,.aac,.ogg,.mp4,.mov,.mkv,.avi,.webm";

function fmtDuration(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return mins ? `${mins}m ${secs}s` : `${secs}s`;
}

function RecordingPicker({ files, setFiles, transcripts, setTranscripts, title, max = 10 }: {
  files: File[]; setFiles: (files: File[]) => void; transcripts: string[];
  setTranscripts: (items: string[]) => void; title: string; max?: number;
}) {
  const change = (event: ChangeEvent<HTMLInputElement>) => {
    const next = Array.from(event.target.files || []).slice(0, max);
    setFiles(next);
    setTranscripts(next.map((_, index) => transcripts[index] || ""));
    event.target.value = "";
  };
  return <div className="lab-file-block">
    <div className="lab-file-header"><div><strong>{title}</strong><span>Choose up to {max} audio or video recordings</span></div><label className="button button-quiet button-small"><Upload size={14} /> Browse files<input type="file" accept={ACCEPT} multiple hidden onChange={change} /></label></div>
    {files.length === 0 ? <div className="lab-drop-hint"><FileAudio size={20} /><span>Select several recordings from the same authorised speaker. Aim for 10–20 minutes total.</span></div> : <div className="lab-file-list">{files.map((file, index) => <div className="lab-file-row" key={`${file.name}-${file.size}-${index}`}><div className="lab-file-main"><FileAudio size={16} /><div><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(1)} MB</span></div></div><button className="icon-button" type="button" aria-label={`Remove ${file.name}`} onClick={() => { setFiles(files.filter((_, i) => i !== index)); setTranscripts(transcripts.filter((_, i) => i !== index)); }}><Trash2 size={14} /></button><input className="lab-transcript-input" value={transcripts[index] || ""} onChange={event => setTranscripts(transcripts.map((value, i) => i === index ? event.target.value : value))} placeholder="Optional exact transcript for this recording" /></div>)}</div>}
  </div>;
}

export default function VoiceLab({ profiles, onRefresh, notify }: { profiles: VoiceProfile[]; onRefresh: () => Promise<void>; notify: Notify }) {
  const [name, setName] = useState("My Voice");
  const [language, setLanguage] = useState("English");
  const [accentNotes, setAccentNotes] = useState("");
  const [pronunciationNotes, setPronunciationNotes] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [transcripts, setTranscripts] = useState<string[]>([]);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [addFiles, setAddFiles] = useState<File[]>([]);
  const [addTranscripts, setAddTranscripts] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [term, setTerm] = useState("");
  const [sayAs, setSayAs] = useState("");
  const [notes, setNotes] = useState("");
  const [savingPronunciation, setSavingPronunciation] = useState(false);
  const [transcriptDrafts, setTranscriptDrafts] = useState<Record<string, string>>({});
  const [savingTranscript, setSavingTranscript] = useState<string | null>(null);
  const [transcribingSample, setTranscribingSample] = useState<string | null>(null);
  const [downloadingQwen, setDownloadingQwen] = useState(false);

  const selectedProfile = profiles.find(profile => profile.id === selectedId) || profiles[0];
  const sampleCount = detail?.samples.length || selectedProfile?.sample_count || 0;
  const remainingSlots = Math.max(0, 10 - sampleCount);

  useEffect(() => {
    if (!selectedId && profiles.length) setSelectedId(profiles[0].id);
    if (selectedId && !profiles.some(profile => profile.id === selectedId)) setSelectedId(profiles[0]?.id || "");
  }, [profiles, selectedId]);

  useEffect(() => {
    let active = true;
    if (!selectedProfile) { setDetail(null); return; }
    setDetailLoading(true);
    api<ProfileDetail>(`/api/v1/profiles/${selectedProfile.id}/detail`)
      .then(data => { if (active) setDetail(data); })
      .catch(error => { if (active) notify("Could not load voice analysis", error instanceof Error ? error.message : "The profile could not be loaded.", "error"); })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selectedProfile?.id, notify]);

  useEffect(() => {
    if (detail) setTranscriptDrafts(Object.fromEntries(detail.samples.map(sample => [sample.id, sample.transcript || ""])));
  }, [detail]);

  const createProfile = async (event: FormEvent) => {
    event.preventDefault();
    if (!consent || !files.length) return;
    setBusy(true);
    try {
      const data = new FormData();
      data.set("name", name.trim()); data.set("language", language);
      data.set("accent_notes", accentNotes); data.set("pronunciation_notes", pronunciationNotes);
      data.set("transcripts_json", JSON.stringify(transcripts)); data.set("consent_ack", "true");
      files.forEach(file => data.append("files", file, file.name));
      const result = await api<{ profile: VoiceProfile; analysis: ProfileDetail["analysis"] }>("/api/v1/enrollments", { method: "POST", body: data });
      setSelectedId(result.profile.id); setFiles([]); setTranscripts([]); setConsent(false);
      await onRefresh();
      notify("Voice enrolment created", `${result.profile.name} now has ${result.profile.sample_count || files.length} analysed recording(s).`);
    } catch (error) {
      notify("Enrolment failed", error instanceof Error ? error.message : "Could not process the selected recordings.", "error");
    } finally { setBusy(false); }
  };

  const addRecordings = async () => {
    if (!selectedProfile || !addFiles.length) return;
    setAdding(true);
    try {
      const data = new FormData();
      data.set("transcripts_json", JSON.stringify(addTranscripts));
      addFiles.forEach(file => data.append("files", file, file.name));
      await api(`/api/v1/profiles/${selectedProfile.id}/samples`, { method: "POST", body: data });
      setAddFiles([]); setAddTranscripts([]); await loadDetail(selectedProfile.id); await onRefresh();
      notify("Recordings added", "The voice profile analysis has been recalculated.");
    } catch (error) { notify("Could not add recordings", error instanceof Error ? error.message : "The upload failed.", "error"); }
    finally { setAdding(false); }
  };

  const loadDetail = async (profileId: string) => {
    setDetailLoading(true);
    try { setDetail(await api<ProfileDetail>(`/api/v1/profiles/${profileId}/detail`)); }
    catch (error) { notify("Could not refresh profile", error instanceof Error ? error.message : "Try again.", "error"); }
    finally { setDetailLoading(false); }
  };

  const setAnchor = async (sampleId: string) => {
    if (!selectedProfile) return;
    try {
      await api(`/api/v1/profiles/${selectedProfile.id}/anchor/${sampleId}`, { method: "POST" });
      await loadDetail(selectedProfile.id); await onRefresh();
      notify("Reference anchor updated", "New generations will use this recording as the Chatterbox reference.");
    } catch (error) { notify("Could not change reference", error instanceof Error ? error.message : "Try again.", "error"); }
  };

  const transcribeSample = async (sampleId: string) => {
    if (!selectedProfile) return;
    setTranscribingSample(sampleId);
    try {
      const result = await api<{ transcript: string; detected_language?: string; language_probability?: number; model: string; review_required: boolean }>(
        `/api/v1/profiles/${selectedProfile.id}/samples/${sampleId}/transcribe`, { method: "POST" },
      );
      setTranscriptDrafts(current => ({ ...current, [sampleId]: result.transcript }));
      await loadDetail(selectedProfile.id);
      notify("Draft transcript created", `Detected language: ${result.detected_language || "unknown"}. Review every word, then click Save transcript to approve it for training export.`, "warning");
    } catch (error) {
      notify("Transcription unavailable", error instanceof Error ? error.message : "Install the optional local Faster-Whisper package and retry.", "error");
    } finally { setTranscribingSample(null); }
  };

  const saveTranscript = async (sampleId: string) => {
    if (!selectedProfile) return;
    const transcript = (transcriptDrafts[sampleId] || "").trim();
    if (!transcript) { notify("Transcript required", "Enter the complete transcript spoken in this recording.", "warning"); return; }
    setSavingTranscript(sampleId);
    try {
      await api(`/api/v1/profiles/${selectedProfile.id}/samples/${sampleId}/transcript`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ transcript }),
      });
      await loadDetail(selectedProfile.id);
      notify("Transcript saved", "This exact transcript can now be used in the Qwen training-data export.");
    } catch (error) { notify("Could not save transcript", error instanceof Error ? error.message : "Try again.", "error"); }
    finally { setSavingTranscript(null); }
  };

  const exportQwenDataset = async () => {
    if (!selectedProfile) return;
    setDownloadingQwen(true);
    try {
      const response = await fetch(`/api/v1/profiles/${selectedProfile.id}/training-export/qwen3`, { cache: "no-store", credentials: "same-origin" });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.error?.message || `Training export failed (HTTP ${response.status}).`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `ArkByte_Qwen3_Training_${selectedProfile.name.replace(/[^a-z0-9_-]/gi, "_")}.zip`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
      notify("Qwen training data exported", "Review train_raw.jsonl and all audio/transcript pairs before using the official Qwen fine-tuning workflow.");
    } catch (error) { notify("Training export unavailable", error instanceof Error ? error.message : "Try again.", "error"); }
    finally { setDownloadingQwen(false); }
  };

  const savePronunciation = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedProfile) return;
    setSavingPronunciation(true);
    try {
      await api(`/api/v1/profiles/${selectedProfile.id}/pronunciations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ term, say_as: sayAs, notes }) });
      setTerm(""); setSayAs(""); setNotes(""); await loadDetail(selectedProfile.id);
      notify("Pronunciation saved", "This spoken form will be applied to matching terms when you generate with this voice.");
    } catch (error) { notify("Could not save pronunciation", error instanceof Error ? error.message : "Try again.", "error"); }
    finally { setSavingPronunciation(false); }
  };

  const deletePronunciation = async (id: string) => {
    if (!selectedProfile) return;
    try { await api(`/api/v1/profiles/${selectedProfile.id}/pronunciations/${id}`, { method: "DELETE" }); await loadDetail(selectedProfile.id); }
    catch (error) { notify("Could not delete pronunciation", error instanceof Error ? error.message : "Try again.", "error"); }
  };

  const totalMinutes = useMemo(() => detail?.analysis ? Math.round(detail.analysis.total_recording_seconds / 60 * 10) / 10 : 0, [detail]);

  return <div className="voice-lab-page">
    <div className="page-heading"><div><div className="eyebrow">SPEAKER ENROLMENT & ANALYSIS</div><h1>Voice Lab</h1><p>Build a reusable voice identity dataset from up to ten recordings. Keep original audio untouched and inspect every sample.</p></div><div className="lab-private-pill"><LockKeyhole size={14} /> LOCAL DATASET</div></div>
    <div className="lab-intro-grid">
      <div className="lab-intro-card"><div className="lab-icon"><Mic2 size={20} /></div><div><strong>Record natural speech</strong><p>Mix conversational speech, neutral reading, questions, names and different speaking rates. Use the same speaker throughout.</p></div></div>
      <div className="lab-intro-card"><div className="lab-icon blue"><Activity size={20} /></div><div><strong>Analyse, don't over-process</strong><p>ArkByte stores the original recordings and creates separate 24 kHz model references without denoising or loudness shaping.</p></div></div>
      <div className="lab-intro-card"><div className="lab-icon violet"><ShieldCheck size={20} /></div><div><strong>Consent-first cloning</strong><p>Only enrol your own voice or a speaker who has explicitly authorised cloning and use.</p></div></div>
    </div>

    <div className="lab-layout">
      <section className="panel lab-enroll-panel">
        <div className="section-head"><div><h3>New speaker enrolment</h3><p>Upload between 1 and 10 recordings now. Add more later until the profile reaches ten.</p></div><span className="soft-label">TARGET: 10 SAMPLES</span></div>
        <form onSubmit={createProfile}>
          <div className="form-grid"><div className="form-field"><label>PROFILE NAME</label><input value={name} onChange={event => setName(event.target.value)} required maxLength={80} placeholder="My natural speaking voice" /></div><div className="form-field"><label>LANGUAGE</label><div className="select-wrap"><select value={language} onChange={event => setLanguage(event.target.value)}>{LANGUAGES.map(item => <option key={item}>{item}</option>)}</select><ChevronDown size={15} /></div></div></div>
          <div className="form-field lab-wide-field"><label>SPEAKER-CONFIRMED ACCENT / REGION (OPTIONAL)</label><input value={accentNotes} onChange={event => setAccentNotes(event.target.value)} maxLength={2000} placeholder="e.g. English with a Goan / Indian-Portuguese-influenced accent" /><small>ArkByte stores this as your note. It does not automatically identify or certify an accent.</small></div>
          <div className="form-field lab-wide-field"><label>PRONUNCIATION NOTES (OPTIONAL)</label><textarea value={pronunciationNotes} onChange={event => setPronunciationNotes(event.target.value)} rows={2} maxLength={2000} placeholder="Words, names, regional pronunciations or speech habits to test…" /></div>
          <RecordingPicker files={files} setFiles={setFiles} transcripts={transcripts} setTranscripts={setTranscripts} title="Recording set" />
          <label className="consent-row lab-consent"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /><span>I confirm I own these recordings or have explicit permission from the speaker to create and use this voice profile.</span></label>
          <div className="lab-form-footer"><span><LockKeyhole size={13} /> Max 250 MB/file · 500 MB/batch · 10 recordings/profile</span><button className="button button-primary" type="submit" disabled={busy || !files.length || !consent || !name.trim()}>{busy ? <><Loader2 size={15} className="spin" /> Analysing recordings…</> : <><Plus size={15} /> Create voice profile</>}</button></div>
        </form>
      </section>

      <section className="panel lab-profile-panel">
        <div className="section-head"><div><h3>Enrolled voice profiles</h3><p>Select a profile to inspect its dataset and reference anchor.</p></div><span className="count-chip">{profiles.length} profiles</span></div>
        {profiles.length === 0 ? <div className="lab-empty"><AudioLines size={26} /><strong>No enrolled voice yet</strong><p>Create a profile with your own recordings to begin manual testing.</p></div> : <>
          <div className="form-field"><label>SELECT PROFILE</label><div className="select-wrap"><select value={selectedProfile?.id || ""} onChange={event => setSelectedId(event.target.value)}>{profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name} · {profile.sample_count || 0}/10</option>)}</select><ChevronDown size={15} /></div></div>
          {detailLoading ? <div className="lab-loading"><Loader2 className="spin" size={18} /> Analysing profile…</div> : detail?.analysis ? <>
            <div className="lab-completion"><div className="lab-completion-top"><strong>{detail.profile.name}</strong><span>{detail.analysis.enrollment_completion}% enrolled</span></div><div className="lab-progress"><i style={{ width: `${detail.analysis.enrollment_completion}%` }} /></div><div className="lab-mini-stats"><div><strong>{detail.analysis.sample_count}/10</strong><span>Recordings</span></div><div><strong>{totalMinutes} min</strong><span>Source audio</span></div><div><strong>{detail.analysis.median_quality_score}/100</strong><span>Median quality</span></div></div></div>
            <div className="lab-metrics-grid"><div><span>Median F0</span><strong>{detail.analysis.median_pitch_hz ? `${detail.analysis.median_pitch_hz} Hz` : "Unavailable"}</strong></div><div><span>RMS level</span><strong>{detail.analysis.median_rms_dbfs !== null ? `${detail.analysis.median_rms_dbfs} dBFS` : "Unavailable"}</strong></div><div><span>Spectral centroid</span><strong>{detail.analysis.median_spectral_centroid_hz ? `${detail.analysis.median_spectral_centroid_hz} Hz` : "Unavailable"}</strong></div></div>
            <div className="lab-note"><strong>Accent notes</strong><p>{detail.analysis.accent_notes || "No speaker-confirmed accent notes provided."}</p><small>{detail.analysis.accent_classification}</small></div>
            <div className="lab-pipeline panel"><div className="section-head"><div><h3>Voice intelligence pipeline</h3><p>Transparent status of each processing stage. Manual/model-dependent work is not marked complete.</p></div><Waves size={17} /></div><div className="lab-pipeline-grid">{detail.analysis.pipeline_stages.map(stage => <div className="lab-pipeline-stage" key={stage.id}><div><strong>{stage.name}</strong><span className={`pipeline-status ${stage.status}`}>{stage.status.replaceAll("_", " ")}</span></div><p>{stage.detail}</p></div>)}</div></div>
            <div className="lab-samples-heading"><strong>Recording analysis</strong><span>{remainingSlots} slots remaining</span></div>
            <div className="lab-sample-list">{detail.samples.map(sample => <article className="lab-sample-card" key={sample.id}>
              <div className="lab-sample-top"><div className="lab-sample-file"><FileAudio size={15} /><div><strong>{sample.source_name}</strong><span>{fmtDuration(sample.duration_seconds)} · {sample.quality_grade} · {sample.quality_score}/100</span></div></div>{sample.is_anchor ? <span className="anchor-chip"><Star size={11} /> Active anchor</span> : <button className="button button-quiet button-small" type="button" onClick={() => void setAnchor(sample.id)}>Use as anchor</button>}</div>
              <audio controls preload="none" src={`/api/v1/profile-samples/${sample.id}/audio`} />
              <div className="lab-sample-metrics"><span>RMS {sample.rms_dbfs} dBFS</span><span>Silence {(sample.silence_ratio * 100).toFixed(0)}%</span><span>Clipping {(sample.clipping_ratio * 100).toFixed(2)}%</span><span>Pitch {sample.pitch_median_hz ? `${sample.pitch_median_hz} Hz` : "—"}</span></div>
              {sample.warnings.length > 0 && <p className="lab-warning-text">{sample.warnings.join(" ")}</p>}
              <div className="lab-sample-transcript-edit"><label htmlFor={`transcript-${sample.id}`}>EXACT TRANSCRIPT · {sample.transcript_reviewed ? "REVIEWED" : "REVIEW REQUIRED"}</label><textarea id={`transcript-${sample.id}`} rows={3} maxLength={20000} value={transcriptDrafts[sample.id] ?? sample.transcript ?? ""} onChange={event => setTranscriptDrafts(current => ({ ...current, [sample.id]: event.target.value }))} placeholder="Enter every word spoken in this full recording. Include disfluencies and names." /><div className="lab-transcript-actions"><button className="button button-quiet button-small" type="button" onClick={() => void transcribeSample(sample.id)} disabled={transcribingSample === sample.id}>{transcribingSample === sample.id ? <><Loader2 size={13} className="spin" /> Transcribing…</> : <><AudioLines size={13} /> Auto-transcribe</>}</button><button className="button button-quiet button-small" type="button" onClick={() => void saveTranscript(sample.id)} disabled={savingTranscript === sample.id || !(transcriptDrafts[sample.id] || "").trim()}>{savingTranscript === sample.id ? <Loader2 size={13} className="spin" /> : <Save size={13} />} Save transcript</button></div></div>
            </article>)}</div>
            {remainingSlots > 0 && <div className="lab-add-samples"><RecordingPicker files={addFiles} setFiles={setAddFiles} transcripts={addTranscripts} setTranscripts={setAddTranscripts} title="Add recordings to this profile" max={remainingSlots} /><button className="button button-primary" type="button" onClick={() => void addRecordings()} disabled={adding || !addFiles.length}>{adding ? <Loader2 size={14} className="spin" /> : <Plus size={14} />} Add to profile</button></div>}
            <div className="lab-qwen-export panel">
              <div><strong>Qwen3-TTS speaker-adaptation dataset</strong><p>Export the full original utterances, exact transcripts and one shared reference audio as a training-ready ZIP. The official model fine-tuning is run separately.</p></div>
              <button className="button button-primary" type="button" onClick={() => void exportQwenDataset()} disabled={downloadingQwen || !detail.samples.length}>{downloadingQwen ? <><Loader2 size={14} className="spin" /> Preparing dataset…</> : <><Download size={14} /> Export Qwen training ZIP</>}</button>
            </div>
            <div className="lab-pronunciation">
              <div className="section-head"><div><h3>Personal pronunciation dictionary</h3><p>Text substitutions are applied before local generation.</p></div></div>
              <form className="lab-pronunciation-form" onSubmit={savePronunciation}><div className="form-field"><label>WRITTEN TERM</label><input value={term} onChange={event => setTerm(event.target.value)} placeholder="e.g. Costas" maxLength={100} required /></div><div className="form-field"><label>SAY AS</label><input value={sayAs} onChange={event => setSayAs(event.target.value)} placeholder="Enter the pronunciation text" maxLength={200} required /></div><div className="form-field lab-pronunciation-note"><label>NOTES</label><input value={notes} onChange={event => setNotes(event.target.value)} placeholder="Optional pronunciation reminder" maxLength={500} /></div><button className="button button-quiet" type="submit" disabled={savingPronunciation}>{savingPronunciation ? <Loader2 size={14} className="spin" /> : <Plus size={14} />} Save pronunciation</button></form>
              {detail.pronunciations.length > 0 ? <div className="lab-pronunciation-list">{detail.pronunciations.map(item => <div key={item.id}><span><strong>{item.term}</strong><em>→</em>{item.say_as}</span><button className="icon-button" type="button" onClick={() => void deletePronunciation(item.id)} aria-label={`Delete ${item.term}`}><Trash2 size={14} /></button></div>)}</div> : <p className="lab-muted">No personal pronunciation overrides yet.</p>}
            </div>
            <div className="lab-identity-limit"><ShieldCheck size={16} /><p><strong>Speaker identity evaluation is optional.</strong> This profile contains acoustic descriptors. The ECAPA-TDNN comparison appears in Benchmark Studio only when SpeechBrain is installed and its pretrained weights are available. Accent verification still requires phonetic tests and human review.</p></div>
          </> : <div className="lab-empty"><Activity size={25} /><strong>Select an enrolled profile</strong><p>Recording diagnostics and pronunciation controls will appear here.</p></div>}
        </>}
      </section>
    </div>
  </div>;
}
