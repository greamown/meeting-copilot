import { useCallback, useEffect, useRef, useState } from "react";

export interface MicrophoneState {
  active: boolean;
  level: number;
  error: string | null;
  devices: MediaDeviceInfo[];
  start: (deviceId?: string, onChunk?: (chunk: ArrayBuffer) => void) => Promise<void>;
  stop: () => void;
}

function legacyProcessor(context: AudioContext, onChunk?: (chunk: ArrayBuffer) => void) {
  const processor = context.createScriptProcessor(4096, 1, 1);
  processor.onaudioprocess = event => {
    const input = event.inputBuffer.getChannelData(0);
    const ratio = context.sampleRate / 16000;
    const pcm = new Int16Array(Math.floor(input.length / ratio));
    for (let index = 0; index < pcm.length; index += 1) {
      // Average the source window (see pcm-processor.js): avoids aliasing artifacts.
      const from = Math.floor(index * ratio);
      const to = Math.min(input.length, Math.max(from + 1, Math.floor((index + 1) * ratio)));
      let sum = 0;
      for (let i = from; i < to; i += 1) sum += input[i] ?? 0;
      const sample = Math.max(-1, Math.min(1, sum / (to - from)));
      pcm[index] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    onChunk?.(pcm.buffer);
  };
  return processor;
}

async function workletProcessor(
  context: AudioContext,
  onChunk?: (chunk: ArrayBuffer) => void,
): Promise<AudioWorkletNode> {
  let timeout = 0;
  try {
    await Promise.race([
      context.audioWorklet.addModule("/pcm-processor.js"),
      new Promise<never>((_, reject) => {
        timeout = window.setTimeout(() => reject(new Error("AudioWorklet load timed out")), 3000);
      }),
    ]);
  } finally {
    window.clearTimeout(timeout);
  }
  const processor = new AudioWorkletNode(context, "pcm-processor");
  processor.port.onmessage = (event: MessageEvent<ArrayBuffer>) => onChunk?.(event.data);
  return processor;
}

export function useMicrophone(): MicrophoneState {
  const [active, setActive] = useState(false);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const resources = useRef<{
    stream: MediaStream;
    context: AudioContext;
    node: AudioNode;
    timer: number;
  } | null>(null);

  const stop = useCallback(() => {
    const item = resources.current;
    if (item) {
      item.stream.getTracks().forEach(track => track.stop());
      item.node.disconnect();
      void item.context.close();
      cancelAnimationFrame(item.timer);
      resources.current = null;
    }
    setActive(false);
    setLevel(0);
  }, []);

  const start = useCallback(async (
    deviceId?: string,
    onChunk?: (chunk: ArrayBuffer) => void,
  ) => {
    stop();
    setError(null);
    let stream: MediaStream | null = null;
    let context: AudioContext | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: deviceId ? { exact: deviceId } : undefined,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      context = new AudioContext();
      await context.resume();
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      let node: AudioNode;
      if (context.audioWorklet) {
        try {
          node = await workletProcessor(context, onChunk);
        } catch {
          node = legacyProcessor(context, onChunk);
        }
      } else {
        node = legacyProcessor(context, onChunk);
      }
      source.connect(node);
      node.connect(context.destination);

      const values = new Uint8Array(analyser.frequencyBinCount);
      let timer = 0;
      const meter = () => {
        analyser.getByteTimeDomainData(values);
        let sum = 0;
        for (const value of values) {
          const normalized = (value - 128) / 128;
          sum += normalized * normalized;
        }
        setLevel(Math.min(1, Math.sqrt(sum / values.length) * 4));
        timer = requestAnimationFrame(meter);
      };
      meter();
      resources.current = { stream, context, node, timer };
      setActive(true);
      setDevices(
        (await navigator.mediaDevices.enumerateDevices()).filter(item => item.kind === "audioinput"),
      );
    } catch (reason) {
      stream?.getTracks().forEach(track => track.stop());
      if (context) void context.close();
      setError(reason instanceof Error ? reason.message : "Microphone unavailable");
      stop();
      throw reason;
    }
  }, [stop]);

  useEffect(() => stop, [stop]);
  return { active, level, error, devices, start, stop };
}
