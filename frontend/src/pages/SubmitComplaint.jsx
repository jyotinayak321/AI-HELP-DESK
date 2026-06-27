import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { submitIntake } from "../api/tickets.api";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import ErrorMessage from "../components/ui/ErrorMessage";

const API_BASE = "http://127.0.0.1:8000";

function VoiceWidget({ onTranscript, onServiceNo }) {
  const [recording, setRecording] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [stage, setStage] = useState("idle");
  const [message, setMessage] = useState("");
  const [transcript, setTranscript] = useState("");
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);

  function speak(text) {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "hi-IN";
      u.rate = 0.85;
      u.volume = 1;
      window.speechSynthesis.speak(u);
    }
  }

  async function startSession() {
    try {
      const res = await fetch(`${API_BASE}/api/voice/start`, { method: "POST" });
      const data = await res.json();
      setSessionId(data.session_id);
      setStage("service_number");
      setMessage(data.message);
      speak(data.message);
    } catch (e) {
      setMessage("Session failed: " + e.message);
    }
  }

  async function startRecording() {
    try {
      window.speechSynthesis.cancel();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRef.current = new MediaRecorder(stream);
      chunksRef.current = [];
      mediaRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRef.current.onstop = handleAudioStop;
      mediaRef.current.start();
      setRecording(true);
      setMessage("Recording chal rahi hai... boliye!");
    } catch (e) {
      setMessage("Mic access nahi mila: " + e.message);
      speak("Mic access nahi mila");
    }
  }

  function stopRecording() {
    if (mediaRef.current && recording) {
      mediaRef.current.stop();
      mediaRef.current.stream.getTracks().forEach((t) => t.stop());
      setRecording(false);
      setMessage("Processing ho raha hai...");
    }
  }

  async function handleAudioStop() {
    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("audio", blob, "audio.webm");

    try {
      if (stage === "service_number") {
        const res = await fetch(`${API_BASE}/api/voice/service-number`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (data.is_valid) {
          setStage("confirm_service");
          onServiceNo(data.recognized_text);
          const msg = data.confirmation_message ||
            `Kya aapka service number ${data.recognized_text} hai?`;
          setMessage(msg);
          speak(msg);
        } else {
          const msg = data.message || "Service number samajh nahi aaya. Dobara boliye.";
          setMessage(msg);
          speak(msg);
        }
      } else if (stage === "complaint") {
        const res = await fetch(`${API_BASE}/api/voice/complaint`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        setTranscript(data.transcript);
        onTranscript(data.transcript);
        setStage("done");
        const msg = "Aapki complaint record ho gayi! Ab submit karein.";
        setMessage(msg);
        speak(msg);
      }
    } catch (e) {
      setMessage("Error: " + e.message);
    }
  }

  async function confirmServiceNo(confirmed) {
    try {
      await fetch(
        `${API_BASE}/api/voice/confirm?session_id=${sessionId}&confirmed=${confirmed}`,
        { method: "POST" }
      );
      if (confirmed) {
        setStage("complaint");
        const msg = "Dhanyavaad! Ab apni complaint boliye.";
        setMessage(msg);
        speak(msg);
      } else {
        setStage("service_number");
        const msg = "Theek hai. Dobara apna service number boliye.";
        setMessage(msg);
        speak(msg);
      }
    } catch (e) {
      setMessage("Error: " + e.message);
    }
  }

  if (stage === "idle") {
    return (
      <button onClick={startSession} style={voiceBtn}>
        🎙 Voice Se Complaint Shuru Karein
      </button>
    );
  }

  return (
    <div style={voiceBox}>
      <div style={{ fontWeight: 600, color: "#185FA5", marginBottom: "10px" }}>
        🎙 Voice Mode — {stageLabel(stage)}
      </div>

      {message && (
        <div style={msgBox}>
          🔊 {message}
        </div>
      )}

      {transcript && (
        <div style={transcriptBox}>
          <strong>Aapki Complaint:</strong> {transcript}
        </div>
      )}

      {(stage === "service_number" || stage === "complaint") && (
        <div style={{ marginTop: "12px" }}>
          <button
            onClick={recording ? stopRecording : startRecording}
            style={{
              ...voiceBtn,
              background: recording ? "#dc2626" : "#16a34a",
            }}
          >
            {recording ? "⏹ Stop — Band Karo" : "🎙 Start — Bolna Shuru Karein"}
          </button>
          {recording && (
            <div style={{ color: "#dc2626", textAlign: "center", marginTop: "6px", fontSize: "13px" }}>
              ● Recording chal rahi hai...
            </div>
          )}
        </div>
      )}

      {stage === "confirm_service" && (
        <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
          <button onClick={() => confirmServiceNo(true)} style={confirmBtn}>
            ✅ Haan, Sahi Hai
          </button>
          <button onClick={() => confirmServiceNo(false)} style={cancelBtn}>
            ❌ Nahi, Dobara Bolun
          </button>
        </div>
      )}

      {stage === "done" && (
        <div style={{ color: "#16a34a", fontWeight: 500, marginTop: "8px" }}>
          ✅ Voice complete! Neeche Submit karo.
        </div>
      )}
    </div>
  );
}

function stageLabel(stage) {
  const labels = {
    service_number: "Service Number Boliye",
    confirm_service: "Confirm Karein",
    complaint: "Complaint Boliye",
    done: "Complete!",
  };
  return labels[stage] || stage;
}

function SubmitComplaint() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    raw_text: "",
    complainant_service_no: "",
    complainant_name: "",
    complainant_unit: "",
    complainant_rank: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [voiceMode, setVoiceMode] = useState(false);

  function handleChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  function handleVoiceTranscript(text) {
    setForm((prev) => ({ ...prev, raw_text: text }));
  }

  function handleVoiceServiceNo(serviceNo) {
    setForm((prev) => ({ ...prev, complainant_service_no: serviceNo }));
  }

  async function handleSubmit() {
    if (!form.raw_text.trim() || !form.complainant_service_no.trim()) {
      setError("Complaint text aur service number dono required hain.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = {
        raw_text: form.raw_text.trim(),
        complainant_service_no: form.complainant_service_no.trim(),
        complainant_name: form.complainant_name.trim() || "",
        complainant_unit: form.complainant_unit.trim() || "",
        complainant_rank: form.complainant_rank.trim() || "",
        operator_id: "system",
      };
      const res = await submitIntake(payload);
      navigate("/classify", {
        state: { intakeResponse: res.data, originalForm: payload },
      });
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Intake failed");
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <LoadingSpinner text="AI classification chal rahi hai..." />;

  return (
    <div style={{ maxWidth: "640px", display: "flex", flexDirection: "column", gap: "16px" }}>
      {error && <ErrorMessage message={error} />}

      <div style={{ display: "flex", gap: "10px" }}>
        <button
          onClick={() => setVoiceMode(false)}
          style={{ ...modeBtn, background: !voiceMode ? "#185FA5" : "#e2e8f0", color: !voiceMode ? "#fff" : "#333" }}
        >
          ⌨️ Text Mode
        </button>
        <button
          onClick={() => setVoiceMode(true)}
          style={{ ...modeBtn, background: voiceMode ? "#185FA5" : "#e2e8f0", color: voiceMode ? "#fff" : "#333" }}
        >
          🎙 Voice Mode
        </button>
      </div>

      <div style={card}>
        <div style={cardTitle}>Complainant Details</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "14px" }}>
          <div>
            <label style={labelStyle}>Service Number *</label>
            <input name="complainant_service_no" value={form.complainant_service_no}
              onChange={handleChange} placeholder="e.g. 2893456P" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Name (optional)</label>
            <input name="complainant_name" value={form.complainant_name}
              onChange={handleChange} placeholder="Complainant name" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Unit (optional)</label>
            <input name="complainant_unit" value={form.complainant_unit}
              onChange={handleChange} placeholder="e.g. Admin Wing" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Rank (optional)</label>
            <input name="complainant_rank" value={form.complainant_rank}
              onChange={handleChange} placeholder="e.g. Sergeant" style={inputStyle} />
          </div>
        </div>
      </div>

      {voiceMode ? (
        <VoiceWidget
          onTranscript={handleVoiceTranscript}
          onServiceNo={handleVoiceServiceNo}
        />
      ) : (
        <div style={card}>
          <div style={cardTitle}>Complaint Description</div>
          <div style={{ fontSize: "12px", color: "#64748b", marginBottom: "12px" }}>
            English, Hindi, ya Hinglish
          </div>
          <textarea name="raw_text" value={form.raw_text} onChange={handleChange}
            placeholder="e.g. Mera HRMS login nahi ho raha..."
            rows={6} style={{ ...inputStyle, resize: "vertical", lineHeight: "1.6" }} />
        </div>
      )}

      <button onClick={handleSubmit}
        disabled={!form.raw_text.trim() || !form.complainant_service_no.trim()}
        style={{
          background: "#185FA5", color: "#fff", border: "none",
          borderRadius: "8px", padding: "10px 24px",
          fontSize: "14px", fontWeight: 500, cursor: "pointer",
          opacity: (!form.raw_text.trim() || !form.complainant_service_no.trim()) ? 0.5 : 1,
        }}>
        Classify Complaint →
      </button>
    </div>
  );
}

const card = { background: "#fff", border: "0.5px solid #e2e8f0", borderRadius: "12px", padding: "20px" };
const cardTitle = { fontWeight: 500, fontSize: "14px", marginBottom: "16px" };
const labelStyle = { display: "block", fontSize: "12px", color: "#64748b", marginBottom: "5px" };
const inputStyle = {
  width: "100%", padding: "9px 12px", fontSize: "13px",
  border: "0.5px solid #cbd5e1", borderRadius: "8px",
  outline: "none", fontFamily: "inherit", color: "#1a1a2e",
};
const voiceBtn = {
  background: "#185FA5", color: "#fff", border: "none",
  borderRadius: "8px", padding: "12px 20px",
  fontSize: "14px", fontWeight: 500, cursor: "pointer", width: "100%",
};
const voiceBox = {
  background: "#f0f7ff", border: "1px solid #bfdbfe",
  borderRadius: "12px", padding: "20px",
};
const msgBox = {
  background: "#fff", border: "1px solid #e2e8f0",
  borderRadius: "8px", padding: "10px 14px",
  fontSize: "13px", color: "#334155", marginBottom: "12px",
};
const transcriptBox = {
  background: "#f0fdf4", border: "1px solid #bbf7d0",
  borderRadius: "8px", padding: "10px 14px",
  fontSize: "13px", color: "#166534", marginBottom: "12px",
};
const confirmBtn = {
  background: "#16a34a", color: "#fff", border: "none",
  borderRadius: "8px", padding: "8px 16px", fontSize: "13px", cursor: "pointer",
};
const cancelBtn = {
  background: "#dc2626", color: "#fff", border: "none",
  borderRadius: "8px", padding: "8px 16px", fontSize: "13px", cursor: "pointer",
};
const modeBtn = {
  border: "none", borderRadius: "8px",
  padding: "8px 16px", fontSize: "13px",
  cursor: "pointer", fontWeight: 500,
};

export default SubmitComplaint;