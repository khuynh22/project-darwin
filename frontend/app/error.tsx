'use client';

export default function ErrorBoundary({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    return (
        <div className="flex flex-col items-center justify-center h-screen bg-arena-bg text-white gap-4">
            <h2 className="text-arena-accent text-lg">Something went wrong</h2>
            <pre className="text-xs text-red-400 max-w-lg overflow-auto p-4 bg-black/50 rounded">
                {error.message}
            </pre>
            <button
                onClick={reset}
                className="bg-arena-accent text-black px-4 py-2 text-sm"
            >
                Try again
            </button>
        </div>
    );
}
