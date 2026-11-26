import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import {
  Activity,
  AudioLines,
  AlertTriangle,
  ArrowLeft,
  Check,
  ChevronRight,
  Download,
  Eye,
  FileText,
  House,
  LogOut,
  MessageSquare,
  PhoneOff,
  Plus,
  Search,
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
  VoiceRecording,
} from "./types";

const TOKEN_KEY = "continuum-token";
const NAVIGATION_KEY = "continuum-navigation";

type DashboardView = "home" | "patients" | "reports" | "safety";
type PatientStage = "overview" | "summaries" | "conversation";
type PatientCommunicationMode = "choose" | "message" | "voice" | "summary" | "recordings";
type PatientConsultationView = "landing" | "history";
type NavigationState = {
  view?: DashboardView;
  patientId?: string | null;
  patientStage?: PatientStage;
  consultationId?: string | null;
};

function getNavigationState(): NavigationState {
  try {
    return JSON.parse(localStorage.getItem(NAVIGATION_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function updateNavigationState(update: Partial<NavigationState>) {
  localStorage.setItem(NAVIGATION_KEY, JSON.stringify({ ...getNavigationState(), ...update }));
}

function formatDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value))
    : "Not recorded";
}

function formatMessageTime(value: string) {
  const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function downloadConsultationReport(consultationId: string) {
  const response = await api.get(
    `/consultations/${consultationId}/report.pdf`,
    { responseType: "blob" },
  );
  const disposition = response.headers["content-disposition"] as string | undefined;
  const filename = disposition?.match(/filename="?([^";]+)"?/)?.[1]
    ?? `patient-followup-report-${consultationId.slice(0, 8)}.pdf`;
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
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

function VoiceConversation({ consultationId, initialMessages, onClose, onMessage, embedded = false }: { consultationId: string; initialMessages: Message[]; onClose: () => void; onMessage: () => void; embedded?: boolean }) {
  const [status, setStatus] = useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  const [recordingStatus, setRecordingStatus] = useState<"starting" | "recording" | "saving" | "saved" | "error">("starting");
  const [patientText, setPatientText] = useState("");
  const [voiceTurns, setVoiceTurns] = useState<Array<{ id: number; role: "patient" | "agent"; content: string }>>(() => initialMessages
    .filter((item) => item.role === "patient" || item.role === "agent")
    .sort((first, second) => first.sequence_number - second.sequence_number)
    .map((item) => ({ id: item.id, role: item.role as "patient" | "agent", content: item.content })));
  const [error, setError] = useState("");
  const speechRecognition = useRef<BrowserSpeechRecognition | null>(null);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const mediaStream = useRef<MediaStream | null>(null);
  const audioChunks = useRef<Blob[]>([]);
  const closeAfterSave = useRef(false);
  const conversationActive = useRef(true);
  const listenRef = useRef<() => void>(() => undefined);
  const voiceLog = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const log = voiceLog.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [patientText, voiceTurns]);

  useEffect(() => {
    const startTimer = window.setTimeout(() => listenRef.current(), 0);
    void startRecording();
    return () => {
      window.clearTimeout(startTimer);
      conversationActive.current = false;
      speechRecognition.current?.abort();
      window.speechSynthesis?.cancel();
      mediaStream.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || !("MediaRecorder" in window)) {
      setRecordingStatus("error");
      setError("Audio recording is not supported by this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStream.current = stream;
      const preferredType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = new MediaRecorder(stream, preferredType ? { mimeType: preferredType } : undefined);
      mediaRecorder.current = recorder;
      audioChunks.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunks.current.push(event.data);
      };
      recorder.onerror = () => {
        setRecordingStatus("error");
        setError("The audio recording could not continue.");
      };
      recorder.onstop = () => { void saveRecording(recorder.mimeType); };
      recorder.start(1000);
      setRecordingStatus("recording");
    } catch {
      setRecordingStatus("error");
      setError("Microphone permission is required to record this voice conversation.");
    }
  }

  async function saveRecording(mimeType: string) {
    setRecordingStatus("saving");
    try {
      const contentType = mimeType || "audio/webm";
      const extension = contentType.includes("mp4") ? "m4a" : contentType.includes("ogg") ? "ogg" : "webm";
      const recording = new Blob(audioChunks.current, { type: contentType });
      const form = new FormData();
      form.append("recording", recording, `voice-session.${extension}`);
      await api.post(`/consultations/${consultationId}/voice-recordings`, form);
      setRecordingStatus("saved");
      if (closeAfterSave.current) window.setTimeout(onClose, 450);
    } catch (requestError) {
      closeAfterSave.current = false;
      setRecordingStatus("error");
      setError(`The transcript was saved, but the audio upload failed: ${errorMessage(requestError)}`);
    } finally {
      mediaStream.current?.getTracks().forEach((track) => track.stop());
      mediaStream.current = null;
    }
  }

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
      console.warn("The spoken response could not be played.");
    };
    window.speechSynthesis.speak(speech);
  }

  async function sendSpokenMessage(transcript: string) {
    setPatientText("");
    setVoiceTurns((current) => [...current, { id: Date.now(), role: "patient", content: transcript }]);
    setStatus("thinking");
    try {
      const { data } = await api.post<Message[]>(`/consultations/${consultationId}/messages`, { content: transcript });
      const response = data.find((item) => item.role === "agent");
      if (!response) throw new Error("No voice response was returned");
      setVoiceTurns((current) => [...current, { id: Date.now() + 1, role: "agent", content: response.content }]);
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
      setError(denied ? "Microphone permission was not granted." : "");
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
    if (mediaRecorder.current?.state === "recording") {
      closeAfterSave.current = true;
      setRecordingStatus("saving");
      mediaRecorder.current.stop();
      return;
    }
    if (recordingStatus !== "saving") onClose();
  }

  const statusText = {
    idle: "Ready to listen",
    listening: "Listening...",
    thinking: "Preparing response...",
    speaking: "Agent is speaking...",
  }[status];

  return (
    <div className={embedded ? "voice-inline" : "modal-backdrop voice-backdrop"}>
      <section className="voice-session" role={embedded ? "region" : "dialog"} aria-modal={embedded ? undefined : true} aria-labelledby="voice-session-title">
        <header><div className="voice-brand"><AudioLines /><span><span className="eyebrow">Voice conversation</span><h2 id="voice-session-title">Follow-up call</h2></span></div><span className={`recording-state ${recordingStatus}`}><span />{recordingStatus === "starting" ? "Starting" : recordingStatus === "recording" ? "Recording" : recordingStatus === "saving" ? "Saving" : recordingStatus === "saved" ? "Saved" : "Audio error"}</span><button className="icon-button" onClick={close} aria-label="Close voice session"><X /></button></header>
        <div className={`voice-stage ${status}`}>
          <div className="voice-status"><div className="voice-activity" aria-hidden="true"><AudioLines /></div><div><span className="eyebrow">Live conversation</span><h3>{statusText}</h3></div></div>
          <div className="voice-conversation-log" ref={voiceLog} aria-live="polite">
            {voiceTurns.length === 0 && !patientText && <div className="voice-empty"><AudioLines /><p>Your conversation will appear here as you speak.</p></div>}
            {voiceTurns.map((turn) => <article key={turn.id} className={`voice-turn ${turn.role}`}><span>{turn.role === "patient" ? "You" : "Follow-up agent"}</span><p>{turn.content}</p></article>)}
            {patientText && <article className="voice-turn patient live"><span>You · speaking</span><p>{patientText}</p></article>}
          </div>
          {error && !error.startsWith("Speech could not be recognized") && <p className="form-error voice-error">{error}</p>}
        </div>
        <footer><button className="end-call" onClick={close} disabled={recordingStatus === "saving"}><PhoneOff />{recordingStatus === "saving" ? "Saving recording..." : "End voice session"}</button></footer>
      </section>
    </div>
  );
}

function ConsultationWorkspace({ consultation, canDownloadReport, readOnly = false, patientMode = false, patientChannel = "message", onRefresh, onVoiceSessionEnd }: { consultation: Consultation; canDownloadReport: boolean; readOnly?: boolean; patientMode?: boolean; patientChannel?: "message" | "voice"; onRefresh: () => void; onVoiceSessionEnd?: () => void }) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [showVoiceSession, setShowVoiceSession] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [completing, setCompleting] = useState(false);
  const messagesContainer = useRef<HTMLDivElement | null>(null);
  const voiceHistoryContainer = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setError("");
  }, [consultation.public_id, consultation.status]);

  useEffect(() => {
    const container = messagesContainer.current;
    if (container) container.scrollTop = container.scrollHeight;
    const voiceHistory = voiceHistoryContainer.current;
    if (voiceHistory) voiceHistory.scrollTop = voiceHistory.scrollHeight;
  }, [consultation.public_id, consultation.messages.length]);

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
    if (completing) return;
    setCompleting(true);
    setError("");
    try {
      await api.post(`/consultations/${consultation.public_id}/complete`);
      onRefresh();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setCompleting(false);
    }
  }

  async function downloadReport() {
    setDownloadingReport(true);
    setError("");
    try {
      await downloadConsultationReport(consultation.public_id);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDownloadingReport(false);
    }
  }

  const messageWorkspace = (
    <section className="consultation-workspace">
      <header className="workspace-header"><div><span className={`status ${consultation.status}`}>{consultation.status}</span><h2>{patientMode ? "Message communication" : "Consultation"}</h2><p>{formatDate(consultation.started_at)}</p></div>{consultation.requires_review && <span className="review-flag"><AlertTriangle size={16} />Review required</span>}<div className="header-actions">{canDownloadReport && consultation.status === "completed" && <button className="secondary" onClick={downloadReport} disabled={downloadingReport}><Download size={17} />{downloadingReport ? "Preparing..." : "Download PDF"}</button>}{!patientMode && !readOnly && consultation.status === "active" && <button className="voice-session-button" onClick={() => setShowVoiceSession(true)}><AudioLines size={17} />Voice session</button>}{!readOnly && consultation.status === "active" && <button className="ghost" onClick={complete} disabled={completing}><Check size={17} />{completing ? "Completing..." : "Complete"}</button>}</div></header>
      <div className="messages" ref={messagesContainer} aria-live="polite">{consultation.messages.sort((a, b) => a.sequence_number - b.sequence_number).map((item) => <article key={item.id} className={`message ${item.role}`}><div className="message-meta">{item.role === "agent" ? "Follow-up agent" : item.role}<span>{formatMessageTime(item.created_at)}</span></div><p>{item.content}</p>{item.flagged && <AlertTriangle className="message-alert" size={17} />}</article>)}</div>
      {error && <p className="form-error chat-error">{error}</p>}
      {!readOnly && consultation.status === "active" && <form className="composer" onSubmit={send}><textarea aria-label="Message" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={handleMessageKeyDown} placeholder="Write a response..." rows={2} /><button className="icon-button send-button" disabled={sending || !message.trim()} aria-label="Send message"><Send /></button></form>}
      {!patientMode && showVoiceSession && <VoiceConversation consultationId={consultation.public_id} initialMessages={consultation.messages} onClose={() => setShowVoiceSession(false)} onMessage={onRefresh} />}
    </section>
  );

  if (!patientMode) return messageWorkspace;

  if (patientChannel === "message") return messageWorkspace;

  return (
    <aside className="speech-workspace patient-speech-workspace">
      <header><div><span className="eyebrow">Hands-free</span><h2>Voice recording</h2></div>{consultation.status === "active" && <button className="ghost" onClick={complete} disabled={completing}><Check size={17} />{completing ? "Completing..." : "Complete"}</button>}</header>
      {consultation.status !== "active" ? <div className="speech-unavailable"><AudioLines /><h3>Recording unavailable</h3><p>Voice recording is available only during an active consultation.</p></div> : showVoiceSession ? <VoiceConversation embedded consultationId={consultation.public_id} initialMessages={consultation.messages} onClose={() => { setShowVoiceSession(false); onVoiceSessionEnd?.(); }} onMessage={onRefresh} /> : <div className="voice-history-ready"><div className="messages voice-history-messages" ref={voiceHistoryContainer}>{consultation.messages.sort((a, b) => a.sequence_number - b.sequence_number).map((item) => <article key={item.id} className={`message ${item.role}`}><div className="message-meta">{item.role === "agent" ? "Follow-up agent" : item.role}<span>{formatMessageTime(item.created_at)}</span></div><p>{item.content}</p></article>)}</div><footer><p>Your microphone audio and transcript will be saved to this consultation.</p><button className="voice-session-button" onClick={() => setShowVoiceSession(true)}><AudioLines size={17} />Start recording</button></footer></div>}
    </aside>
  );
}

function PatientCommunicationChoice({ consultation, onSelect }: { consultation: Consultation; onSelect: (mode: "message" | "voice" | "summary" | "recordings") => void }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const active = consultation.status === "active";

  async function downloadReport() {
    setDownloading(true);
    setError("");
    try {
      await downloadConsultationReport(consultation.public_id);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="communication-choice">
      <header><div><span className={`status ${consultation.status}`}>{consultation.status}</span><span>{formatDate(consultation.started_at)}</span></div><h2>Choose how to continue</h2><p>Use text messaging or start a recorded voice conversation.</p></header>
      <div className="communication-options">
        <button onClick={() => onSelect("message")}><span className="communication-option-icon"><MessageSquare /></span><span><strong>{active ? "Start message" : "View messages"}</strong><small>{active ? "Type a response to the follow-up agent" : "Review this consultation transcript"}</small></span><ChevronRight /></button>
        {active && <button onClick={() => onSelect("voice")}><span className="communication-option-icon voice"><AudioLines /></span><span><strong>Start recording</strong><small>Talk with the agent and save the recording</small></span><ChevronRight /></button>}
        {consultation.status === "completed" && <button onClick={() => onSelect("summary")}><span className="communication-option-icon summary"><FileText /></span><span><strong>View consultation summary</strong><small>Review the completed conversation overview</small></span><ChevronRight /></button>}
        {consultation.status === "completed" && <button onClick={() => void downloadReport()} disabled={downloading}><span className="communication-option-icon report"><Download /></span><span><strong>Download report</strong><small>{downloading ? "Preparing your PDF..." : "Download this consultation as a PDF"}</small></span><ChevronRight /></button>}
      </div>
      {error && <p className="form-error communication-choice-error">{error}</p>}
      {active && <footer><ShieldCheck size={17} />Voice audio and transcripts are saved to this consultation.</footer>}
    </section>
  );
}

function PatientVoiceRecordings({ consultation }: { consultation: Consultation }) {
  const [recordings, setRecordings] = useState<VoiceRecording[]>([]);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const audioUrlRef = useRef<string | null>(null);

  useEffect(() => {
    api.get<VoiceRecording[]>(`/consultations/${consultation.public_id}/voice-recordings`)
      .then(({ data }) => setRecordings(data))
      .catch((requestError) => setError(errorMessage(requestError)));
    return () => { if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current); };
  }, [consultation.public_id]);

  async function playRecording(recording: VoiceRecording) {
    setPlayingId(recording.public_id);
    setError("");
    try {
      const response = await api.get(`/voice-recordings/${recording.public_id}`, { responseType: "blob" });
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
      const url = URL.createObjectURL(response.data);
      audioUrlRef.current = url;
      setAudioUrl(url);
    } catch (requestError) {
      setPlayingId(null);
      setError(errorMessage(requestError));
    }
  }

  return (
    <section className="voice-recordings-view">
      <header><span className="eyebrow">Saved audio</span><h2>Voice recordings</h2></header>
      {error && <p className="form-error">{error}</p>}
      <div className="voice-recording-list">{recordings.map((recording, index) => <article key={recording.public_id}><span className="recording-index">{String(recordings.length - index).padStart(2, "0")}</span><div><strong>Voice session</strong><small>{formatDate(recording.created_at)} · {(recording.byte_size / 1024).toFixed(1)} KB</small></div><button className="secondary" onClick={() => void playRecording(recording)}><AudioLines size={17} />Play recording</button>{playingId === recording.public_id && audioUrl && <audio controls autoPlay src={audioUrl} onEnded={() => setPlayingId(null)} />}</article>)}</div>
    </section>
  );
}

function PatientConsultationSummary({ consultation }: { consultation: Consultation }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Summary>(`/consultations/${consultation.public_id}/summary`)
      .then(({ data }) => setSummary(data))
      .catch((requestError) => setError(errorMessage(requestError)));
  }, [consultation.public_id]);

  return (
    <section className="patient-consultation-summary">
      <header><div><span className={`status ${consultation.status}`}>{consultation.status}</span><span>{formatDate(consultation.started_at)}</span></div><h2>Consultation summary</h2></header>
      {error ? <p className="form-error">{error}</p> : summary ? <div className="patient-summary-content"><span className="eyebrow">Conversation overview</span><p>{summary.content}</p></div> : <div className="loading-block">Loading summary...</div>}
    </section>
  );
}

function PatientConsultationLanding({ consultationCount, hasActive, onStart, onViewHistory }: { consultationCount: number; hasActive: boolean; onStart: () => void; onViewHistory: () => void }) {
  return (
    <section className="consultation-entry">
      <header><span className="eyebrow">Consultation</span><h2>How would you like to continue?</h2></header>
      <div className="consultation-entry-options">
        <button onClick={onStart} disabled={hasActive}><span className="communication-option-icon"><Plus /></span><span><strong>Start new consultation</strong><small>{hasActive ? "Complete your active consultation first" : "Begin a new conversation with the follow-up agent"}</small></span><ChevronRight /></button>
        <button onClick={onViewHistory} disabled={consultationCount === 0}><span className="communication-option-icon summary"><MessageSquare /></span><span><strong>View previous consultations</strong><small>{consultationCount === 0 ? "No consultations available" : `${consultationCount} consultation${consultationCount === 1 ? "" : "s"} available`}</small></span><ChevronRight /></button>
      </div>
      {hasActive && <p><span className="status open">Active</span>Select previous consultations to continue your active conversation.</p>}
    </section>
  );
}

function ConsultationSummaryPanel({ consultation, summary, onViewConversation }: { consultation: Consultation; summary: Summary | undefined; onViewConversation: () => void }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  async function downloadReport() {
    setDownloading(true);
    setError("");
    try {
      await downloadConsultationReport(consultation.public_id);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="consultation-summary-panel">
      <header className="workspace-header"><div><span className={`status ${consultation.status}`}>{consultation.status}</span><h2>Consultation</h2><p>{formatDate(consultation.started_at)}</p></div>{consultation.requires_review && <span className="review-flag"><AlertTriangle size={16} />Review required</span>}</header>
      <div className="consultation-summary-body">
        <section><span className="eyebrow">Consultation summary</span><h3>Conversation overview</h3><p>{summary?.content ?? (consultation.status === "active" ? "This consultation is still active. Its summary will be available after completion." : "No summary is available for this consultation.")}</p></section>
        <section className="report-row"><div><span className="eyebrow">Report</span><h3>Patient follow-up report</h3><p>{consultation.status === "completed" ? "Download the complete consultation report as a PDF." : "The PDF report will be available after the consultation is completed."}</p></div>{consultation.status === "completed" && <button className="secondary" onClick={() => void downloadReport()} disabled={downloading}><Download size={17} />{downloading ? "Preparing..." : "Download PDF"}</button>}</section>
        {error && <p className="form-error">{error}</p>}
      </div>
      <footer className="consultation-summary-actions"><span>{consultation.messages.length} messages</span><button className="primary" onClick={onViewConversation}><Eye size={17} />View conversation</button></footer>
    </section>
  );
}

function PatientDetail({ patient, user, onBack, initialConsultationId }: { patient: Patient; user: User; onBack: () => void; initialConsultationId?: string | null }) {
  const canManage = user.role === "admin" || user.role === "clinician";
  const savedNavigation = getNavigationState();
  const restoresPatient = savedNavigation.patientId === patient.public_id;
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(initialConsultationId === undefined ? restoresPatient ? savedNavigation.consultationId ?? null : null : initialConsultationId);
  const [summaries, setSummaries] = useState<Record<string, Summary>>({});
  const [stage, setStage] = useState<PatientStage>(restoresPatient && savedNavigation.patientStage ? savedNavigation.patientStage : canManage ? "overview" : "conversation");
  const [communicationMode, setCommunicationMode] = useState<PatientCommunicationMode>("choose");
  const [patientConsultationView, setPatientConsultationView] = useState<PatientConsultationView>(initialConsultationId ? "history" : "landing");
  const [loadingSummaries, setLoadingSummaries] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const consultationResponse = await api.get<Consultation[]>(`/patients/${patient.public_id}/consultations`);
      setConsultations(consultationResponse.data);
      setSelectedId((current) => consultationResponse.data.some((item) => item.public_id === current) ? current : canManage ? consultationResponse.data[0]?.public_id ?? null : null);
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  useEffect(() => { void load(); }, [patient.public_id]);

  useEffect(() => {
    const navigation = getNavigationState();
    const restore = navigation.patientId === patient.public_id;
    setStage(restore && navigation.patientStage ? navigation.patientStage : canManage ? "overview" : "conversation");
    setCommunicationMode("choose");
    setPatientConsultationView(initialConsultationId ? "history" : "landing");
    setSummaries({});
    setSelectedId(canManage ? restore ? navigation.consultationId ?? null : null : initialConsultationId ?? null);
  }, [patient.public_id, canManage, initialConsultationId]);

  async function startConsultation() {
    try {
      const { data } = await api.post<Consultation>(`/patients/${patient.public_id}/consultations`);
      setConsultations((current) => [data, ...current]);
      setSelectedId(data.public_id);
      setCommunicationMode("choose");
      setPatientConsultationView("history");
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  const selected = consultations.find((item) => item.public_id === selectedId) ?? null;
  const hasActive = consultations.some((item) => item.status === "active");
  const orderedConsultations = [...consultations].sort(
    (first, second) => new Date(first.started_at).getTime() - new Date(second.started_at).getTime(),
  );

  async function loadSummaries() {
    setLoadingSummaries(true);
    setError("");
    const completed = orderedConsultations.filter((item) => item.status === "completed");
    try {
      const responses = await Promise.all(
        completed.map((item) => api.get<Summary>(`/consultations/${item.public_id}/summary`)),
      );
      setSummaries(Object.fromEntries(completed.map((item, index) => [item.public_id, responses[index].data])));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setLoadingSummaries(false);
    }
  }

  useEffect(() => {
    if (canManage && stage === "summaries" && consultations.length > 0) void loadSummaries();
  }, [canManage, consultations, stage]);

  function changeStage(nextStage: PatientStage) {
    setStage(nextStage);
    updateNavigationState({ patientId: patient.public_id, patientStage: nextStage });
  }

  function selectConsultation(consultationId: string) {
    setSelectedId(consultationId);
    setCommunicationMode("choose");
    updateNavigationState({ patientId: patient.public_id, consultationId });
  }

  function viewSummaries() {
    setSelectedId(null);
    updateNavigationState({ patientId: patient.public_id, patientStage: "summaries", consultationId: null });
    setStage("summaries");
  }

  function viewConversation(consultationId: string) {
    setSelectedId(consultationId);
    updateNavigationState({ patientId: patient.public_id, patientStage: "conversation", consultationId });
    setStage("conversation");
  }

  if (canManage && stage === "overview") {
    return (
      <div className="patient-detail patient-overview">
        <header className="patient-heading"><button className="icon-button mobile-back" onClick={onBack} aria-label="Back"><ArrowLeft /></button><div className="patient-avatar">{patient.first_name[0]}{patient.last_name[0]}</div><div><span className="eyebrow">Patient details</span><h1>{patient.first_name} {patient.last_name}</h1><p>Patient ID {patient.public_id.slice(0, 8).toUpperCase()}</p></div></header>
        <section className="patient-profile">
          <div className="profile-field"><span>Full name</span><strong>{patient.first_name} {patient.last_name}</strong></div>
          <div className="profile-field"><span>Date of birth</span><strong>{formatDate(patient.date_of_birth)}</strong></div>
          <div className="profile-field"><span>Record status</span><strong>{patient.is_active ? "Active" : "Inactive"}</strong></div>
          <div className="profile-field"><span>Consultations</span><strong>{consultations.length}</strong></div>
          <div className="profile-actions"><button className="primary" onClick={() => void viewSummaries()}><FileText size={18} />View consultations</button></div>
        </section>
        {error && <p className="form-error page-error">{error}</p>}
      </div>
    );
  }

  if (canManage && stage === "summaries") {
    return (
      <div className="patient-detail summary-page">
        <header className="subpage-heading"><button className="icon-button" onClick={() => changeStage("overview")} aria-label="Back to patient details"><ArrowLeft /></button><div><span className="eyebrow">{patient.first_name} {patient.last_name}</span><h1>Consultations</h1><p>Select a date to review its summary, report, and conversation.</p></div></header>
        {error && <p className="form-error page-error">{error}</p>}
        {loadingSummaries ? <div className="loading-block">Loading consultations...</div> : <div className="consultation-layout clinician-consultations"><aside className="visit-list">{orderedConsultations.length === 0 && <p className="empty-copy">No consultations recorded.</p>}{orderedConsultations.map((item, index) => <button key={item.public_id} className={selectedId === item.public_id ? "selected" : ""} onClick={() => selectConsultation(item.public_id)}><span className="visit-index">{String(index + 1).padStart(2, "0")}</span><span><strong>{formatDate(item.started_at)}</strong><small>{item.status}{item.requires_review ? " · review" : ""}</small></span><ChevronRight size={17} /></button>)}</aside><div className="workspace-container">{selected ? <ConsultationSummaryPanel consultation={selected} summary={summaries[selected.public_id]} onViewConversation={() => viewConversation(selected.public_id)} /> : <section className="consultation-start-state"><div className="communication-option-icon"><FileText /></div><span className="eyebrow">Consultation history</span><h2>Select a date to continue</h2><p>Choose a consultation date to review its summary, report, and conversation.</p></section>}</div></div>}
      </div>
    );
  }

  return (
    <div className="patient-detail">
      <header className="patient-heading">{canManage ? <button className="icon-button" onClick={() => changeStage("summaries")} aria-label="Back to consultation summary"><ArrowLeft /></button> : <button className="icon-button mobile-back" onClick={onBack} aria-label="Back"><ArrowLeft /></button>}<div className="patient-avatar">{patient.first_name[0]}{patient.last_name[0]}</div><div><span className="eyebrow">{canManage ? "Conversation history" : "Patient record"}</span><h1>{patient.first_name} {patient.last_name}</h1><p>DOB {formatDate(patient.date_of_birth)} · ID {patient.public_id.slice(0, 8).toUpperCase()}</p></div>{!canManage && patientConsultationView === "history" && <button className="ghost start-button" onClick={() => { setSelectedId(null); setCommunicationMode("choose"); setPatientConsultationView("landing"); }}><ArrowLeft size={17} />Consultation options</button>}</header>
      {error && <p className="form-error page-error">{error}</p>}
      {!canManage && patientConsultationView === "landing" ? <PatientConsultationLanding consultationCount={consultations.length} hasActive={hasActive} onStart={() => void startConsultation()} onViewHistory={() => { setSelectedId(null); setCommunicationMode("choose"); setPatientConsultationView("history"); }} /> : <div className={`consultation-layout ${!canManage ? "patient-consultations" : ""}`}><aside className="visit-list">{consultations.length === 0 && <p className="empty-copy">No consultations recorded.</p>}{orderedConsultations.map((item, index) => <button key={item.public_id} className={selectedId === item.public_id ? "selected" : ""} onClick={() => { selectConsultation(item.public_id); if (canManage) changeStage("summaries"); }}><span className="visit-index">{String(index + 1).padStart(2, "0")}</span><span><strong>{formatDate(item.started_at)}</strong><small>{item.status}{item.requires_review ? " · review" : ""}</small></span><ChevronRight size={17} /></button>)}</aside><div className="workspace-container">{selected ? canManage ? <ConsultationWorkspace consultation={selected} canDownloadReport={false} readOnly onRefresh={load} /> : communicationMode === "choose" ? <PatientCommunicationChoice consultation={selected} onSelect={setCommunicationMode} /> : <div className="patient-channel-view"><button className="ghost channel-back" onClick={() => setCommunicationMode("choose")}><ArrowLeft size={17} />Communication options</button>{communicationMode === "summary" ? <PatientConsultationSummary consultation={selected} /> : communicationMode === "recordings" ? <PatientVoiceRecordings consultation={selected} /> : <ConsultationWorkspace consultation={selected} canDownloadReport patientMode patientChannel={communicationMode} onRefresh={load} onVoiceSessionEnd={() => setCommunicationMode("choose")} />}</div> : canManage ? <div className="empty-state"><MessageSquare /><h2>No consultation selected</h2></div> : <section className="consultation-start-state"><div className="communication-option-icon"><MessageSquare /></div><span className="eyebrow">Consultation history</span><h2>Select a date to continue</h2><p>Choose a consultation date to view its messages and communication options.</p></section>}</div></div>}
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

function ClinicianHome({ patientCount, onViewPatients }: { patientCount: number; onViewPatients: () => void }) {
  return (
    <section className="home-page">
      <header><span className="eyebrow">Clinical workspace</span><h1>Home</h1><p>Access patient records, consultation summaries, and conversation history.</p></header>
      <button className="home-action" onClick={onViewPatients}><span className="home-action-icon"><Users /></span><span><strong>View patients</strong><small>{patientCount} patient {patientCount === 1 ? "record" : "records"}</small></span><ChevronRight /></button>
    </section>
  );
}

function PatientHome({ patient, onOpenConsultation, onViewReports }: { patient: Patient | undefined; onOpenConsultation: (consultationId?: string) => void; onViewReports: () => void }) {
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!patient) return;
    api.get<Consultation[]>(`/patients/${patient.public_id}/consultations`)
      .then(({ data }) => setConsultations(data))
      .catch((requestError) => setError(errorMessage(requestError)));
  }, [patient]);

  async function addConsultation() {
    if (!patient) return;
    setStarting(true);
    setError("");
    try {
      const { data } = await api.post<Consultation>(`/patients/${patient.public_id}/consultations`);
      onOpenConsultation(data.public_id);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setStarting(false);
    }
  }

  const activeConsultation = consultations.find((item) => item.status === "active");
  const latestConsultation = consultations[0];
  const latestReport = consultations.find((item) => item.status === "completed");

  return (
    <section className="home-page patient-home">
      <header><span className="eyebrow">Patient portal</span><h1>{patient ? `Welcome, ${patient.first_name}` : "Welcome"}</h1><p>Continue your follow-up conversations and review your consultation history.</p></header>
      {error && <p className="form-error patient-home-error">{error}</p>}
      <div className="patient-home-actions">
        <button className="home-action" onClick={() => void addConsultation()} disabled={!patient || Boolean(activeConsultation) || starting}><span className="home-action-icon"><Plus /></span><span><strong>Add consultation</strong><small>{activeConsultation ? "Complete your active consultation first" : starting ? "Starting consultation..." : "Start a new follow-up"}</small></span><ChevronRight /></button>
        <button className="home-action" onClick={() => onOpenConsultation()} disabled={!latestConsultation}><span className="home-action-icon"><MessageSquare /></span><span><strong>View consultation</strong><small>Open consultation options</small></span><ChevronRight /></button>
        <button className="home-action" onClick={onViewReports} disabled={!latestReport}><span className="home-action-icon"><FileText /></span><span><strong>View consultation reports</strong><small>{latestReport ? "Open all completed PDF reports" : "No completed reports yet"}</small></span><ChevronRight /></button>
      </div>
    </section>
  );
}

function PatientReports({ patient, onBack }: { patient: Patient | undefined; onBack: () => void }) {
  const [consultations, setConsultations] = useState<Consultation[]>([]);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!patient) return;
    api.get<Consultation[]>(`/patients/${patient.public_id}/consultations`)
      .then(({ data }) => setConsultations(data.filter((item) => item.status === "completed").reverse()))
      .catch((requestError) => setError(errorMessage(requestError)));
  }, [patient]);

  async function downloadReport(consultation: Consultation) {
    setDownloadingId(consultation.public_id);
    setError("");
    try {
      await downloadConsultationReport(consultation.public_id);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <section className="patient-reports-page">
      <header><button className="icon-button" onClick={onBack} aria-label="Back to home"><ArrowLeft /></button><div><span className="eyebrow">Patient reports</span><h1>Consultation reports</h1></div></header>
      {error && <p className="form-error">{error}</p>}
      <div className="patient-report-list">
        {consultations.map((consultation, index) => <article key={consultation.public_id}><span className="report-number">{String(index + 1).padStart(2, "0")}</span><div><strong>Consultation report</strong><small>{formatDate(consultation.started_at)}</small></div><button className="secondary" onClick={() => void downloadReport(consultation)} disabled={downloadingId === consultation.public_id}><Download size={17} />{downloadingId === consultation.public_id ? "Preparing..." : "Download report"}</button></article>)}
        {consultations.length === 0 && <div className="empty-state"><FileText /><h2>No completed reports</h2></div>}
      </div>
    </section>
  );
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [user, setUser] = useState<User | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selected, setSelected] = useState<Patient | null>(null);
  const [view, setView] = useState<DashboardView>(() => getNavigationState().view ?? "home");
  const [showNew, setShowNew] = useState(false);
  const [patientSearch, setPatientSearch] = useState("");
  const [patientConsultationTarget, setPatientConsultationTarget] = useState<{ id: string | null; key: number }>({ id: null, key: 0 });
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.get<User>("/auth/me"), api.get<Patient[]>("/patients")])
      .then(([userResponse, patientResponse]) => {
        setUser(userResponse.data);
        setPatients(patientResponse.data);
        if (userResponse.data.role === "patient") {
          setView("home");
          setSelected(patientResponse.data[0] ?? null);
          updateNavigationState({ view: "home", patientId: patientResponse.data[0]?.public_id ?? null });
          return;
        }
        const patientId = getNavigationState().patientId;
        setSelected(patientResponse.data.find((patient) => patient.public_id === patientId) ?? null);
      })
      .catch((requestError) => {
        if (isUnauthorized(requestError)) onLogout();
        else setError(errorMessage(requestError));
      });
  }, [onLogout]);

  if (!user) return <div className="app-loading"><Activity /><span>{error || "Loading patient records..."}</span></div>;
  const canManage = user.role !== "patient";
  const normalizedSearch = patientSearch.trim().toLowerCase();
  const visiblePatients = normalizedSearch
    ? patients.filter((patient) =>
      `${patient.first_name} ${patient.last_name} ${patient.public_id}`.toLowerCase().includes(normalizedSearch),
    )
    : patients;

  function changeView(nextView: DashboardView) {
    setView(nextView);
    updateNavigationState({ view: nextView });
    if (canManage && nextView !== "patients") setSelected(null);
  }

  function openPatientConsultations(consultationId?: string) {
    setSelected(patients[0] ?? null);
    setPatientConsultationTarget((current) => ({ id: consultationId ?? null, key: current.key + 1 }));
    updateNavigationState({
      patientId: patients[0]?.public_id ?? null,
      patientStage: "conversation",
      consultationId: consultationId ?? null,
    });
    changeView("patients");
  }

  function openPatientReports() {
    setView("reports");
    updateNavigationState({ view: "reports" });
  }

  function selectPatient(patient: Patient | null) {
    setSelected(patient);
    updateNavigationState({
      patientId: patient?.public_id ?? null,
      patientStage: patient ? "overview" : undefined,
      consultationId: null,
    });
  }

  return (
    <main className={`app-shell ${view !== "patients" ? "wide-mode" : ""} ${!canManage ? "patient-mode" : ""}`}>
      <aside className="app-nav"><div className="nav-brand"><div className="brand-mark"><Activity /></div><strong>Continuum</strong></div><nav>{canManage && <button className={view === "home" ? "active" : ""} onClick={() => changeView("home")}><House /><span>Home</span></button>}{!canManage && <><button className={view === "home" ? "active" : ""} onClick={() => changeView("home")}><House /><span>Home</span></button><button className={view === "patients" ? "active" : ""} onClick={() => openPatientConsultations()}><MessageSquare /><span>Consultation</span></button></>}{canManage && <button className={view === "safety" ? "active" : ""} onClick={() => changeView("safety")}><AlertTriangle /><span>Safety</span></button>}</nav><div className="nav-user"><div><UserRound /><span><strong>{user.username}</strong><small>{user.role}</small></span></div><button className="icon-button" onClick={onLogout} aria-label="Sign out"><LogOut /></button></div></aside>
      {canManage && view === "patients" && <aside className={`patient-sidebar ${selected ? "mobile-hidden" : ""}`}><header><div><span className="eyebrow">Registry</span><h2>Patients</h2></div><button className="icon-button add-button" onClick={() => setShowNew(true)} aria-label="Add patient"><Plus /></button></header><label className="patient-search"><span className="sr-only">Search patients</span><Search size={17} /><input type="search" value={patientSearch} onChange={(event) => setPatientSearch(event.target.value)} placeholder="Search patients" /></label><div className="patient-list">{visiblePatients.map((patient) => <button key={patient.public_id} className={selected?.public_id === patient.public_id ? "selected" : ""} onClick={() => selectPatient(patient)}><span className="mini-avatar">{patient.first_name[0]}{patient.last_name[0]}</span><span><strong>{patient.first_name} {patient.last_name}</strong><small>{patient.public_id.slice(0, 8).toUpperCase()}</small></span><ChevronRight /></button>)}{visiblePatients.length === 0 && <p className="patient-search-empty">No matching patients.</p>}</div></aside>}
      <section className="main-content">{view === "home" ? canManage ? <ClinicianHome patientCount={patients.length} onViewPatients={() => changeView("patients")} /> : <PatientHome patient={patients[0]} onOpenConsultation={openPatientConsultations} onViewReports={openPatientReports} /> : view === "reports" && !canManage ? <PatientReports patient={patients[0]} onBack={() => changeView("home")} /> : view === "safety" ? <SafetyQueue /> : selected ? <PatientDetail key={canManage ? selected.public_id : `${selected.public_id}-${patientConsultationTarget.key}`} patient={selected} user={user} onBack={() => selectPatient(null)} initialConsultationId={canManage ? undefined : patientConsultationTarget.id} /> : <div className="welcome-state"><div><span className="eyebrow">Patient registry</span><h1>Select a patient record</h1><p>Open a patient to view their details and conversation summaries.</p></div></div>}</section>
      {showNew && <NewPatientDialog onClose={() => setShowNew(false)} onCreated={(patient) => { setPatients((current) => [...current, patient].sort((a, b) => a.last_name.localeCompare(b.last_name))); selectPatient(patient); setShowNew(false); }} />}
    </main>
  );
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(Boolean(localStorage.getItem(TOKEN_KEY)));
  function logout() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(NAVIGATION_KEY); setAuthenticated(false); }
  return authenticated ? <Dashboard onLogout={logout} /> : <Login onAuthenticated={() => setAuthenticated(true)} />;
}