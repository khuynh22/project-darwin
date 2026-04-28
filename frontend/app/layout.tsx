import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Project Darwin — The Pixel Arena',
  description: 'Multi-agent LLM social-economy simulation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
