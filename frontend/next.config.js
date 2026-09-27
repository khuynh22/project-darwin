const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The shared world tables live above this directory; the build has to be
  // told they are part of the app.
  outputFileTracingRoot: path.join(__dirname, '..'),
  // Phaser ships browser-only globals; only import it in client components.
  webpack: (config) => {
    config.externals = config.externals || [];
    config.resolve.alias['@shared'] = path.resolve(__dirname, '../shared');
    return config;
  },
  env: {
    NEXT_PUBLIC_ORACLE_HTTP: process.env.NEXT_PUBLIC_ORACLE_HTTP || 'http://localhost:8000',
    NEXT_PUBLIC_ORACLE_WS: process.env.NEXT_PUBLIC_ORACLE_WS || 'ws://localhost:8000/ws',
  },
};

module.exports = nextConfig;
