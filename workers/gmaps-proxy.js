/**
 * FriesGo Global - Free Cloudflare Worker Proxy for Google Maps Places API (New)
 *
 * Why use this proxy?
 *   1. Keeps your Google Maps API Key safely in Cloudflare Secrets (invisible in browser).
 *   2. Lets all 5-6 colleagues click "Google Maps 批量采客" directly on your webpage (mobile & PC).
 *   3. Optional KV monthly hard cap (<= 900 calls/month) guarantees $0 billing within Google's
 *      1,000 free Enterprise Text Search calls/month (= up to 18,000 real businesses/month!).
 *
 * Setup (2 minutes on https://dash.cloudflare.com -> Workers & Pages -> Create Worker):
 *   1. Paste this file into your Worker and Deploy.
 *   2. Go to Worker Settings -> Variables and Secrets:
 *      - Add Secret: GOOGLE_MAPS_API_KEY = <your Google Maps Places API New key>
 *      - Optional Secret: TEAM_PASS = <simple passcode for your team, e.g. friesgo2026>
 *   3. (Optional) Bind a KV namespace named QUOTA_KV to enforce hard 900 calls/month limit.
 *   4. Paste your Worker URL (e.g. https://friesgo-gmaps.xxx.workers.dev) into the webpage!
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Team-Pass",
};

const MONTHLY_CAP = 900; // Hard safety cap below Google's 1,000 free Enterprise calls/month

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
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }
    if (request.method !== "POST") {
      return jsonResp({ error: "POST only" }, 405);
    }

    if (env.TEAM_PASS) {
      const pass = request.headers.get("X-Team-Pass") || "";
      if (pass !== env.TEAM_PASS) {
        return jsonResp({ error: "团队访问口令不正确（请在网页填写口令）" }, 401);
      }
    }

    if (!env.GOOGLE_MAPS_API_KEY) {
      return jsonResp({ error: "Worker 尚未配置 GOOGLE_MAPS_API_KEY 密钥" }, 500);
    }

    // Optional hard monthly quota cap using Cloudflare KV
    let usedThisMonth = 0;
    const ym = new Date().toISOString().slice(0, 7);
    const kvKey = `gmaps_calls_${ym}`;
    if (env.QUOTA_KV) {
      usedThisMonth = parseInt((await env.QUOTA_KV.get(kvKey)) || "0", 10);
      if (usedThisMonth >= MONTHLY_CAP) {
        return jsonResp(
          { error: `本月已达安全免费上限（${MONTHLY_CAP} 次），已自动暂停以防产生费用。` },
          429
        );
      }
    }

    let body = {};
    try {
      body = await request.json();
    } catch {
      return jsonResp({ error: "Invalid JSON body" }, 400);
    }

    const textQuery = String(body.textQuery || "").trim();
    if (!textQuery) {
      return jsonResp({ error: "请提供搜索关键词 textQuery" }, 400);
    }

    const payload = {
      textQuery,
      pageSize: Math.min(20, Math.max(5, parseInt(body.pageSize || 20, 10))),
    };
    if (body.pageToken) payload.pageToken = String(body.pageToken);
    if (body.languageCode) payload.languageCode = String(body.languageCode);

    const gRes = await fetch("https://places.googleapis.com/v1/places:searchText", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": env.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
      },
      body: JSON.stringify(payload),
    });

    const data = await gRes.json();
    if (gRes.ok && env.QUOTA_KV) {
      await env.QUOTA_KV.put(kvKey, String(usedThisMonth + 1), { expirationTtl: 60 * 60 * 24 * 35 });
    }

    return jsonResp(
      {
        places: data.places || [],
        nextPageToken: data.nextPageToken || "",
        error: data.error ? data.error.message : "",
        quotaUsed: env.QUOTA_KV ? usedThisMonth + 1 : null,
        quotaCap: MONTHLY_CAP,
      },
      gRes.ok ? 200 : gRes.status
    );
  },
};

function jsonResp(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json; charset=utf-8" },
  });
}
