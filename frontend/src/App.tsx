import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import {
  Activity,
  AudioLines,
  AlertTriangle,
  ArrowLeft,
  Check,
  ChevronRight,
  Download,
  LogOut,
  MessageSquare,
  PhoneOff,
  Plus,
  Send,
  ShieldCheck,
  UserRound,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { api, errorMessage, isUnauthorized } from "./api";
import type {
  Consultation,
  Message,
  Patient,
  SafetyEvent,
  Summary,
  User,
} from "./types";

const TOKEN_KEY = "continuum-token";

function formatDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value))
    : "Not recorded";
}

function Login({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [username, setUsername] = useState("clinician");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = new URLSearchParams({ username, password });
      const { data } = await api.post("/auth/login", body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      localStorage.setItem(TOKEN_KEY, data.access_token);
      onAuthenticated();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function signup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ""));
    try {
      const { data } = await api.post("/auth/patient-signup", payload);
      localStorage.setItem(TOKEN_KEY, data.access_token);
      onAuthenticated();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  function changeMode(nextMode: "login" | "signup") {
    setMode(nextMode);
    setError("");
  }

  return (
    <main className="login-shell">
      <section className="login-brand">
        <div className="brand-mark"><Activity size={26} /></div>
        <div>
          <span className="eyebrow">Clinical follow-up</span>
          <h1>Continuum</h1>
        </div>
        <p>Patient history that carries forward, with structured assessment and clinician oversight.</p>
        <div className="pulse-line" aria-hidden="true"><span /></div>
      </section>
      <section className="login-panel">
        <div className="auth-panel">
          <nav className="auth-switch" aria-label="Authentication mode"><button className={mode === "login" ? "active" : ""} onClick={() => changeMode("login")}>Sign in</button><button className={mode === "signup" ? "active" : ""} onClick={() => changeMode("signup")}>Sign up</button></nav>
        {mode === "login" ? <form key="login" onSubmit={submit} className="login-form">
          <div>
            <span className="eyebrow">Secure access</span>
            <h2>Sign in</h2>
          </div>
          <label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} required /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          {error && <p className="form-error">{error}</p>}
          <button className="primary wide" disabled={busy}>{busy ? "Signing in..." : "Sign in"}<ChevronRight size={18} /></button>
          <p className="privacy-note"><ShieldCheck size={16} /> Authorized clinical use only</p>
        </form> : <form key="signup" onSubmit={signup} className="login-form signup-login-form">
          <div>
            <span className="eyebrow">Patient registration</span>
            <h2>Create account</h2>
          </div>
          <div className="auth-name-row"><label>First name<input name="first_name" required /></label><label>Last name<input name="last_name" required /></label></div>
          <label>Date of birth<input name="date_of_birth" type="date" /></label>
          <label>Username<input name="username" minLength={3} maxLength={100} pattern="[A-Za-z0-9_.-]+" autoComplete="username" required /></label>
          <label>Password<input name="password" type="password" minLength={10} maxLength={128} autoComplete="new-password" required /></label>
          {error && <p className="form-error">{error}</p>}
          <button className="primary wide" disabled={busy}><UserPlus size={18} />{busy ? "Creating account..." : "Create account"}</button>
          <p className="privacy-note"><ShieldCheck size={16} /> Patient account access</p>
        </form>}
        </div>
      </section>
    </main>
  );
}

function NewPatientDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (patient: Patient) => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ""));
    try {
      const { data } = await api.post<Patient>("/patients", payload);
      onCreated(data);
    } catch (requestError) {
      setError(errorMessage(requestError));
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="new-patient-title">
        <header><div><span className="eyebrow">Registry</span><h2 id="new-patient-title">New patient</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><X /></button></header>
        <form onSubmit={submit} className="form-grid">
          <label>First name<input name="first_name" required /></label>
          <label>Last name<input name="last_name" required /></label>
          <label className="span-two">Date of birth<input name="date_of_birth" type="date" /></label>
          <div className="form-separator span-two"><span>Optional patient portal</span></div>
          <label>Portal username<input name="portal_username" minLength={3} /></label>
          <label>Portal password<input name="portal_password" type="password" minLength={10} /></label>
          {error && <p className="form-error span-two">{error}</p>}
          <footer className="span-two"><button type="button" className="ghost" onClick={onClose}>Cancel</button><button className="primary" disabled={busy}><Plus size={17} />{busy ? "Creating..." : "Create patient"}</button></footer>
        </form>
      </section>
    </div>
  );
}

function VoiceConversation({ consultationId, onClose, onMessage }: { consultationId: string; onClose: () => void; onMessage: () => void }) {
  const [status, setStatus] = useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  const [patientText, setPatientText] = useState("");
  const [agentText, setAgentText] = useState("");
  const [error, setError] = useState("");
  const speechRecognition = useRef<BrowserSpeechRecognition | null>(null);
  const conversationActive = useRef(true);
  const listenRef = useRef<() => void>(() => undefined);

  useEffect(() => {
    const startTimer = window.setTimeout(() => listenRef.current(), 0);
    return () => {
      window.clearTimeout(startTimer);
      conversationActive.current = false;
      speechRecognition.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, []);

  function speakResponse(message: Message) {
    const speech = new SpeechSynthesisUtterance(message.content);
    speech.lang = navigator.language || "en-US";
    speech.rate = 0.95;
    speech.onstart = () => setStatus("speaking");
    speech.onend = () => {
      if (conversationActive.current) listen();
    };
    speech.onerror = () => {
      conversationActive.current = false;
      setStatus("idle");
      setError("The spoken response could not be played.");
    };
    window.speechSynthesis.speak(speech);
  }

  async function sendSpokenMessage(transcript: string) {
    setPatientText(transcript);
    setStatus("thinking");
    try {
      const { data } = await api.post<Message[]>(`/consultations/${consultationId}/messages`, { content: transcript });
      const response = data.find((item) => item.role === "agent");
      if (!response) throw new Error("No voice response was returned");
      setAgentText(response.content);
      onMessage();
      speakResponse(response);
    } catch (requestError) {
      conversationActive.current = false;
      setStatus("idle");
      setError(errorMessage(requestError));
    }
  }

  function listen() {
    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Recognition || !("speechSynthesis" in window)) {
      setError("Voice sessions are not supported by this browser.");
      return;
    }
    conversationActive.current = true;
    window.speechSynthesis.cancel();
    setError("");
    setPatientText("");
    setAgentText("");
    let transcript = "";
    const recognition = new Recognition();
    recognition.lang = navigator.language || "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.onstart = () => setStatus("listening");
    recognition.onresult = (event) => {
      transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      setPatientText(transcript.trim());
    };
    recognition.onerror = (event) => {
      if (event.error === "no-speech") {
        transcript = "";
        return;
      }
      const denied = event.error === "not-allowed" || event.error === "service-not-allowed";
      conversationActive.current = false;
      setError(denied ? "Microphone permission was not granted." : "Speech could not be recognized. Please try again.");
      setStatus("idle");
      transcript = "";
    };
    recognition.onend = () => {
      speechRecognition.current = null;
      const finalTranscript = transcript.trim();
      if (finalTranscript) void sendSpokenMessage(finalTranscript);
      else if (conversationActive.current) listen();
      else setStatus("idle");
    };
    speechRecognition.current = recognition;
    try {
      recognition.start();
    } catch {
      setStatus("idle");
      setError("The voice session could not be started.");
    }
  }
  listenRef.current = listen;

  function close() {
    conversationActive.current = false;
    speechRecognition.current?.abort();
    window.speechSynthesis?.cancel();
    onClose();
  }

  const statusText = {
    idle: "Ready to listen",
    listening: "Listening...",
    thinking: "Preparing response...",
    speaking: "Agent is speaking...",
  }[status];

  return (
    <div className="modal-backdrop voice-backdrop">
      <section className="voice-session" role="dialog" aria-modal="true" aria-labelledby="voice-session-title">
        <header><div className="voice-brand"><AudioLines /><span><span className="eyebrow">Voice conversation</span><h2 id="voice-session-title">Follow-up call</h2></span></div><button className="icon-button" onClick={close} aria-label="Close voice session"><X /></button></header>
        <div className={`voice-stage ${status}`}>
          <div className="voice-rings" aria-hidden="true"><span /><span /><span /></div>
          <div className="voice-activity" aria-hidden="true"><AudioLines /></div>
          <h3>{statusText}</h3>
          {patientText && <div className="voice-transcript"><span>You said</span><p>{patientText}</p></div>}
          {agentText && <div className="voice-transcript agent"><span>Agent</span><p>{agentText}</p></div>}
          {error && <p className="form-error voice-error">{error}</p>}
        </div>
        <footer><button className="end-call" onClick={close}><PhoneOff />End voice session</button></footer>
      </section>
    </div>
  );
}

function ConsultationWorkspace({ consultation, canManage, canDownloadReport, onRefresh }: { consultation: Consultation; canManage: boolean; canDownloadReport: boolean; onRefresh: () => void }) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [showVoiceSession, setShowVoiceSession] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);

  useEffect(() => {
    setError("");
  }, [consultation.public_id]);

  useEffect(() => {
    if (consultation.status !== "completed") {
      setSummary(null);
      return;
    }
    api.get<Summary>(`/consultations/${consultation.public_id}/summary`)
      .then(({ data }) => setSummary(data))
      .catch((requestError) => setError(errorMessage(requestError)));
  }, [consultation.public_id, consultation.status]);

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!message.trim()) return;
    setSending(true);
    try {
      await api.post(`/consultations/${consultation.public_id}/messages`, { content: message });
      setMessage("");
      onRefresh();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSending(false);
    }
  }

  function handleMessageKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function complete() {
    try {
      await api.post(`/consultations/${consultation.public_id}/complete`);
      onRefresh();
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  async function reviewSummary(review_status: "approved" | "rejected") {
    if (!summary) return;
    try {
      const { data } = await api.patch<Summary>(`/summaries/${summary.id}`, { review_status });
      setSummary(data);
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  async function downloadReport() {
    setDownloadingReport(true);
    setError("");
    try {
      const response = await api.get(
        `/consultations/${consultation.public_id}/report.pdf`,
        { responseType: "blob" },
      );
      const disposition = response.headers["content-disposition"] as string | undefined;
      const filename = disposition?.match(/filename="?([^";]+)"?/)?.[1]
        ?? `patient-followup-report-${consultation.public_id.slice(0, 8)}.pdf`;
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDownloadingReport(false);
    }
  }

  return (
    <section className="consultation-workspace">
      <header className="workspace-header"><div><span className={`status ${consultation.status}`}>{consultation.status}</span><h2>Consultation</h2><p>{formatDate(consultation.started_at)}</p></div>{consultation.requires_review && <span className="review-flag"><AlertTriangle size={16} />Review required</span>}<div className="header-actions">{canDownloadReport && consultation.status === "completed" && <button className="secondary" onClick={downloadReport} disabled={downloadingReport}><Download size={17} />{downloadingReport ? "Preparing..." : "Download PDF"}</button>}{consultation.status === "active" && <button className="voice-session-button" onClick={() => setShowVoiceSession(true)}><AudioLines size={17} />Voice session</button>}{consultation.status === "active" && <button className="ghost" onClick={complete}><Check size={17} />Complete</button>}</div></header>
      <div className="messages" aria-live="polite">{consultation.messages.sort((a, b) => a.sequence_number - b.sequence_number).map((item) => <article key={item.id} className={`message ${item.role}`}><div className="message-meta">{item.role === "agent" ? "Follow-up agent" : item.role}<span>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></div><p>{item.content}</p>{item.flagged && <AlertTriangle className="message-alert" size={17} />}</article>)}</div>
      {summary && <section className="summary-review"><div><span className="eyebrow">Consultation summary</span><p>{summary.content}</p></div><div><span className={`status ${summary.review_status}`}>{summary.review_status}</span>{canManage && summary.review_status === "draft" && <><button className="secondary" onClick={() => reviewSummary("approved")}><Check size={16} />Approve</button><button className="ghost" onClick={() => reviewSummary("rejected")}><X size={16} />Reject</button></>}</div></section>}
      {error && <p className="form-error chat-error">{error}</p>}
      {consultation.status === "active" && <form className="composer" onSubmit={send}><textarea aria-label="Message" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={handleMessageKeyDown} placeholder="Write a response..." rows={2} /><button className="icon-button send-button" disabled={sending || !message.trim()} aria-label="Send message"><Send /></button></form>}
      {showVoiceSession && <VoiceConversation consultationId={consultation.public_id} onClose={() => setShowVoiceSession(false)} onMessage={onRefresh} />}
    </section>
  );
}

function PatientDetail({ patient, user, onBack }: { patient: Patient; user: User; onBack: () => void }) {
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const canManage = user.role === "admin" || user.role === "clinician";

  async function load() {
    try {
      const consultationResponse = await api.get<Consultation[]>(`/patients/${patient.public_id}/consultations`);
      setConsultations(consultationResponse.data);
      setSelectedId((current) => current ?? consultationResponse.data[0]?.public_id ?? null);
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  useEffect(() => { void load(); }, [patient.public_id]);

  async function startConsultation() {
    try {
      const { data } = await api.post<Consultation>(`/patients/${patient.public_id}/consultations`);
      setConsultations((current) => [data, ...current]);
      setSelectedId(data.public_id);
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  const selected = consultations.find((item) => item.public_id === selectedId) ?? null;
  const hasActive = consultations.some((item) => item.status === "active");

  return (
    <div className="patient-detail">
      <header className="patient-heading"><button className="icon-button mobile-back" onClick={onBack} aria-label="Back"><ArrowLeft /></button><div className="patient-avatar">{patient.first_name[0]}{patient.last_name[0]}</div><div><span className="eyebrow">Patient record</span><h1>{patient.first_name} {patient.last_name}</h1><p>DOB {formatDate(patient.date_of_birth)} · ID {patient.public_id.slice(0, 8).toUpperCase()}</p></div><button className="primary start-button" onClick={startConsultation} disabled={hasActive} title={hasActive ? "Complete the active consultation before starting a new one" : "Start a new consultation"}><Plus size={18} />New consultation</button></header>
      {error && <p className="form-error page-error">{error}</p>}
      <div className="consultation-layout"><aside className="visit-list">{consultations.length === 0 && <p className="empty-copy">No consultations recorded.</p>}{consultations.map((item, index) => <button key={item.public_id} className={selectedId === item.public_id ? "selected" : ""} onClick={() => setSelectedId(item.public_id)}><span className="visit-index">{String(consultations.length - index).padStart(2, "0")}</span><span><strong>{formatDate(item.started_at)}</strong><small>{item.status}{item.requires_review ? " · review" : ""}</small></span><ChevronRight size={17} /></button>)}</aside><div className="workspace-container">{selected ? <ConsultationWorkspace consultation={selected} canManage={canManage} canDownloadReport={user.role === "patient"} onRefresh={load} /> : <div className="empty-state"><MessageSquare /><h2>No consultation selected</h2></div>}</div></div>
    </div>
  );
}

function SafetyQueue() {
  const [events, setEvents] = useState<SafetyEvent[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try { setEvents((await api.get<SafetyEvent[]>("/safety-events")).data); }
    catch (requestError) { setError(errorMessage(requestError)); }
  }
  useEffect(() => { void load(); }, []);
  async function update(id: number, status: "acknowledged" | "resolved") {
    await api.patch(`/safety-events/${id}`, { status });
    await load();
  }

  return <section className="safety-page"><header><div><span className="eyebrow">Clinical oversight</span><h1>Safety queue</h1><p>Responses requiring documented clinician review.</p></div><span className="alert-count">{events.filter((event) => event.status === "open").length}<small>open</small></span></header>{error && <p className="form-error">{error}</p>}<div className="safety-list">{events.map((event) => <article key={event.id} className={`safety-item ${event.status}`}><div className="safety-icon"><AlertTriangle /></div><div><div className="safety-meta"><span className={`status ${event.status}`}>{event.status}</span><span>{formatDate(event.created_at)}</span></div><h3>{event.reason}</h3><p>{event.action_taken}</p></div><div className="safety-actions">{event.status === "open" && <button className="secondary" onClick={() => update(event.id, "acknowledged")}>Acknowledge</button>}{event.status !== "resolved" && <button className="ghost" onClick={() => update(event.id, "resolved")}><Check size={17} />Resolve</button>}</div></article>)}{events.length === 0 && <div className="empty-state"><ShieldCheck /><h3>No safety events</h3></div>}</div></section>;
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [user, setUser] = useState<User | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selected, setSelected] = useState<Patient | null>(null);
  const [view, setView] = useState<"patients" | "safety">("patients");
  const [showNew, setShowNew] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.get<User>("/auth/me"), api.get<Patient[]>("/patients")])
      .then(([userResponse, patientResponse]) => { setUser(userResponse.data); setPatients(patientResponse.data); if (userResponse.data.role === "patient") setSelected(patientResponse.data[0] ?? null); })
      .catch((requestError) => {
        if (isUnauthorized(requestError)) onLogout();
        else setError(errorMessage(requestError));
      });
  }, [onLogout]);

  if (!user) return <div className="app-loading"><Activity /><span>{error || "Loading patient records..."}</span></div>;
  const canManage = user.role !== "patient";

  return (
    <main className={`app-shell ${view !== "patients" ? "wide-mode" : ""}`}>
      <aside className="app-nav"><div className="nav-brand"><div className="brand-mark"><Activity /></div><strong>Continuum</strong></div><nav><button className={view === "patients" ? "active" : ""} onClick={() => setView("patients")}><Users /><span>Patients</span></button>{canManage && <button className={view === "safety" ? "active" : ""} onClick={() => { setView("safety"); setSelected(null); }}><AlertTriangle /><span>Safety</span></button>}</nav><div className="nav-user"><div><UserRound /><span><strong>{user.username}</strong><small>{user.role}</small></span></div><button className="icon-button" onClick={onLogout} aria-label="Sign out"><LogOut /></button></div></aside>
      {view === "patients" && <aside className={`patient-sidebar ${selected ? "mobile-hidden" : ""}`}><header><div><span className="eyebrow">Registry</span><h2>Patients</h2></div>{canManage && <button className="icon-button add-button" onClick={() => setShowNew(true)} aria-label="Add patient"><Plus /></button>}</header><div className="patient-list">{patients.map((patient) => <button key={patient.public_id} className={selected?.public_id === patient.public_id ? "selected" : ""} onClick={() => setSelected(patient)}><span className="mini-avatar">{patient.first_name[0]}{patient.last_name[0]}</span><span><strong>{patient.first_name} {patient.last_name}</strong><small>{patient.public_id.slice(0, 8).toUpperCase()}</small></span><ChevronRight /></button>)}</div></aside>}
      <section className="main-content">{view === "safety" ? <SafetyQueue /> : selected ? <PatientDetail patient={selected} user={user} onBack={() => setSelected(null)} /> : <div className="welcome-state"><div><span className="eyebrow">Clinical workspace</span><h1>Select a patient record</h1><p>Review consultations, symptoms, safety concerns, and follow-up activity.</p></div><div className="welcome-grid"><span><MessageSquare />Conversation history</span><span><AudioLines />Voice follow-up</span><span><Download />Symptom reports</span><span><ShieldCheck />Safety review</span></div></div>}</section>
      {showNew && <NewPatientDialog onClose={() => setShowNew(false)} onCreated={(patient) => { setPatients((current) => [...current, patient].sort((a, b) => a.last_name.localeCompare(b.last_name))); setSelected(patient); setShowNew(false); }} />}
    </main>
  );
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(Boolean(localStorage.getItem(TOKEN_KEY)));
  function logout() { localStorage.removeItem(TOKEN_KEY); setAuthenticated(false); }
  return authenticated ? <Dashboard onLogout={logout} /> : <Login onAuthenticated={() => setAuthenticated(true)} />;
}