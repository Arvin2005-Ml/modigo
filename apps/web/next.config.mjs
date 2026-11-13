const apiOrigin = process.env.API_ORIGIN || 'http://127.0.0.1:8000';
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(apiOrigin)) {
  throw new Error('API_ORIGIN must address the API on container loopback');
}
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  logging: false,
  // The pinned TypeScript 5 compiler API avoids child-process CLI output parsing.
  experimental: {useTypeScriptCli: false},
  async rewrites() { return [{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }]; },
  async headers() {
    return [{source: '/:path*', headers: [
      {key: 'Referrer-Policy', value: 'no-referrer'},
      {key: 'X-Content-Type-Options', value: 'nosniff'},
      {key: 'X-Frame-Options', value: 'DENY'},
      {key: 'Cache-Control', value: 'no-store'},
      {key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()'}
    ]}, {source: '/sw.js', headers: [
      {key: 'Content-Type', value: 'application/javascript; charset=utf-8'},
      {key: 'Cache-Control', value: 'no-store, max-age=0'},
      {key: 'Service-Worker-Allowed', value: '/'},
      {key: 'Content-Security-Policy', value: "default-src 'self'; script-src 'self'"}
    ]}];
  }
};
export default nextConfig;
