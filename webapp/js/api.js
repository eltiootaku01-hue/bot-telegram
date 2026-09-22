const DEFAULT_API_BASE_URL = "";

function configuredApiBaseUrl() {
  const meta = document.querySelector('meta[name="waifumon-api-base-url"]');
  const fromMeta = meta?.content?.trim() || "";
  const fromGlobal = window.WAIFUMON_API_BASE_URL?.trim?.() || "";
  const fromQuery = new URLSearchParams(window.location.search).get("api")?.trim() || "";
  return (fromQuery || fromGlobal || fromMeta || DEFAULT_API_BASE_URL).replace(/\/+$/, "");
}

export class WaifuMonApi {
  constructor({ baseUrl = configuredApiBaseUrl() } = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  _url(path) {
    if (!this.baseUrl) {
      throw new Error("TMA API base URL is not configured.");
    }
    return this.baseUrl + path;
  }

  _headers() {
    const initData = window.Telegram?.WebApp?.initData || "";
    if (!initData) {
      throw new Error("Telegram initData is unavailable. Abrí la Mini App desde Telegram.");
    }
    return {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData,
    };
  }

  async _request(path, options = {}) {
    const response = await fetch(this._url(path), {
      ...options,
      headers: {
        ...this._headers(),
        ...(options.headers || {}),
      },
      cache: "no-store",
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    }
    return payload;
  }

  async getCombatInit() {
    return this._request("/api/combat/init", { method: "GET" });
  }

  async combatAction(payload) {
    return this._request("/api/combat/action", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createInvoice(product) {
    return this._request("/api/store/invoice", {
      method: "POST",
      body: JSON.stringify({ product }),
    });
  }
}
