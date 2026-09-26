import type { NextConfig } from "next";

// O navegador chama /api/* no próprio frontend; o Next repassa para a API FastAPI.
// API_URL: endereço do backend (padrão http://localhost:8000).
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
