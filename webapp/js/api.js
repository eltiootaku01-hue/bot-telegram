const DEFAULT_API_BASE_URL = "";

function configuredApiBaseUrl() {
  const meta = document.querySelector('meta[name="waifumon-api-base-url"]');
  const fromMeta = meta?.content?.trim() || "";
  const fromGlobal = window.WAIFUMON_API_BASE_URL?.trim?.() || "";
  return (fromGlobal || fromMeta || DEFAULT_API_BASE_URL).replace(/\/+$/, "");
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

  _headers({ json = true } = {}) {
    const initData = window.Telegram?.WebApp?.initData || "";
    if (!initData) {
      throw new Error("Telegram initData is unavailable. Abrí la Mini App desde Telegram.");
    }
    const headers = {
      "X-Telegram-Init-Data": initData,
    };
    if (json) {
      headers["Content-Type"] = "application/json";
    }
    return headers;
  }

  async _request(path, options = {}) {
    const response = await fetch(this._url(path), {
      ...options,
      headers: {
        ...this._headers({ json: !(options.body instanceof FormData) }),
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

  async listAdminCards() {
    return this._request("/api/admin/cards", { method: "GET" });
  }

  async createCard(formData) {
    return this._request("/api/admin/cards", {
      method: "POST",
      body: formData,
    });
  }

  cardAssetUrl(imageUrl) {
    const value = String(imageUrl || "").replace(/^\/+/, "");
    const prefix = "assets/cards/";
    if (!value.startsWith(prefix)) {
      throw new Error("Invalid card asset path.");
    }
    const filename = value.slice(prefix.length);
    if (!/^[A-Za-z0-9_-]+\.(?:jpg|png|webp)$/i.test(filename)) {
      throw new Error("Invalid card asset filename.");
    }
    return this._url(`/api/cards/assets/${encodeURIComponent(filename)}`);
  }
}
