// data-proxy.worker.js — R2 Parquet 代理 Worker v2
// 正确处理 DuckDB WASM 的 Range 请求

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const key = url.pathname.slice(1) || 'jobs.parquet';

    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
          'Access-Control-Allow-Headers': 'Range',
          'Access-Control-Expose-Headers': 'Content-Length, Content-Range, Accept-Ranges, Content-Type',
          'Access-Control-Max-Age': '86400',
        },
      });
    }

    // Parse Range header for DuckDB WASM requests
    const rangeHeader = request.headers.get('Range');
    const options = {};
    let expectedStatus = 200;

    if (rangeHeader) {
      const match = rangeHeader.match(/bytes=(\d+)-(\d+)?/);
      if (match) {
        const offset = parseInt(match[1], 10);
        const end = match[2] ? parseInt(match[2], 10) : undefined;
        options.range = { offset };
        if (end !== undefined) {
          options.range.length = end - offset + 1;
        }
        expectedStatus = 206;
      }
    }

    const r2Object = await env.PARQUET_BUCKET.get(key, options);

    if (r2Object === null) {
      return new Response('Not Found', { status: 404 });
    }

    const responseHeaders = new Headers();
    responseHeaders.set('Access-Control-Allow-Origin', '*');
    responseHeaders.set('Access-Control-Expose-Headers', 'Content-Length, Content-Range, Accept-Ranges, Content-Type');
    responseHeaders.set('Content-Type', 'application/octet-stream');
    responseHeaders.set('Accept-Ranges', 'bytes');
    responseHeaders.set('Cache-Control', 'public, max-age=3600');

    if (rangeHeader && r2Object.range) {
      const start = r2Object.range.offset;
      const end = start + r2Object.range.length - 1;
      const total = r2Object.size;
      responseHeaders.set('Content-Range', `bytes ${start}-${end}/${total}`);
      responseHeaders.set('Content-Length', r2Object.range.length);
      return new Response(r2Object.body, { status: 206, headers: responseHeaders });
    }

    responseHeaders.set('Content-Length', r2Object.size);
    return new Response(r2Object.body, { status: 200, headers: responseHeaders });
  },
};
