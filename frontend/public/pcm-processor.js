class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input) return true;

    const ratio = sampleRate / 16000;
    const pcm = new Int16Array(Math.floor(input.length / ratio));
    for (let index = 0; index < pcm.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, input[Math.floor(index * ratio)]));
      pcm[index] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
