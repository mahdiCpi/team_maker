import type { NextConfig } from "next";

/**
 * Dev topology (Story 2.0, AC 6).
 *
 * The browser only ever issues same-origin `/api/...` requests; Next proxies
 * them server-side to the FastAPI process. That is deliberate instead of CORS:
 * it removes preflight, credentials-mode and every `Access-Control-*` header
 * from the picture, and it matches AD-3's eventual one-process distribution
 * story ("the web UI served by the backend"). There is no CORS middleware
 * anywhere in this repo, and there must not be one.
 *
 * The API origin is read from the environment and never hard-coded, because
 * the ports move: `langfuse/docker-compose.yml` runs under `network_mode:
 * host` with a 3000 listener and no `ports:` mapping, so when that optional
 * dev stack is up on a Linux host it occupies 3000 and `next dev` falls
 * forward to 3001. 8000 is uvicorn's default and is what `make api-dev` binds.
 *
 * A `web/app/api/` directory would shadow this rewrite with a filesystem
 * route. There must not be one — `tests/api/test_dev_topology.py` asserts it.
 */
const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_ORIGIN}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
