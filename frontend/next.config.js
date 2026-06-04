/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV === "development";

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",

  async headers() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains; preload",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              // unsafe-eval + unsafe-inline requeridos por webpack HMR y RSC en desarrollo
              isDev
                ? "script-src 'self' 'unsafe-eval' 'unsafe-inline'"
                : "script-src 'self'",
              // blob: requerido por webpack workers en desarrollo
              isDev ? "worker-src blob:" : "",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https:",
              `connect-src 'self' ${[apiUrl, "https://*.sentry.io", isDev ? "ws://localhost:3000" : ""].filter(Boolean).join(" ")}`,
              "font-src 'self'",
              "frame-ancestors 'none'",
            ].filter(Boolean).join("; "),
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
