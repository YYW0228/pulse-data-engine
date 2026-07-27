/**
 * Pulse Data Engine — Cloudflare Worker
 *
 * Zero-cost delivery chain: serve Parquet files from R2 with CORS + Range.
 * DuckDB WASM reads Parquet via HTTP Range requests, so we MUST support:
 *   1. Range header → 206 Partial Content
 *   2. OPTIONS preflight → 204 with CORS headers
 *   3. GET / → manifest listing (JSON)
 *   4. GET /parquet/* → Parquet files from R2
 *
 * Deploy:
 *   npm install -g wrangler
 *   wrangler deploy
 */

// ── CORS headers for every response ──────────────────────────────────
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
  'Access-Control-Allow-Headers': 'Range, Content-Type',
  'Access-Control-Expose-Headers': 'Content-Range, Accept-Ranges, Content-Length',
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const method = request.method;

    // ── OPTIONS preflight ──────────────────────────────────────────
    if (method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: { ...CORS_HEADERS, 'Access-Control-Max-Age': '86400' },
      });
    }

    // ── Health check ───────────────────────────────────────────────
    if (url.pathname === '/' || url.pathname === '/health') {
      return new Response(JSON.stringify({
        status: 'ok',
        service: 'pulse-data-engine',
        parquet_prefix: 'parquet/',
        docs: 'https://github.com/YYW0228/pulse-data-engine',
      }), {
        headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    // ── Manifest listing ──────────────────────────────────────────
    if (url.pathname === '/manifest.json') {
      const objects = await env.PULSE_BUCKET.list({ prefix: 'parquet/' });
      const files = objects.objects.map(o => ({
        key: o.key,
        size: o.size,
        etag: o.etag,
        uploaded: o.uploaded,
      }));
      return new Response(JSON.stringify({ files, count: files.length }), {
        headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    // ── Serve Parquet files ────────────────────────────────────────
    if (url.pathname.startsWith('/parquet/')) {
      const key = url.pathname.slice(1); // "parquet/year=2026/month=7/..."
      const object = await env.PULSE_BUCKET.get(key);

      if (object === null) {
        return new Response(`Not Found: ${key}`, {
          status: 404,
          headers: CORS_HEADERS,
        });
      }

      // Range request → 206 Partial Content (required by DuckDB WASM)
      const rangeHeader = request.headers.get('Range');
      if (rangeHeader) {
        // Parse Range header: "bytes=start-end"
        const match = rangeHeader.match(/bytes=(\d+)-(\d*)/);
        if (match) {
          const start = parseInt(match[1], 10);
          const end = match[2] ? parseInt(match[2], 10) : object.size - 1;
          const chunkSize = end - start + 1;

          // Stream only the requested byte range
          const stream = object.body({ offset: start, length: chunkSize });

          return new Response(stream, {
            status: 206,
            headers: {
              ...CORS_HEADERS,
              'Content-Type': 'application/octet-stream',
              'Content-Length': String(chunkSize),
              'Content-Range': `bytes ${start}-${end}/${object.size}`,
              'Accept-Ranges': 'bytes',
              'Cache-Control': 'public, max-age=3600',
              'ETag': object.etag,
            },
          });
        }
      }

      // Full response
      const headers = {
        ...CORS_HEADERS,
        'Content-Type': 'application/octet-stream',
        'Content-Length': String(object.size),
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'public, max-age=3600',
        'ETag': object.etag,
      };

      return new Response(object.body, { headers });
    }

    // ── 404 ────────────────────────────────────────────────────────
    return new Response('Not Found', {
      status: 404,
      headers: CORS_HEADERS,
    });
  },
};
