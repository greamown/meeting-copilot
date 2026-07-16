class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input) return true;

    const ratio = sampleRate / 16000;
    const pcm = new Int16Array(Math.floor(input.length / ratio));
    for (let index = 0; index < pcm.length; index += 1) {
      // Average the source window instead of picking one sample: cheap anti-aliasing,
      // raw decimation feeds aliased audio to whisper and degrades accuracy.
      const from = Math.floor(index * ratio);
      const to = Math.min(input.length, Math.max(from + 1, Math.floor((index + 1) * ratio)));
      let sum = 0;
      for (let i = from; i < to; i += 1) sum += input[i];
      const sample = Math.max(-1, Math.min(1, sum / (to - from)));
      pcm[index] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
