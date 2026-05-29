'use client';

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4 p-6 text-center">
      <div className="text-4xl">🐛</div>
      <h2 className="font-display text-cozy-ink text-xl">A critter tripped on the carpet</h2>
      <pre className="text-xs text-[#B14848] max-w-lg overflow-auto p-4 bg-[#FFE0E0] border border-[#E6A8A8] rounded-xl text-left">
        {error.message}
      </pre>
      <button onClick={reset} className="btn-cozy primary">
        Try again
      </button>
    </div>
  );
}
