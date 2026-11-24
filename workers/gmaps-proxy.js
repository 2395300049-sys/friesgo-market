/**
 * FriesGo Global - Cloudflare Worker Proxy for Google Maps Places API (New)
 *
 * Security & Billing Best Practices:
 *   1. Keeps GOOGLE_MAPS_API_KEY in Cloudflare Secrets (never exposed in browser or URLs).
 *   2. Enforces mandatory TEAM_PASS secret (returns 503 if unset so proxy is never publicly open).
 *   3. Optional QUOTA_KV tracks approximate monthly calls (note: KV is eventually consistent, NOT
 *      atomic — always configure hard monthly quotas/budget alerts in Google Cloud Console too!).
 *   4. Optional ALLOWED_ORIGIN restricts browser CORS to your exact GitHub Pages origin.
 */

function buildCorsHeaders(request, env) {
  const reqOrigin = request.headers.get("Origin") || "";
  const allowedRaw = (env.ALLOWED_ORIGIN || "").trim();
  let allowOrigin = "*";
  if (allowedRaw) {
    const allowedList = allowedRaw.split(",").map((s) => s.trim()).filter(Boolean);
    allowOrigin = allowedList.includes(reqOrigin) ? reqOrigin : allowedList[0];
  }
  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Team-Pass",
    "Vary": "Origin",
  };
}

const MONTHLY_CAP = 900; // Soft app-level guardrail below Google's 1,000 free Enterprise calls/month

const FIELD_MASK = [
  "places.displayName",
  "places.formattedAddress",
  "places.internationalPhoneNumber",
  "places.websiteUri",
  "places.rating",
  "places.userRatingCount",
  "places.googleMapsUri",
  "places.primaryTypeDisplayName",
  "nextPageToken",
].join(",");

export default {
  async fetch(request, env) {
    const cors = buildCorsHeaders(request, env);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "POST") {
      return jsonResp({ error: "POST only" }, 405, cors);
    }

    // Mandatory team auth to prevent unauthorized public abuse
    if (!env.TEAM_PASS) {
      return jsonResp(
        { error: "服务端安全拦截：请先在 Cloudflare Worker Secrets 配置 TEAM_PASS 团队口令后再启用。" },
        503,
        cors
      );
    }
    const pass = request.headers.get("X-Team-Pass") || "";
    if (pass !== env.TEAM_PASS) {
      return jsonResp({ error: "团队访问口令不正确（请在网页填写口令）" }, 401, cors);
    }

    if (!env.GOOGLE_MAPS_API_KEY) {
      return jsonResp({ error: "Worker 尚未配置 GOOGLE_MAPS_API_KEY 密钥" }, 500, cors);
    }

    // Best-effort monthly usage tracking via Cloudflare KV (reserve slot before calling upstream)
    let usedThisMonth = 0;
    const ym = new Date().toISOString().slice(0, 7);
    const kvKey = `gmaps_calls_${ym}`;
    if (env.QUOTA_KV) {
      usedThisMonth = parseInt((await env.QUOTA_KV.get(kvKey)) || "0", 10);
      if (usedThisMonth >= MONTHLY_CAP) {
        return jsonResp(
          { error: `本应用本月已记录达 ${MONTHLY_CAP} 次上限，已自动暂停请求（请以 Google Cloud 账单配额为准）。` },
          429,
          cors
        );
      }
      await env.QUOTA_KV.put(kvKey, String(usedThisMonth + 1), { expirationTtl: 60 * 60 * 24 * 35 });
    }

    let body = {};
    try {
      body = await request.json();
    } catch {
      return jsonResp({ error: "Invalid JSON body" }, 400, cors);
    }

    const textQuery = String(body.textQuery || "").trim();
    if (!textQuery) {
      return jsonResp({ error: "请提供搜索关键词 textQuery" }, 400, cors);
    }

    const payload = {
      textQuery,
      pageSize: Math.min(20, Math.max(5, parseInt(body.pageSize || 20, 10))),
    };
    if (body.pageToken) payload.pageToken = String(body.pageToken);
    if (body.languageCode) payload.languageCode = String(body.languageCode);

    let gRes;
    try {
      gRes = await fetch("https://places.googleapis.com/v1/places:searchText", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Goog-Api-Key": env.GOOGLE_MAPS_API_KEY,
          "X-Goog-FieldMask": FIELD_MASK,
        },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      return jsonResp({ error: "连接 Google Maps 上游失败：" + String(err) }, 502, cors);
    }

    let data = {};
    const rawText = await gRes.text();
    try {
      data = rawText ? JSON.parse(rawText) : {};
    } catch {
      return jsonResp(
        { error: `Google Maps 上游返回非 JSON 响应 (HTTP ${gRes.status})` },
        502,
        cors
      );
    }

    return jsonResp(
      {
        places: data.places || [],
        nextPageToken: data.nextPageToken || "",
        error: data.error ? data.error.message : "",
        quotaUsed: env.QUOTA_KV ? usedThisMonth + 1 : null,
        quotaCap: MONTHLY_CAP,
      },
      gRes.ok ? 200 : gRes.status,
      cors
    );
  },
};

function jsonResp(obj, status = 200, corsHeaders = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" },
  });
}
