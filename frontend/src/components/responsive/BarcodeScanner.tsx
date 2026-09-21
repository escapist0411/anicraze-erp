import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { Camera, CameraOff, RotateCcw, ScanLine } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

type Props = { onScan: (value: string) => void; placeholder?: string };

export function BarcodeScanner({ onScan, placeholder = 'Scan barcode or enter SKU' }: Props) {
  const [input, setInput] = useState('');
  const [camera, setCamera] = useState(false);
  const [error, setError] = useState('');
  const video = useRef<HTMLVideoElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const controls = useRef<IScannerControls | null>(null);
  const last = useRef({ value: '', at: 0 });
  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  const emit = (raw: string, cameraResult = false) => {
    const value = raw.trim();
    if (!value) return;
    if (!cameraResult || value !== last.current.value || Date.now() - last.current.at > 1200) {
      last.current = { value, at: Date.now() };
      onScanRef.current(value);
    }
  };

  const submitManual = () => {
    emit(input);
    setInput('');
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  useEffect(() => {
    if (!camera) return;
    let active = true;
    const reader = new BrowserMultiFormatReader();

    const stop = () => {
      active = false;
      controls.current?.stop();
      controls.current = null;
      stream.current?.getTracks().forEach((track) => track.stop());
      stream.current = null;
      if (video.current) video.current.srcObject = null;
    };

    const start = async () => {
      setError('');
      const preferred: MediaStreamConstraints = { audio: false, video: { facingMode: { ideal: 'environment' } } };
      try {
        stream.current = await navigator.mediaDevices.getUserMedia(preferred);
      } catch (preferredError) {
        if (preferredError instanceof DOMException && preferredError.name === 'NotAllowedError') throw preferredError;
        stream.current = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
      }
      if (!active || !video.current) return stop();
      video.current.srcObject = stream.current;
      await video.current.play();
      controls.current = await reader.decodeFromStream(stream.current, video.current, (result) => {
        if (result?.getText()) emit(result.getText(), true);
      });
    };

    void start().catch((cause: unknown) => {
      stop();
      const denied = cause instanceof DOMException && cause.name === 'NotAllowedError';
      setError(denied ? 'Camera permission is required to scan barcodes.' : 'Camera could not start. Try again or use manual barcode entry.');
      setCamera(false);
    });
    return stop;
  }, [camera]);

  return (
    <div className="space-y-3">
      <label className="flex min-h-12 items-center rounded-lg border bg-background px-3">
        <ScanLine className="size-4 text-primary" />
        <input ref={inputRef} autoFocus value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); submitManual(); } }} className="min-w-0 flex-1 bg-transparent px-2 outline-none" placeholder={placeholder} />
        <button type="button" onClick={submitManual} className="min-h-10 rounded-md px-3 text-xs font-semibold">Search</button>
      </label>
      <button type="button" onClick={() => { setError(''); setCamera((value) => !value); }} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border font-semibold">
        {camera ? <CameraOff className="size-5" /> : error ? <RotateCcw className="size-5" /> : <Camera className="size-5" />}
        {camera ? 'Close camera' : error ? 'Try again' : 'Open camera / Start scanner'}
      </button>
      {camera && <video ref={video} muted autoPlay playsInline aria-label="Barcode camera preview" className="aspect-video w-full rounded-xl bg-black object-cover" />}
      {error && <div role="alert" className="rounded-lg bg-amber-500/10 p-3 text-xs text-amber-800"><p>{error}</p><p className="mt-1">You can still enter a barcode, SKU, or product name above.</p></div>}
    </div>
  );
}
