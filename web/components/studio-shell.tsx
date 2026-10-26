"use client";

import {
  Activity, ArrowDownToLine, ArrowRight, AudioWaveform, BarChart3, Check,
  CheckCircle2, ChevronDown, ChevronRight, CircleAlert, Clock3, Cpu,
  Database, Download, FileAudio, FileText, Gauge, Headphones, Home,
  Info, Layers3, Loader2, LockKeyhole, Menu, Mic2, MoreHorizontal,
  Music2, Pause, Play, Plus, RefreshCw, Search, Settings2, ShieldCheck,
  FolderOpen, Save, FilePlus2,
  SlidersHorizontal, Sparkles, Trash2, Upload, WandSparkles, X, Zap
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, StudioApiError } from "@/lib/api";
import type { GenerationJob, Health, HistoryItem, StudioProject, StudioProjectSummary, VoiceProfile } from "@/lib/types";
import VoiceLab from "@/components/voice-lab";
import BenchmarkLab from "@/components/benchmark-lab";
import CustomVoiceLab from "@/components/custom-voice-lab";

type Page = "overview" | "projects" | "voices" | "lab" | "customvoice" | "benchmark" | "script" | "history" | "settings" | "about";
type ModelCapability = { id: string; name: string; package: string; role: string; status: string; integrated: boolean; hardware_note?: string; requires_transcript?: boolean; recommended_vram_gb?: number; first_use_download?: boolean };
type Toast = { id: number; title: string; message: string; kind: "success" | "error" | "info" | "warning" };

const LANGUAGES = [
  ["English", "en"], ["Hindi", "hi"], ["Portuguese", "pt"], ["Spanish", "es"],
  ["French", "fr"], ["German", "de"], ["Italian", "it"], ["Japanese", "ja"],
  ["Korean", "ko"], ["Chinese", "zh"], ["Arabic", "ar"], ["Russian", "ru"],
  ["Dutch", "nl"], ["Polish", "pl"], ["Turkish", "tr"], ["Danish", "da"],
  ["Greek", "el"], ["Finnish", "fi"], ["Hebrew", "he"], ["Malay", "ms"],
  ["Norwegian", "no"], ["Swahili", "sw"], ["Swedish", "sv"]
] as const;

const navItems: { id: Page; label: string; icon: typeof Home; section?: string }[] = [
  { id: "overview", label: "Overview", icon: Home, section: "Workspace" },
  { id: "projects", label: "Projects", icon: FolderOpen },
  { id: "voices", label: "Voice library", icon: Mic2 },
  { id: "lab", label: "Voice Lab", icon: Activity },
  { id: "customvoice", label: "Custom Voice Lab", icon: AudioWaveform },
  { id: "script", label: "Script studio", icon: WandSparkles },
  { id: "benchmark", label: "Benchmark Studio", icon: BarChart3, section: "Evaluation" },
  { id: "history", label: "Generation history", icon: Clock3, section: "Your work" },
  { id: "settings", label: "Settings & health", icon: Settings2 },
  { id: "about", label: "About ArkByte", icon: Info, section: "Studio" }
];

function formatDate(value?: string) {
  if (!value) return "Just now";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Recently" : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}
function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
function initials(name: string) {
  return name.split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase() || "").join("");
}

function toProjectSummary(project: StudioProject): StudioProjectSummary {
  const normalized = project.script.replace(/\s+/g, " ").trim();
  return {
    id: project.id,
    title: project.title,
    script_preview: normalized.slice(0, 240),
    character_count: project.script.length,
    profile_id: project.profile_id,
    language_id: project.language_id,
    created_at: project.created_at,
    updated_at: project.updated_at
  };
}

function Waveform({ bars = 32, active = false }: { bars?: number; active?: boolean }) {
  return <div className={`waveform ${active ? "waveform-active" : ""}`} aria-hidden="true">
    {Array.from({ length: bars }, (_, i) => <i key={i} style={{ height: `${16 + ((i * 19 + i * i * 7) % 72)}%`, animationDelay: `${(i % 11) * -0.11}s` }} />)}
  </div>;
}

function StatusPill({ ok, children, warning = false }: { ok: boolean; children: React.ReactNode; warning?: boolean }) {
  return <span className={`status-pill ${warning ? "warning" : ok ? "good" : "bad"}`}><i />{children}</span>;
}

function ToastStack({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  return <div className="toast-stack" aria-live="polite">{toasts.map(toast => <div className={`toast toast-${toast.kind}`} key={toast.id}>
    {toast.kind === "success" ? <CheckCircle2 size={18} /> : toast.kind === "error" ? <CircleAlert size={18} /> : <Info size={18} />}
    <div><strong>{toast.title}</strong><p>{toast.message}</p></div>
    <button className="icon-button" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification"><X size={15} /></button>
  </div>)}</div>;
}

export default function StudioShell() {
  const [page, setPage] = useState<Page>("overview");
  const [health, setHealth] = useState<Health | null>(null);
  const [modelCapabilities, setModelCapabilities] = useState<ModelCapability[]>([]);
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [projects, setProjects] = useState<StudioProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [mobileNav, setMobileNav] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [activeJob, setActiveJob] = useState<GenerationJob | null>(null);
  const [playing, setPlaying] = useState<HistoryItem | null>(null);
  const [script, setScript] = useState("");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [language, setLanguage] = useState("en");
  const [outputName, setOutputName] = useState("youtube-narration");
  const [projectTitle, setProjectTitle] = useState("My narration project");
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [projectSaved, setProjectSaved] = useState(false);
  const [savingProject, setSavingProject] = useState(false);
  const [openingProjectId, setOpeningProjectId] = useState<string | null>(null);
  const [exaggeration, setExaggeration] = useState(0.5);
  const [pace, setPace] = useState(0.5);
  const [temperature, setTemperature] = useState(0.8);
  const [modelId, setModelId] = useState<"chatterbox" | "voxcpm05" | "voxcpm2">("chatterbox");
  const [generating, setGenerating] = useState(false);
  const [generationRightsAck, setGenerationRightsAck] = useState(false);
  const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [profileToDelete, setProfileToDelete] = useState<VoiceProfile | null>(null);
  const pollAbort = useRef<AbortController | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const notify = useCallback((title: string, message: string, kind: Toast["kind"] = "success") => {
    const id = Date.now() + Math.random();
    setToasts(current => [...current, { id, title, message, kind }].slice(-4));
    window.setTimeout(() => setToasts(current => current.filter(item => item.id !== id)), 6500);
  }, []);

  const refresh = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true); else setLoading(true);
    try {
      const [healthData, profileData, historyData, projectData, modelData] = await Promise.all([
        api<Health>("/api/v1/health"),
        api<{ profiles: VoiceProfile[] }>("/api/v1/profiles"),
        api<{ history: HistoryItem[] }>("/api/v1/history"),
        api<{ projects: StudioProjectSummary[] }>("/api/v1/projects"),
        api<{ models: ModelCapability[] }>("/api/v1/models")
      ]);
      setHealth(healthData);
      setProfiles(profileData.profiles || []);
      setHistory(historyData.history || []);
      setProjects(projectData.projects || []);
      setModelCapabilities(modelData.models || []);
      setApiError(null);
      setSelectedProfile(current => profileData.profiles?.some(item => item.id === current) ? current : (profileData.profiles?.[0]?.id || ""));
    } catch (error) {
      const message = error instanceof Error ? error.message : "The local service could not be reached.";
      setApiError(message);
      if (!silent) notify("Local service unavailable", message, "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [notify]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(true); }, 15000);
    return () => { window.clearInterval(timer); pollAbort.current?.abort(); };
  }, [refresh]);

  const dismissToast = (id: number) => setToasts(items => items.filter(item => item.id !== id));
  const goto = (next: Page) => { setPage(next); setMobileNav(false); setSearch(""); };

  const pollGeneration = async (jobId: string) => {
    pollAbort.current?.abort();
    const controller = new AbortController();
    pollAbort.current = controller;
    const started = Date.now();
    while (!controller.signal.aborted && Date.now() - started < 45 * 60 * 1000) {
      try {
        const data = await api<{ job: GenerationJob }>(`/api/v1/generations/${jobId}`, { signal: controller.signal });
        setActiveJob(data.job);
        if (data.job.status === "complete") {
          setGenerating(false);
          notify("Narration ready", "Your audio has been saved locally.", "success");
          await refresh(true);
          return;
        }
        if (data.job.status === "failed") {
          setGenerating(false);
          notify(data.job.error?.code || "Generation failed", data.job.error?.message || "Check the local service log.", "error");
          return;
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        setGenerating(false);
        notify("Could not check generation", error instanceof Error ? error.message : "The local service stopped responding.", "error");
        return;
      }
      await new Promise(resolve => window.setTimeout(resolve, 1400));
    }
    setGenerating(false);
    notify("Generation status unknown", "The browser stopped waiting. Check Generation History before starting another job.", "warning");
  };

  const submitGeneration = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedProfile) { notify("Select a voice", "Create or choose a voice profile before generating.", "error"); return; }
    if (!generationRightsAck) { notify("Usage confirmation required", "Confirm that you have permission to use this voice and agree to the responsible-use policy.", "error"); return; }
    if (script.trim().length < 3) { notify("Add a script", "Write or paste narration text before generating.", "error"); return; }
    if (script.length > 50000) { notify("Script is too long", "The current limit is 50,000 characters.", "error"); return; }
    const selectedCapability = modelCapabilities.find(item => item.id === modelId);
    const selectedModelReady = modelId === "chatterbox"
      ? Boolean(health?.engine.installed)
      : Boolean(selectedCapability?.integrated && selectedCapability.status === "installed");
    if (!selectedModelReady) { notify("Selected model is not installed", modelId === "chatterbox" ? "Install the local Chatterbox engine, then refresh system health." : "Run INSTALL VOXCPM MODELS.ps1, then restart ArkByte and refresh system health.", "error"); goto("settings"); return; }
    setGenerating(true);
    setActiveJob({ id: "pending", status: "queued", progress: 0, message: "Submitting your narration…" });
    try {
      const result = await api<{ job: GenerationJob }>("/api/v1/generations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: selectedProfile, script, language_id: language, output_name: outputName, exaggeration, cfg_weight: pace, temperature, model_id: modelId, rights_ack: generationRightsAck })
      });
      setActiveJob(result.job);
      setGenerationRightsAck(false);
      void pollGeneration(result.job.id);
    } catch (error) {
      setGenerating(false);
      setGenerationRightsAck(false);
      notify("Generation could not start", error instanceof Error ? error.message : "Unexpected local error.", "error");
    }
  };

  const deleteHistoryItem = async (item: HistoryItem) => {
    if (!window.confirm(`Permanently delete this narration and its generated audio file?\n\n“${item.script_preview || "Narration"}”\n\nVoice profiles, original reference recordings and saved projects will remain.`)) return;
    setDeletingHistoryId(item.id);
    try {
      await api<{ ok: boolean; deleted: number }>(`/api/v1/history/${item.id}`, { method: "DELETE" });
      setHistory(current => current.filter(entry => entry.id !== item.id));
      setPlaying(current => current?.id === item.id ? null : current);
      notify("History item deleted", "The history entry and its generated audio were deleted. Voice profiles and source recordings were kept.");
    } catch (error) {
      notify("Could not delete history item", error instanceof Error ? error.message : "The local service could not delete this item.", "error");
    } finally {
      setDeletingHistoryId(null);
    }
  };

  const permanentlyDeleteVoiceProfile = async (profile: VoiceProfile) => {
    const result = await api<{ ok: boolean; deleted: boolean; file_cleanup_complete: boolean }>(`/api/v1/profiles/${profile.id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation_phrase: "DELETE VOICE" })
    });
    setProfiles(current => current.filter(item => item.id !== profile.id));
    if (selectedProfile === profile.id) setSelectedProfile("");
    if (profileToDelete?.id === profile.id) setProfileToDelete(null);
    setHistory(current => current.map(item => item.profile_id === profile.id ? { ...item, profile_id: null } : item));
    setProjects(current => current.map(item => item.profile_id === profile.id ? { ...item, profile_id: null } : item));
    setPlaying(current => current && current.profile_id === profile.id ? null : current);
    await refresh(true);
    if (result.file_cleanup_complete) {
      notify("Voice profile permanently deleted", `${profile.name}: ArkByte-managed source recordings, reference clips and profile data were removed. Generated audio and saved projects were kept.`, "success");
    } else {
      notify("Profile removed; file cleanup pending", "The profile is no longer available. Windows is holding some source files; ArkByte will retry cleanup the next time the local service starts.", "warning");
    }
  };

  const clearHistory = async () => {
    if (!history.length || clearingHistory || generating) return;
    const confirmed = window.confirm(`Permanently delete all ${history.length} generation-history item(s) and their generated audio files?\n\nThis does NOT delete voice profiles, original reference recordings, saved projects or model files.`);
    if (!confirmed) return;
    setClearingHistory(true);
    try {
      const result = await api<{ ok: boolean; deleted: number }>("/api/v1/history", { method: "DELETE" });
      setHistory([]);
      setPlaying(null);
      notify("Generation history cleared", `${result.deleted} history item(s) and their generated audio files were deleted.`);
    } catch (error) {
      notify("Could not clear history", error instanceof Error ? error.message : "The local service could not clear generation history.", "error");
      await refresh(true);
    } finally {
      setClearingHistory(false);
    }
  };

  const saveProject = async () => {
    if (!script.trim()) {
      notify("Nothing to save", "Add narration text before saving a project.", "warning");
      return;
    }
    setSavingProject(true);
    try {
      const result = await api<{ project: StudioProject }>("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: currentProjectId || undefined,
          title: projectTitle.trim() || outputName || "Untitled narration",
          script,
          profile_id: selectedProfile || null,
          language_id: language,
          output_name: outputName,
          exaggeration,
          cfg_weight: pace,
          temperature,
          model_id: modelId
        })
      });
      setCurrentProjectId(result.project.id);
      setProjectSaved(true);
      setProjects(current => [toProjectSummary(result.project), ...current.filter(item => item.id !== result.project.id)]);
      notify("Project saved", `“${result.project.title}” is stored in your local project library.`);
    } catch (error) {
      notify("Could not save project", error instanceof Error ? error.message : "Unexpected local error.", "error");
    } finally {
      setSavingProject(false);
    }
  };

  const openProject = async (project: StudioProjectSummary) => {
    setOpeningProjectId(project.id);
    try {
      const result = await api<{ project: StudioProject }>(`/api/v1/projects/${project.id}`);
      const detail = result.project;
      setCurrentProjectId(detail.id);
      setProjectSaved(true);
      setProjectTitle(detail.title);
      setScript(detail.script);
      setSelectedProfile(detail.profile_id || "");
      setLanguage(detail.language_id);
      setOutputName(detail.output_name);
      setExaggeration(detail.exaggeration);
      setPace(detail.cfg_weight);
      setTemperature(detail.temperature);
      setModelId(detail.model_id || "chatterbox");
      goto("script");
      notify("Project opened", `Loaded “${detail.title}”.`, "info");
    } catch (error) {
      notify("Could not open project", error instanceof Error ? error.message : "The saved project could not be loaded.", "error");
    } finally {
      setOpeningProjectId(null);
    }
  };

  const startNewProject = () => {
    setCurrentProjectId(null);
    setProjectSaved(false);
    setProjectTitle("Untitled narration");
    setScript("");
    setOutputName("youtube-narration");
    setModelId("chatterbox");
    setPage("script");
    setMobileNav(false);
  };

  const filteredProfiles = useMemo(() => profiles.filter(item => `${item.name} ${item.language} ${item.source_name}`.toLowerCase().includes(search.toLowerCase())), [profiles, search]);
  const filteredHistory = useMemo(() => history.filter(item => `${item.profile_name} ${item.script_preview} ${item.language}`.toLowerCase().includes(search.toLowerCase())), [history, search]);
  const filteredProjects = useMemo(() => projects.filter(item => `${item.title} ${item.script_preview} ${item.language_id}`.toLowerCase().includes(search.toLowerCase())), [projects, search]);
  const engineReady = Boolean(health?.engine.installed);
  const selectedCapability = modelCapabilities.find(item => item.id === modelId);
  const selectedModelReady = modelId === "chatterbox" ? engineReady : Boolean(selectedCapability?.integrated && selectedCapability.status === "installed");
  const mediaReady = Boolean(health?.media.ffmpeg && health?.media.ffprobe);
  const databaseReady = health?.database.status === "ok";
  const recentHistory = history.slice(0, 4);
  const activeProfile = profiles.find(item => item.id === selectedProfile);
  const totalChars = script.length;

  return <div className="app-frame">
    <div className="ambient ambient-one" /><div className="ambient ambient-two" />
    <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
      <div className="brand-lockup">
        <div className="brand-mark"><AudioWaveform size={23} strokeWidth={2.4} /></div>
        <div><strong>ARKBYTE</strong><span>VOICE STUDIO</span></div>
        <button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={18} /></button>
      </div>
      <nav className="side-nav" aria-label="Main navigation">
        {navItems.map((item, index) => <div key={item.id}>
          {item.section && <div className={`nav-section ${index ? "nav-section-spaced" : ""}`}>{item.section}</div>}
          <button onClick={() => goto(item.id)} className={`nav-item ${page === item.id ? "active" : ""}`} aria-current={page === item.id ? "page" : undefined}>
            <item.icon size={18} strokeWidth={1.9} /><span>{item.label}</span>{item.id === "voices" && profiles.length > 0 && <em>{profiles.length}</em>}
          </button>
        </div>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="privacy-card"><div className="privacy-heading"><ShieldCheck size={15} /> PRIVATE BY DESIGN</div><p>Your voice references, scripts and generated audio stay on this device.</p><div className="privacy-foot"><span className="privacy-dot" /> Local processing only</div></div>
        <div className="sidebar-user"><div className="user-avatar">AB</div><div><strong>Creator workspace</strong><span>Local account</span></div><button className="icon-button" onClick={() => goto("settings")} aria-label="Open settings"><MoreHorizontal size={18} /></button></div>
      </div>
    </aside>

    {mobileNav && <button className="mobile-scrim" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}

    <main className="main-shell">
      <header className="topbar">
        <div className="topbar-left"><button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open menu"><Menu size={20} /></button><div className="breadcrumbs"><span>ArkByte</span><ChevronRight size={14} /><strong>{navItems.find(item => item.id === page)?.label}</strong></div></div>
        <div className="topbar-right"><div className="local-badge"><span /> LOCAL MODE</div><div className="topbar-divider" /><button className="icon-button" onClick={() => void refresh(true)} aria-label="Refresh system status" title="Refresh status"><RefreshCw size={17} className={refreshing ? "spin" : ""} /></button><button className="help-link" onClick={() => goto("settings")}>Help & support</button></div>
      </header>

      <div className="page-content">
        {apiError && <div className="connection-banner"><div className="banner-icon"><CircleAlert size={18} /></div><div><strong>Local service is offline</strong><p>{apiError}</p></div><button className="button button-quiet button-small" onClick={() => void refresh()}>Retry connection <RefreshCw size={14} /></button></div>}

        {page === "overview" && <>
          <div className="page-heading"><div><div className="eyebrow">CREATOR WORKSPACE</div><h1>Overview</h1><p>Your voice workflow, ready for the next narration.</p></div><button className="button button-primary" onClick={() => { setCreateOpen(true); }}><Plus size={17} /> Create voice profile</button></div>
          <section className="hero-card"><div className="hero-glow" /><div className="hero-copy"><div className="eyebrow hero-eyebrow"><span className="live-dot" /> YOUR VOICE WORKFLOW</div><h2>Your voice.<br /><span>Ready for the next script.</span></h2><p>Use recordings you already have. Build a local voice reference, write your narration and create audio without a paid API.</p><div className="hero-actions"><button className="button button-primary" onClick={() => setCreateOpen(true)}><Plus size={17} /> Create voice profile</button><button className="button button-glass" onClick={() => goto("script")}>Open script studio <ArrowRight size={16} /></button></div></div><div className="hero-art"><div className="hero-art-ring ring-one" /><div className="hero-art-ring ring-two" /><div className="hero-art-core"><AudioWaveform size={56} strokeWidth={1.5} /><span>VOICE<br />STUDIO</span></div><div className="hero-art-caption">LOCAL AI · CREATOR CONTROL</div></div><div className="hero-orb orb-a" /><div className="hero-orb orb-b" /></section>
          <div className="stats-grid">
            <StatCard label="Voice profiles" value={profiles.length.toString()} note="Reusable speaker datasets" icon={Mic2} tone="mint" index={0} />
            <StatCard label="Reference clips" value={profiles.reduce((sum, item) => sum + (item.sample_count || 0), 0).toString()} note="Original recordings retained locally" icon={FileAudio} tone="blue" index={1} />
            <StatCard label="Generations" value={history.length.toString()} note="Completed narrations" icon={AudioWaveform} tone="violet" index={2} />
            <StatCard label="Saved projects" value={projects.length.toString()} note="Reusable narration workspaces" icon={FolderOpen} tone="amber" index={3} />
          </div>
          <section className="panel readiness-panel"><div className="section-head"><div><h3>System readiness</h3><p>A quick check of the local components used by the studio.</p></div><button className="button button-quiet button-small" onClick={() => void refresh(true)}><RefreshCw size={14} className={refreshing ? "spin" : ""} /> Run system check</button></div><div className="readiness-grid"><ReadinessItem icon={FileAudio} label="Media tools" detail={mediaReady ? "FFmpeg and FFprobe ready" : "FFmpeg or FFprobe not detected"} ready={mediaReady} /><ReadinessItem icon={Cpu} label="AI engine" detail={!health ? "Checking local service…" : engineReady ? `Chatterbox installed · ${health.engine.cuda ? "GPU available" : "CPU available"}` : "AI engine not installed"} ready={engineReady} warning={!engineReady} /><ReadinessItem icon={Database} label="Local database" detail={databaseReady ? "SQLite integrity check passed" : "Database not available"} ready={databaseReady} /></div></section>
          <div className="overview-grid"><section className="panel workflow-panel"><div className="section-head"><div><h3>A simple creator workflow</h3><p>Four steps from your existing video to a finished narration file.</p></div><span className="soft-label">GET STARTED</span></div><div className="workflow-steps"><WorkflowStep number="01" title="Import a recording" detail="Choose a video or audio file you own." icon={Upload} onClick={() => setCreateOpen(true)} /><WorkflowStep number="02" title="Create a voice profile" detail="Extract a clean 5–30 second reference." icon={Mic2} onClick={() => setCreateOpen(true)} /><WorkflowStep number="03" title="Write your script" detail="Paste your narration and tune delivery." icon={FileText} onClick={() => goto("script")} /><WorkflowStep number="04" title="Generate your audio" detail="Preview and save a local WAV file." icon={Headphones} onClick={() => goto("script")} /></div></section><section className="panel recent-panel"><div className="section-head"><div><h3>Recent generations</h3><p>Your latest narration files.</p></div><button className="text-link" onClick={() => goto("history")}>View all <ArrowRight size={14} /></button></div>{recentHistory.length ? <div className="recent-list">{recentHistory.map(item => <HistoryRow key={item.id} item={item} onPlay={() => setPlaying(item)} />)}</div> : <EmptyState icon={AudioWaveform} title="No narrations yet" detail="Your completed audio projects will appear here." action="Start writing" onAction={() => goto("script")} />}</section></div>
        </>}

        {page === "projects" && <>
          <div className="page-heading"><div><div className="eyebrow">YOUR PRODUCTION WORKSPACE</div><h1>Projects</h1><p>Save scripts, voice choices and generation settings together. Projects stay in your local ArkByte database.</p></div><button className="button button-primary" onClick={startNewProject}><FilePlus2 size={17} /> New project</button></div>
          <div className="toolbar"><div className="search-box"><Search size={16} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search projects and scripts…" /></div><div className="toolbar-note"><LockKeyhole size={14} /> Saved locally · no cloud sync</div></div>
          {loading ? <LoadingPanel label="Loading projects…" /> : filteredProjects.length ? <div className="project-grid">{filteredProjects.map(project => <ProjectCard key={project.id} project={project} opening={openingProjectId === project.id} onOpen={() => void openProject(project)} onDelete={async () => { if (!window.confirm(`Delete the project “${project.title}”? Generated audio and voice profiles will not be deleted.`)) return; try { await api(`/api/v1/projects/${project.id}`, { method: "DELETE" }); setProjects(current => current.filter(item => item.id !== project.id)); if (currentProjectId === project.id) { setCurrentProjectId(null); setProjectSaved(false); } notify("Project deleted", `“${project.title}” was removed. Generated audio was kept.`); } catch (error) { notify("Could not delete project", error instanceof Error ? error.message : "Unexpected local error.", "error"); } }} />)}</div> : <EmptyState icon={FolderOpen} title={search ? "No matching projects" : "Your project library is ready"} detail={search ? "Try another title or script phrase." : "Save a narration from Script Studio to keep its text, voice and delivery settings together."} action={search ? "Clear search" : "Create first project"} onAction={() => search ? setSearch("") : startNewProject()} />}
        </>}

        {page === "voices" && <>
          <div className="page-heading"><div><div className="eyebrow">YOUR REFERENCE COLLECTION</div><h1>Voice library</h1><p>Manage reusable voice references created from recordings you have permission to use.</p></div><button className="button button-primary" onClick={() => setCreateOpen(true)}><Plus size={17} /> New voice profile</button></div>
          <div className="toolbar"><div className="search-box"><Search size={16} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search voice profiles…" /></div><div className="toolbar-note"><LockKeyhole size={14} /> Stored locally on this device</div></div>
          {loading ? <LoadingPanel label="Loading voice profiles…" /> : filteredProfiles.length ? <div className="voice-grid">{filteredProfiles.map((profile, index) => <VoiceCard key={profile.id} profile={profile} index={index} onUse={() => { setSelectedProfile(profile.id); goto("script"); }} onDelete={() => setProfileToDelete(profile)} />)}</div> : <EmptyState icon={Mic2} title={search ? "No matching profiles" : "Your voice library is ready"} detail={search ? "Try a different search term." : "Import an existing video or recording to create your first reusable voice profile."} action={search ? "Clear search" : "Create voice profile"} onAction={() => search ? setSearch("") : setCreateOpen(true)} />}
        </>}

        {page === "lab" && <VoiceLab profiles={profiles} onRefresh={() => refresh(true)} notify={notify} />}

        {page === "customvoice" && <CustomVoiceLab profiles={profiles} notify={notify} />}

        {page === "benchmark" && <BenchmarkLab profiles={profiles} history={history} notify={notify} />}

        {page === "script" && <>
          <div className="page-heading"><div><div className="eyebrow">AI NARRATION WORKSPACE</div><h1>Script studio</h1><p>Shape your narration, tune delivery and generate locally.</p></div><div className="script-heading-actions"><span className="studio-ready"><span className={selectedModelReady ? "ready-dot" : "warning-dot"} />{selectedModelReady ? `${modelId === "voxcpm05" ? "VoxCPM 0.5B" : modelId === "voxcpm2" ? "VoxCPM 2" : "Chatterbox"} available` : "Model setup needed"}</span><button type="button" className="button button-quiet button-small" onClick={saveProject} disabled={savingProject || !script.trim()}>{savingProject ? <Loader2 size={15} className="spin" /> : <Save size={15} />} Save project</button></div></div>
          <form className="script-layout" onSubmit={submitGeneration}>
            <div className="script-main panel"><div className="panel-title-row"><div><h3>Write your narration</h3><p>Keep paragraphs clear. Long scripts are split automatically.</p></div><span className="local-chip"><LockKeyhole size={12} /> PRIVATE</span></div><div className="project-name-row"><div className="form-field"><label htmlFor="project-title">PROJECT NAME</label><input id="project-title" value={projectTitle} onChange={event => { setProjectTitle(event.target.value); setProjectSaved(false); }} maxLength={100} placeholder="Give this narration a name" /></div><span className="project-save-state">{projectSaved ? "All changes saved locally" : currentProjectId ? "Unsaved changes · click Save" : "New project · not saved yet"}</span></div><div className="script-toolbar"><div className="script-tool-label"><FileText size={15} /> MAIN SCRIPT</div><div className="script-toolbar-actions"><button type="button" className="button button-quiet button-small" onClick={saveProject} disabled={savingProject || !script.trim()}>{savingProject ? <Loader2 size={14} className="spin" /> : <Save size={14} />} Save</button><button type="button" className="button button-quiet button-small" onClick={() => { setScript(""); setProjectSaved(false); }} disabled={!script}><Trash2 size={14} /> Clear</button></div></div><textarea className="script-editor" value={script} onChange={event => { setScript(event.target.value); setProjectSaved(false); }} placeholder="Start writing your YouTube narration…&#10;&#10;A good opening captures attention. Keep each paragraph focused and let your voice carry the story." maxLength={50000} /><div className="editor-footer"><span>{totalChars.toLocaleString()} / 50,000 characters</span><span>~{Math.max(1, Math.ceil(totalChars / 850))} min read · estimated</span></div><div className="script-bottom"><div className="output-name-field"><label htmlFor="output-name">OUTPUT FILE NAME</label><input id="output-name" value={outputName} onChange={event => { setOutputName(event.target.value); setProjectSaved(false); }} maxLength={100} /></div><div className="language-field"><label htmlFor="language">LANGUAGE</label><div className="select-wrap"><select id="language" value={language} onChange={event => { setLanguage(event.target.value); setProjectSaved(false); }}>{LANGUAGES.map(([label, code]) => <option value={code} key={code}>{label}</option>)}</select><ChevronDown size={15} /></div></div></div></div>
            <aside className="script-side"><section className="panel voice-select-panel"><div className="side-panel-title"><div><div className="eyebrow">VOICE PROFILE</div><h3>Choose your voice</h3></div><div className="side-icon"><Mic2 size={18} /></div></div>{profiles.length ? <div className="select-wrap voice-select-wrap"><select aria-label="Voice profile" value={selectedProfile} onChange={event => { setSelectedProfile(event.target.value); setProjectSaved(false); }}>{profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name} · {profile.language}</option>)}</select><ChevronDown size={15} /></div> : <div className="inline-empty"><Mic2 size={18} /><span>No voice profiles created yet.</span><button type="button" className="text-link" onClick={() => setCreateOpen(true)}>Create one <ArrowRight size={13} /></button></div>}{activeProfile && <div className="selected-voice"><div className="voice-avatar">{initials(activeProfile.name)}</div><div className="selected-voice-meta"><strong>{activeProfile.name}</strong><span>{activeProfile.language} · local reference</span></div><span className="selected-check"><Check size={14} /></span></div>}</section>
              <section className="panel controls-panel"><div className="section-head compact"><div><h3>Delivery controls</h3><p>Fine-tune the generation style.</p></div><SlidersHorizontal size={17} className="muted-icon" /></div><div className="form-field model-select-field"><label htmlFor="generation-model">GENERATION MODEL</label><div className="select-wrap"><select id="generation-model" value={modelId} onChange={event => { setModelId(event.target.value as "chatterbox" | "voxcpm05" | "voxcpm2"); setProjectSaved(false); }}><option value="chatterbox">Chatterbox Multilingual V3{engineReady ? " · installed" : " · unavailable"}</option><option value="voxcpm05">VoxCPM 0.5B{modelCapabilities.some(item => item.id === "voxcpm05" && item.status === "installed") ? " · installed" : " · install required"}</option><option value="voxcpm2">VoxCPM 2 (2B){modelCapabilities.some(item => item.id === "voxcpm2" && item.status === "installed") ? " · installed" : " · install required · 8 GB VRAM"}</option></select><ChevronDown size={15} /></div><small>{modelId === "voxcpm05" ? "English and Chinese only. Requires a reviewed exact transcript for a reference clip (30 seconds or less). Around 5 GB VRAM is reported; 6 GB GPUs are tight. First use downloads the checkpoint." : modelId === "voxcpm2" ? "Multilingual reference conditioning. The upstream VRAM reference is about 8 GB, so this is not recommended for a 6 GB GPU." : "Chatterbox Multilingual V3 uses reference-audio conditioning and supports the current studio language list."}</small></div><SliderField label="Expression" value={exaggeration} min={0.25} max={2} step={0.05} valueLabel={exaggeration.toFixed(2)} onChange={value => { setExaggeration(value); setProjectSaved(false); }} left="Subtle" right="Expressive" /><SliderField label="Pacing guidance" value={pace} min={0} max={1} step={0.05} valueLabel={pace.toFixed(2)} onChange={value => { setPace(value); setProjectSaved(false); }} left="Relaxed" right="Guided" /><SliderField label="Variation" value={temperature} min={0.05} max={2} step={0.05} valueLabel={temperature.toFixed(2)} onChange={value => { setTemperature(value); setProjectSaved(false); }} left="Consistent" right="Dynamic" /><div className="control-note"><Info size={14} /> Controls are model-dependent. Results may vary by recording quality.</div></section>
              <section className="generate-card"><div className="generate-card-top"><div className="generate-spark"><Sparkles size={18} /></div><span>LOCAL AI GENERATION</span></div><h3>Ready to give your script a voice?</h3><p>Your narration is processed on this device. No paid API or cloud upload.</p><label className="generation-policy-check"><input type="checkbox" checked={generationRightsAck} disabled={generating} onChange={event => setGenerationRightsAck(event.target.checked)} /><span>I own this voice or have the speaker’s explicit permission. I will not use generated speech to impersonate or deceive, commit fraud, harass anyone, create non-consensual intimate content, or bypass identity/biometric verification. I will disclose synthetic speech where people could mistake it for a real recording.</span></label><button className="button button-primary generate-button" type="submit" disabled={generating || !profiles.length || !selectedModelReady || !script.trim() || !generationRightsAck}>{generating ? <><Loader2 size={17} className="spin" /> Generating…</> : <><WandSparkles size={17} /> Generate narration <ArrowRight size={16} /></>}</button><div className="generate-meta"><span><ShieldCheck size={13} /> Private</span><span><Zap size={13} /> GPU / CPU fallback</span></div></section>
            </aside>
          </form>
          {activeJob && <section className={`panel job-panel job-${activeJob.status}`}><div className="job-header"><div><div className="eyebrow">GENERATION TASK</div><h3>{activeJob.status === "complete" ? "Your narration is ready" : activeJob.status === "failed" ? "Generation needs attention" : "Creating your narration"}</h3><p>{activeJob.message}</p></div><span className={`job-status ${activeJob.status}`}>{activeJob.status}</span></div><div className="progress-track"><i style={{ width: `${Math.max(2, activeJob.progress * 100)}%` }} /></div><div className="job-footer"><span>{Math.round(activeJob.progress * 100)}% complete</span>{activeJob.status === "complete" && activeJob.audio_url && <a className="button button-primary button-small" href={`${activeJob.audio_url}?download=1`}><Download size={14} /> Download WAV</a>}{activeJob.status === "failed" && <span className="error-inline">{activeJob.error?.code}</span>}</div></section>}
        </>}

        {page === "history" && <>
          <div className="page-heading"><div><div className="eyebrow">YOUR AUDIO OUTPUTS</div><h1>Generation history</h1><p>Review, download or permanently delete narrations created on this device.</p></div><div className="history-heading-actions"><button className="button button-quiet" onClick={() => void refresh(true)}><RefreshCw size={15} /> Refresh</button>{history.length > 0 && <button className="button button-danger-quiet" onClick={() => void clearHistory()} disabled={clearingHistory || generating}>{clearingHistory ? <Loader2 size={15} className="spin" /> : <Trash2 size={15} />} Clear history</button>}</div></div>
          <div className="toolbar"><div className="search-box"><Search size={16} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search scripts and voice profiles…" /></div><div className="toolbar-note"><FileAudio size={14} /> WAV audio · local files</div></div>
          {filteredHistory.length ? <div className="panel history-panel"><div className="history-table-head"><span>PROJECT</span><span>VOICE</span><span>CREATED</span><span>STATUS</span><span /></div>{filteredHistory.map(item => <HistoryTableRow key={item.id} item={item} onPlay={() => setPlaying(item)} onDelete={() => void deleteHistoryItem(item)} deleting={deletingHistoryId === item.id} />)}</div> : <EmptyState icon={AudioWaveform} title="No generated audio yet" detail="Completed narrations will be listed here with local playback and download links." action="Open script studio" onAction={() => goto("script")} />}
        </>}

        {page === "about" && <>
          <div className="page-heading"><div><div className="eyebrow">THE CREATOR & THE PROJECT</div><h1>About ArkByte</h1><p>A local-first voice creation studio built by a developer working at the intersection of AI and software.</p></div><a className="button button-quiet" href="https://github.com/costaspinto" target="_blank" rel="noreferrer">GitHub profile <ArrowRight size={15} /></a></div>
          <section className="about-hero panel"><div className="about-avatar">CP</div><div className="about-hero-copy"><div className="eyebrow">CREATOR · ARKBYTE</div><h2>Costas Pinto</h2><p>Computer Science graduate and AI/ML engineer focused on building practical AI products, Generative AI applications, LLM workflows and full-stack software. ArkByte is the space where those ideas become usable tools.</p><div className="about-meta"><span><CheckCircle2 size={14} /> MCA · AI & Machine Learning</span><span><CheckCircle2 size={14} /> CGPA 9.07</span><span><CheckCircle2 size={14} /> Computer Science</span></div></div></section>
          <div className="about-grid">
            <section className="panel about-card"><div className="eyebrow">EDUCATION</div><h3>Academic background</h3><div className="about-item"><strong>Master of Computer Applications</strong><span>Artificial Intelligence & Machine Learning · Manipal University Jaipur · 9.07 CGPA</span></div><div className="about-item"><strong>Bachelor of Science</strong><span>Computer Science · Shivaji University, Kolhapur</span></div></section>
            <section className="panel about-card"><div className="eyebrow">SELECTED PROJECTS</div><h3>Applied AI work</h3><div className="about-projects"><span>DocuReadAI <small>RAG document assistant</small></span><span>PulmoProbe AI <small>ML prediction application</small></span><span>WildScan <small>Computer vision</small></span><span>EcoSim <small>Simulation and modelling</small></span><span>Atomic Explorer <small>Interactive learning tool</small></span></div></section>
          </div>
          <section className="panel about-card about-skills"><div className="eyebrow">TECHNOLOGY</div><h3>Tools used across the work</h3><div className="about-tags">{["Python","PyTorch","TensorFlow","Scikit-learn","LangChain","Hugging Face","LLMs & RAG","FastAPI","Flask","React","Next.js","TypeScript","SQL","Docker","Git","Google Cloud","IBM watsonx.ai"].map(skill => <span key={skill}>{skill}</span>)}</div></section>
          <p className="about-footnote">ArkByte Voice Studio is a local-first project. Voice profiles require an ownership/permission confirmation, and every generation requires a separate responsible-use acknowledgement. Do not impersonate, deceive, defraud, harass or bypass identity verification. Disclose synthetic speech where listeners could mistake it for a real recording. Read docs/SAFE-USE-POLICY.md for the full policy.</p>
        </>}

        {page === "settings" && <>
          <div className="page-heading"><div><div className="eyebrow">LOCAL ENVIRONMENT</div><h1>Settings & health</h1><p>Check your local engine, media tools and storage health.</p></div><button className="button button-quiet" onClick={() => void refresh(true)}><RefreshCw size={15} className={refreshing ? "spin" : ""} /> Run diagnostics</button></div>
          <div className="settings-grid"><section className="panel settings-main"><div className="section-head"><div><h3>System components</h3><p>Live checks from the local Python service.</p></div><span className="soft-label">LOCAL</span></div><div className="component-list"><ComponentRow icon={Cpu} title="Chatterbox AI engine" detail={health?.engine.installed ? `Installed · ${health.engine.loaded ? "model loaded" : "loads on demand"}` : "Not detected in the current Python environment"} ready={Boolean(health?.engine.installed)} /><ComponentRow icon={Zap} title="Hardware acceleration" detail={health?.engine.cuda ? "CUDA GPU detected" : health?.engine.torch ? "CPU mode available · no CUDA device detected" : "PyTorch not detected"} ready={Boolean(health?.engine.cuda)} warning={Boolean(health?.engine.installed && !health?.engine.cuda)} /><ComponentRow icon={FileAudio} title="FFmpeg / FFprobe" detail={mediaReady ? "Both media tools detected" : "One or more media tools are missing"} ready={mediaReady} /><ComponentRow icon={Database} title="Local database" detail={health?.database.status || "Checking…"} ready={databaseReady} /></div><div className="diagnostic-actions"><button className="button button-primary" onClick={() => void refresh()}><Activity size={16} /> Re-run full health check</button><a className="button button-quiet" href="/api/v1/health" target="_blank" rel="noreferrer">View health response <ArrowRight size={14} /></a></div></section><section className="settings-stack"><div className="panel privacy-settings"><div className="settings-icon mint"><ShieldCheck size={20} /></div><h3>Private by design</h3><p>The web UI communicates with a loopback-only Python service. Voice media and generated audio are stored in your local ArkByte data directory.</p><div className="privacy-list"><span><CheckCircle2 size={14} /> No paid APIs</span><span><CheckCircle2 size={14} /> Local inference</span><span><CheckCircle2 size={14} /> No remote account</span></div></div><div className="panel support-card"><div className="settings-icon blue"><Info size={19} /></div><h3>Need help?</h3><p>If an operation fails, the Python service writes a rotating diagnostic log. Keep the log private before sharing it.</p><div className="support-foot"><span>ArkByte Voice Studio Web 1.2.0</span><span>Build · Local edition</span></div></div></section></div>
        </>}
      </div>
      <footer className="app-footer"><span>© ArkByte Voice Studio</span><span><span className="footer-dot" /> LOCAL-FIRST · NO PAID API</span><span>Web edition 1.2.0</span></footer>
    </main>

    {playing && <div className="audio-dock"><div className="dock-art"><AudioWaveform size={21} /></div><div className="dock-meta"><strong>{playing.script_preview || "Narration"}</strong><span>{playing.profile_name} · {playing.language}</span></div><audio ref={audioRef} controls src={playing.audio_url || undefined} autoPlay onError={() => notify("Audio unavailable", "The audio file may have been moved or deleted.", "error")} /><button className="icon-button" onClick={() => setPlaying(null)} aria-label="Close audio player"><X size={17} /></button></div>}
    {createOpen && <CreateProfileModal onClose={() => setCreateOpen(false)} onCreated={async profile => { setCreateOpen(false); setSelectedProfile(profile.id); notify("Voice profile created", `${profile.name} is ready for script generation.`); await refresh(true); goto("script"); }} notify={notify} />}
    {profileToDelete && <DeleteVoiceProfileModal profile={profileToDelete} onClose={() => setProfileToDelete(null)} onConfirm={() => permanentlyDeleteVoiceProfile(profileToDelete)} />}
    <ToastStack toasts={toasts} dismiss={dismissToast} />
  </div>;
}

function LoadingPanel({ label }: { label: string }) {
  return (
    <div
      className="panel"
      role="status"
      aria-live="polite"
      aria-busy="true"
      style={{
        minHeight: 160,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 10
      }}
    >
      <Loader2 size={18} className="spin" />
      <span>{label}</span>
    </div>
  );
}
function StatCard({ label, value, note, icon: Icon, tone, index }: { label: string; value: string; note: string; icon: typeof Home; tone: string; index: number }) {
  return <div className={`stat-card stat-${tone}`} style={{ animationDelay: `${index * 80}ms` }}><div className="stat-top"><span>{label}</span><div className="stat-icon"><Icon size={17} /></div></div><strong>{value}</strong><p>{note}</p><div className="stat-shine" /></div>;
}
function ReadinessItem({ icon: Icon, label, detail, ready, warning = false }: { icon: typeof Home; label: string; detail: string; ready: boolean; warning?: boolean }) {
  return <div className={`readiness-item ${warning && !ready ? "readiness-warning" : ready ? "readiness-good" : "readiness-bad"}`}><div className="readiness-icon"><Icon size={17} /></div><div><strong>{label}</strong><span>{detail}</span></div><i>{ready ? <Check size={15} /> : <CircleAlert size={15} />}</i></div>;
}
function WorkflowStep({ number, title, detail, icon: Icon, onClick }: { number: string; title: string; detail: string; icon: typeof Home; onClick: () => void }) {
  return <button className="workflow-step" onClick={onClick}><span className="step-number">{number}</span><span className="step-icon"><Icon size={18} /></span><span className="step-copy"><strong>{title}</strong><small>{detail}</small></span><ChevronRight size={17} className="step-arrow" /></button>;
}
function EmptyState({ icon: Icon, title, detail, action, onAction }: { icon: typeof Home; title: string; detail: string; action: string; onAction: () => void }) {
  return <div className="empty-state"><div className="empty-icon"><Icon size={25} /></div><h3>{title}</h3><p>{detail}</p><button className="button button-quiet" onClick={onAction}>{action} <ArrowRight size={15} /></button></div>;
}
function HistoryRow({ item, onPlay }: { item: HistoryItem; onPlay: () => void }) {
  return <div className="recent-row"><button className="play-tile" onClick={onPlay} disabled={!item.audio_url} aria-label="Play narration"><Play size={14} fill="currentColor" /></button><div className="recent-row-copy"><strong>{item.script_preview || "Narration"}</strong><span>{item.profile_name} · {formatDate(item.created_at)}</span></div><button className="icon-button" onClick={onPlay} disabled={!item.audio_url} aria-label="Open audio"><ArrowRight size={15} /></button></div>;
}
function ProjectCard({ project, opening, onOpen, onDelete }: { project: StudioProjectSummary; opening: boolean; onOpen: () => void; onDelete: () => void }) {
  return <article className="project-card">
    <div className="project-card-top"><div className="project-card-icon"><FolderOpen size={21} /></div><span className="project-updated">Updated {formatDate(project.updated_at)}</span></div>
    <h3>{project.title}</h3>
    <p>{project.script_preview || "No script content"}{project.character_count > project.script_preview.length ? "…" : ""}</p>
    <div className="project-meta"><span><FileText size={13} /> {project.character_count.toLocaleString()} characters</span><span><AudioWaveform size={13} /> {project.language_id.toUpperCase()}</span></div>
    <div className="project-card-footer"><button className="button button-primary button-small" onClick={onOpen} disabled={opening}>{opening ? <Loader2 size={14} className="spin" /> : null}{opening ? "Opening…" : "Open project"} {!opening && <ArrowRight size={14} />}</button><button className="icon-button" onClick={onDelete} aria-label={`Delete ${project.title}`} title="Delete project"><Trash2 size={15} /></button></div>
  </article>;
}

function VoiceCard({ profile, index, onUse, onDelete }: { profile: VoiceProfile; index: number; onUse: () => void; onDelete: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return <article className="voice-card" style={{ animationDelay: `${index * 55}ms` }}><div className="voice-card-top"><div className={`voice-profile-art art-${index % 4}`}><AudioWaveform size={25} /></div><div className="voice-card-actions"><button className="icon-button" onClick={() => setMenuOpen(value => !value)} aria-label="Profile actions"><MoreHorizontal size={18} /></button>{menuOpen && <div className="profile-menu"><button onClick={() => { setMenuOpen(false); onUse(); }}><WandSparkles size={14} /> Use in script studio</button><button className="danger-text" onClick={() => { setMenuOpen(false); onDelete(); }}><Trash2 size={14} /> Delete profile</button></div>}</div></div><div className="voice-card-name"><h3>{profile.name}</h3><span className="voice-language">{profile.language}</span></div><p className="voice-source"><FileAudio size={14} /> {profile.source_name}</p><div className="voice-card-wave"><Waveform bars={26} /></div><div className="voice-card-footer"><span><span className="privacy-dot" /> Saved locally</span><button className="button button-quiet button-small" onClick={onUse}>Use voice <ArrowRight size={14} /></button></div></article>;
}
function HistoryTableRow({ item, onPlay, onDelete, deleting }: { item: HistoryItem; onPlay: () => void; onDelete: () => void; deleting: boolean }) {
  return <div className="history-table-row"><div className="history-project"><div className="history-file-icon"><FileAudio size={17} /></div><div><strong>{item.script_preview || "Narration"}</strong><span>{item.language}</span></div></div><span className="history-voice">{item.profile_name}</span><span className="history-date">{formatDate(item.created_at)}</span><span><span className="complete-pill"><i /> Complete</span></span><div className="history-actions"><button className="icon-button" disabled={!item.audio_url} onClick={onPlay} aria-label="Play"><Play size={15} /></button>{item.audio_url && <a className="icon-button" href={`${item.audio_url}?download=1`} aria-label="Download"><Download size={15} /></a>}<button className="icon-button history-delete" disabled={deleting} onClick={onDelete} aria-label="Delete history item" title="Delete generated audio and history">{deleting ? <Loader2 size={15} className="spin" /> : <Trash2 size={15} />}</button></div></div>;
}
function SliderField({ label, value, min, max, step, valueLabel, onChange, left, right }: { label: string; value: number; min: number; max: number; step: number; valueLabel: string; onChange: (value: number) => void; left: string; right: string }) {
  return <div className="slider-field"><div className="slider-label"><label>{label}</label><strong>{valueLabel}</strong></div><input type="range" min={min} max={max} step={step} value={value} onChange={event => onChange(Number(event.target.value))} style={{ "--range-progress": `${((value - min) / (max - min)) * 100}%` } as React.CSSProperties} /><div className="slider-ends"><span>{left}</span><span>{right}</span></div></div>;
}
function ComponentRow({ icon: Icon, title, detail, ready, warning = false }: { icon: typeof Home; title: string; detail: string; ready: boolean; warning?: boolean }) {
  return <div className="component-row"><div className="component-icon"><Icon size={18} /></div><div className="component-copy"><strong>{title}</strong><span>{detail}</span></div><StatusPill ok={ready} warning={warning && !ready}>{ready ? "Ready" : warning ? "Optional" : "Needs attention"}</StatusPill></div>;
}

function DeleteVoiceProfileModal({ profile, onClose, onConfirm }: { profile: VoiceProfile; onClose: () => void; onConfirm: () => Promise<void> }) {
  const [phrase, setPhrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const exactPhrase = phrase === "DELETE VOICE";
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!exactPhrase || busy) return;
    setBusy(true);
    setError("");
    try {
      await onConfirm();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The voice profile could not be deleted. No success was reported.");
    } finally {
      setBusy(false);
    }
  };
  return <div className="modal-backdrop delete-profile-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}>
    <div className="modal-card delete-profile-modal" role="dialog" aria-modal="true" aria-labelledby="delete-voice-title" aria-describedby="delete-voice-description">
      <div className="modal-header"><div><div className="eyebrow danger-eyebrow">PERMANENT VOICE DATA REMOVAL</div><h2 id="delete-voice-title">Delete voice profile?</h2><p id="delete-voice-description">This removes <strong>{profile.name}</strong> from the local profile library and permanently deletes its ArkByte-managed reference recordings.</p></div><button className="icon-button" onClick={onClose} disabled={busy} aria-label="Close delete dialog"><X size={19} /></button></div>
      <form onSubmit={submit} className="delete-profile-form">
        <div className="delete-profile-warning"><ShieldCheck size={18} /><div><strong>What will be deleted</strong><p>Original enrolled clips, processed reference audio, transcripts, profile analysis, pronunciation rules and the profile record.</p><strong>What will be kept</strong><p>Generated narrations, saved projects, model files and model caches. Copies you previously exported or copied outside ArkByte are not removed.</p></div></div>
        <div className="form-field"><label htmlFor="delete-voice-confirmation">TYPE DELETE VOICE TO CONFIRM</label><input id="delete-voice-confirmation" value={phrase} onChange={event => setPhrase(event.target.value)} autoComplete="off" autoFocus spellCheck={false} placeholder="DELETE VOICE" disabled={busy} /></div>
        {error && <p className="delete-profile-error" role="alert">{error}</p>}
        <div className="modal-footer"><span><LockKeyhole size={13} /> The local service checks this phrase too.</span><div className="delete-profile-actions"><button type="button" className="button button-quiet" onClick={onClose} disabled={busy}>Cancel</button><button type="submit" className="button button-delete-confirm" disabled={!exactPhrase || busy}>{busy ? <><Loader2 size={15} className="spin" /> Deleting…</> : <><Trash2 size={15} /> Permanently delete voice</>}</button></div></div>
      </form>
    </div>
  </div>;
}

function CreateProfileModal({ onClose, onCreated, notify }: { onClose: () => void; onCreated: (profile: VoiceProfile) => void; notify: (title: string, message: string, kind?: Toast["kind"]) => void }) {
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("English");
  const [file, setFile] = useState<File | null>(null);
  const [start, setStart] = useState(0);
  const [duration, setDuration] = useState(12);
  const [denoise, setDenoise] = useState(true);
  const [consent, setConsent] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const allowed = ["mp4", "mov", "mkv", "avi", "webm", "wav", "mp3", "m4a", "flac", "aac", "ogg"];
  const pickFile = (next?: File) => {
    if (!next) return;
    const extension = next.name.split(".").pop()?.toLowerCase() || "";
    if (!allowed.includes(extension)) { notify("Unsupported file", "Choose MP4, MOV, MKV, AVI, WEBM, WAV, MP3, M4A, FLAC, AAC or OGG.", "error"); return; }
    if (next.size > 10 * 1024 * 1024 * 1024) { notify("File is too large", "The maximum supported import size is 10 GB.", "error"); return; }
    setFile(next);
    if (!name) setName(next.name.replace(/\.[^.]+$/, "").slice(0, 64));
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !name.trim() || !consent) { notify("Complete the required fields", "Add a file, profile name and voice permission confirmation.", "error"); return; }
    const data = new FormData();
    data.set("file", file);
    data.set("name", name.trim());
    data.set("language", language);
    data.set("start_seconds", String(start));
    data.set("duration_seconds", String(duration));
    data.set("denoise", String(denoise));
    data.set("consent_ack", "true");
    setBusy(true);
    try {
      const result = await api<{ profile: VoiceProfile }>("/api/v1/profiles", { method: "POST", body: data });
      onCreated(result.profile);
    } catch (error) {
      notify("Voice profile could not be created", error instanceof Error ? error.message : "Unexpected import error.", "error");
    } finally {
      setBusy(false);
    }
  };
  return <div className="modal-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}><div className="modal-card create-modal" role="dialog" aria-modal="true" aria-labelledby="create-title"><div className="modal-header"><div><div className="eyebrow">VOICE LIBRARY</div><h2 id="create-title">Create a voice profile</h2><p>Use a recording you own or have permission to clone.</p></div><button className="icon-button" onClick={onClose} disabled={busy} aria-label="Close modal"><X size={19} /></button></div><form onSubmit={submit}><div className={`drop-zone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); pickFile(event.dataTransfer.files[0]); }} onClick={() => inputRef.current?.click()} role="button" tabIndex={0} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}><input ref={inputRef} type="file" accept="video/*,audio/*,.mkv,.flac,.m4a,.aac,.ogg" hidden onChange={event => pickFile(event.target.files?.[0])} />{file ? <><div className="drop-icon success"><CheckCircle2 size={23} /></div><strong>{file.name}</strong><span>{formatBytes(file.size)} · Ready to process</span><small>Click to choose a different file</small></> : <><div className="drop-icon"><Upload size={23} /></div><strong>Drop your video or audio here</strong><span>or browse files from this device</span><small>MP4, MOV, MKV, WAV, MP3 and more · Up to 10 GB</small></>}</div><div className="form-grid"><div className="form-field"><label htmlFor="profile-name">PROFILE NAME</label><input id="profile-name" value={name} onChange={event => setName(event.target.value)} placeholder="e.g. My YouTube Voice" maxLength={80} required /></div><div className="form-field"><label htmlFor="profile-language">LANGUAGE</label><div className="select-wrap"><select id="profile-language" value={language} onChange={event => setLanguage(event.target.value)}>{LANGUAGES.map(([label]) => <option key={label}>{label}</option>)}</select><ChevronDown size={15} /></div></div></div><div className="form-grid segment-grid"><div className="form-field"><label htmlFor="start-seconds">START AT (SECONDS)</label><input id="start-seconds" type="number" min="0" max="86400" step="0.5" value={start} onChange={event => setStart(Math.max(0, Number(event.target.value)))} /></div><div className="form-field"><label htmlFor="duration-seconds">REFERENCE LENGTH</label><div className="select-wrap"><select id="duration-seconds" value={duration} onChange={event => setDuration(Number(event.target.value))}><option value="5">5 seconds</option><option value="8">8 seconds</option><option value="12">12 seconds</option><option value="15">15 seconds</option><option value="20">20 seconds</option><option value="25">25 seconds</option><option value="30">30 seconds</option></select><ChevronDown size={15} /></div></div></div><label className="check-row"><input type="checkbox" checked={denoise} onChange={event => setDenoise(event.target.checked)} /><span><strong>Clean and normalize reference audio</strong><small>Apply basic filtering and loudness normalization during extraction.</small></span></label><label className="consent-row"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /><span>I own this voice or have the speaker’s explicit permission. I will not use it for impersonation, deception, fraud, harassment or identity-verification bypass.</span></label><div className="modal-footer"><span><LockKeyhole size={13} /> Uploaded media is processed locally.</span><button className="button button-primary" type="submit" disabled={busy || !file || !consent}>{busy ? <><Loader2 size={16} className="spin" /> Creating profile…</> : <><Plus size={16} /> Create voice profile</>}</button></div></form></div></div>;
}
