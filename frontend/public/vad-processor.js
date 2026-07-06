// vad-processor.js
// Runs inside the browser's dedicated audio thread.
// Captures raw microphone audio and converts it to 16-bit PCM
// chunks that our backend's Silero VAD model can understand.

class VADProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];

    // If there's no audio data yet (mic still initializing), skip this cycle
    if (!input || !input[0]) {
      return true;
    }

    const channelData = input[0]; // Float32Array of raw audio samples (-1.0 to 1.0)

    // Convert Float32 samples to 16-bit PCM integers
    const pcm16 = new Int16Array(channelData.length);
    for (let i = 0; i < channelData.length; i++) {
      const sample = Math.max(-1, Math.min(1, channelData[i]));
      pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }

    // Send this chunk of audio back to the main thread
    this.port.postMessage(pcm16.buffer, [pcm16.buffer]);

    // Returning true keeps this processor alive for the next audio chunk
    return true;
  }
}

registerProcessor('vad-processor', VADProcessor);