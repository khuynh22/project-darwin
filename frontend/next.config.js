/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Phaser ships browser-only globals; only import it in client components.
  webpack: (config) => {
    config.externals = config.externals || [];
    return config;
  },
  env: {
    NEXT_PUBLIC_ORACLE_HTTP: process.env.NEXT_PUBLIC_ORACLE_HTTP || 'http://localhost:8000',
    NEXT_PUBLIC_ORACLE_WS: process.env.NEXT_PUBLIC_ORACLE_WS || 'ws://localhost:8000/ws',
  },
};

module.exports = nextConfig;
