import React, { useState, useRef, useEffect, useCallback } from "react";
import toast from "react-hot-toast";

function VoiceRecorder({ onRecordingComplete, onRecordingStart, isProcessing = false }) {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState("Starting microphone...");
  const isRecordingRef = useRef(false);
  const isStoppingRef = useRef(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const rafRef = useRef(null);
  const hasSpokeRef = useRef(false);
  const isFirstRender = useRef(true);

  const stopRecording = useCallback(() => {
    if (!isRecordingRef.current || isStoppingRef.current) return;
    isStoppingRef.current = true;
    clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = null;
    cancelAnimationFrame(rafRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setTimeout(() => {
      if (audioCtxRef.current) { audioCtxRef.current.close().catch(() => {}); audioCtxRef.current = null; }
      if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    }, 500);
    isRecordingRef.current = false;
    hasSpokeRef.current = false;
    setIsRecording(false);
    setStatus("Starting microphone...");
    setTimeout(() => { isStoppingRef.current = false; }, 600);
  }, []);

  const startSilenceDetection = useCallback((stream) => {
    try {
      const audioCtx = new AudioContext();
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      audioCtxRef.current = audioCtx;
      const data = new Uint8Array(analyser.frequencyBinCount);
      const check = () => {
        if (!isRecordingRef.current) return;
        analyser.getByteFrequencyData(data);
        const avg = data.reduce((a, b) => a + b, 0) / data.length;
        if (avg > 5) {
          hasSpokeRef.current = true;
          setStatus("Speaking detected...");
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        } else if (hasSpokeRef.current) {
          setStatus("Will auto-stop after silence...");
          if (!silenceTimerRef.current) {
            silenceTimerRef.current = setTimeout(() => { stopRecording(); }, 2500);
          }
        } else {
          setStatus("Listening for speech...");
        }
        rafRef.current = requestAnimationFrame(check);
      };
      rafRef.current = requestAnimationFrame(check);
    } catch (err) { console.error("Silence detection failed:", err); }
  }, [stopRecording]);

  const startRecording = useCallback(async () => {
    if (isRecordingRef.current) return;
    if (onRecordingStart) onRecordingStart();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mr;
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = () => {
        console.log("MediaRecorder stopped - sending to backend");
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        console.log("Blob size:", blob.size);
        onRecordingComplete(blob);
      };
      mr.start();
      isRecordingRef.current = true;
      hasSpokeRef.current = false;
      setIsRecording(true);
      setStatus("Listening for speech...");
      startSilenceDetection(stream);
      setTimeout(() => { if (isRecordingRef.current) stopRecording(); }, 30000);
    } catch (err) { console.error("Mic error:", err); toast.error("Microphone access denied."); }
  }, [onRecordingStart, onRecordingComplete, stopRecording, startSilenceDetection]);

  useEffect(() => {
    return () => {
      clearTimeout(silenceTimerRef.current);
      cancelAnimationFrame(rafRef.current);
      if (audioCtxRef.current) audioCtxRef.current.close().catch(() => {});
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  useEffect(() => {
    const t = setTimeout(() => { if (!isProcessing && !isRecordingRef.current) startRecording(); }, 2500);
    return () => clearTimeout(t);
  }, []); // eslint-disable-line

  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return; }
    if (!isProcessing && !isRecordingRef.current) {
      const t = setTimeout(() => { if (!isRecordingRef.current) startRecording(); }, 2000);
      return () => clearTimeout(t);
    }
  }, [isProcessing]); // eslint-disable-line

  return (
    <div style={{padding:"16px",border:"1px solid #e2e8f0",borderRadius:"12px",background:"#f8fafc",display:"flex",justifyContent:"center",alignItems:"center",minHeight:"80px"}}>
      {isProcessing ? (
        <div style={{display:"flex",alignItems:"center",gap:"12px"}}>
          <div style={{width:"20px",height:"20px",border:"3px solid #e2e8f0",borderTop:"3px solid #185FA5",borderRadius:"50%",animation:"spin 1s linear infinite"}}></div>
          <span style={{fontSize:"13px",color:"#64748b"}}>Processing audio...</span>
        </div>
      ) : isRecording ? (
        <div style={{display:"flex",alignItems:"center",background:"#fee2e2",padding:"8px 12px 8px 16px",borderRadius:"8px",border:"1px solid #fca5a5",width:"100%",justifyContent:"space-between"}}>
          <div style={{width:"10px",height:"10px",borderRadius:"50%",background:"#e24b4a",marginRight:"10px",animation:"pulse 1.5s infinite",flexShrink:0}}></div>
          <div style={{display:"flex",flexDirection:"column",flex:1}}>
            <span style={{fontSize:"13px",color:"#e24b4a",fontWeight:600}}>Recording...</span>
            <span style={{fontSize:"11px",color:"#64748b"}}>{status}</span>
          </div>
          <button onClick={stopRecording} style={{background:"#e24b4a",color:"white",border:"none",padding:"10px 20px",borderRadius:"8px",fontSize:"14px",fontWeight:500,cursor:"pointer"}}>Stop and Submit</button>
        </div>
      ) : (
        <div style={{display:"flex",alignItems:"center",gap:"12px"}}>
          <div style={{width:"20px",height:"20px",border:"3px solid #e2e8f0",borderTop:"3px solid #185FA5",borderRadius:"50%",animation:"spin 1s linear infinite"}}></div>
          <span style={{fontSize:"13px",color:"#64748b"}}>{status}</span>
        </div>
      )}
    </div>
  );
}

if (typeof document !== "undefined" && !document.getElementById("vr-kf")) {
  const s = document.createElement("style");
  s.id = "vr-kf";
  s.innerHTML = "@keyframes pulse{0%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(226,75,74,0.7)}70%{transform:scale(1);box-shadow:0 0 0 6px rgba(226,75,74,0)}100%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(226,75,74,0)}}@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}";
  document.head.appendChild(s);
}

export default VoiceRecorder;
