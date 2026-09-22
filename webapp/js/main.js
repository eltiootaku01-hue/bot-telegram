import { WaifuMonCombatCanvas, playCutIn } from "./combat.js";
import { WaifuMonApi } from "./api.js";

const tg = window.Telegram?.WebApp;

function playerDisplayName() {
  return tg?.initDataUnsafe?.user?.first_name
    || tg?.initDataUnsafe?.user?.username
    || "Jugador";
}

function setupTelegram() {
  if (!tg) return;

  tg.ready();
  tg.expand?.();

  const version = document.getElementById("telegram-version");
  if (version) version.textContent = `Telegram ${tg.version || "—"}`;

  tg.onEvent("themeChanged", () => {
    document.body.dataset.theme = tg.colorScheme || "light";
  });
}

function setupPlayerHeader() {
  const name = playerDisplayName();
  const node = document.getElementById("player-name");
  if (node) node.textContent = name;

  // This value is informational only. The server must validate Telegram initData
  // before associating a referral with the authenticated user.
  document.body.dataset.referral = tg?.initDataUnsafe?.start_param || "";
}


function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function setupHolographicCard(member) {
  const card = document.getElementById("sujetoCero");
  const glare = document.getElementById("hologram");
  const art = document.getElementById("tcg-card-art");
  const nameNode = document.getElementById("tcg-card-name");
  const status = document.getElementById("card-showcase-status");
  if (!card || !glare || !art || !member) return;

  const safeId = String(member.id || "").trim();
  if (!/^[a-z0-9_-]+$/i.test(safeId)) return;

  const cardUrl = new URL(
    `../assets/production/cards/${safeId}--normal.jpg`,
    import.meta.url,
  ).href;

  art.alt = `Carta de ${member.name || safeId}`;
  art.src = cardUrl;
  art.onerror = () => {
    art.removeAttribute("src");
    if (status) status.textContent = "Arte no disponible";
  };
  if (nameNode) nameNode.textContent = String(member.name || safeId).toUpperCase();
  if (status) status.textContent = "Foil activo";

  card.classList.add("is-interactive");

  const applyTilt = (x, y) => {
    const tiltX = clamp(x, -1, 1) * 11;
    const tiltY = clamp(y, -1, 1) * 11;
    const glareX = clamp(x, -1, 1) * 42;
    const glareY = clamp(y, -1, 1) * 42;

    card.style.setProperty("--card-tilt-x", `${tiltX}deg`);
    card.style.setProperty("--card-tilt-y", `${-tiltY}deg`);
    glare.style.setProperty("--glare-x", `${glareX}%`);
    glare.style.setProperty("--glare-y", `${glareY}%`);
  };

  const resetTilt = () => applyTilt(0, 0);

  card.addEventListener("pointermove", (event) => {
    const rect = card.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    const y = ((event.clientY - rect.top) / rect.height) * 2 - 1;
    applyTilt(x, y);
  });

  card.addEventListener("pointerleave", resetTilt);

  let orientationAttached = false;
  const attachOrientation = () => {
    if (orientationAttached) return true;
    if (!("DeviceOrientationEvent" in window)) return false;

    window.addEventListener("deviceorientation", (event) => {
      const beta = Number.isFinite(event.beta) ? event.beta : 0;
      const gamma = Number.isFinite(event.gamma) ? event.gamma : 0;
      applyTilt(
        clamp(gamma / 45, -1, 1),
        clamp(beta / 45, -1, 1),
      );
    }, { passive: true });

    orientationAttached = true;
    return true;
  };

  card.addEventListener("click", async () => {
    try {
      const Orientation = window.DeviceOrientationEvent;
      if (
        Orientation
        && typeof Orientation.requestPermission === "function"
        && !orientationAttached
      ) {
        const permission = await Orientation.requestPermission();
        if (permission !== "granted") {
          if (status) status.textContent = "Foil táctil activo";
          return;
        }
      }
      if (attachOrientation()) {
        if (status) status.textContent = "Foil giroscópico activo";
      }
    } catch {
      if (status) status.textContent = "Foil táctil activo";
    }
  });

  attachOrientation();
}

function setupTeam(combat, init) {
  const grid = document.getElementById("team-grid");
  const count = document.getElementById("team-count");
  if (!grid) return;

  grid.replaceChildren();
  for (const member of init.team) {
    const slot = document.createElement("article");
    slot.className = "team-slot";

    const image = document.createElement("img");
    image.alt = member.name;
    image.loading = "lazy";
    image.decoding = "async";
    image.src = member.sprites?.idle || "";
    image.onerror = () => {
      image.remove();
      const fallback = document.createElement("div");
      fallback.className = "sprite-fallback";
      fallback.textContent = member.name;
      slot.prepend(fallback);
    };

    const label = document.createElement("strong");
    label.textContent = member.name;
    slot.append(image, label);
    grid.append(slot);
  }

  if (count) count.textContent = init.team.length + "/3";
  const entities = [
    ...init.team.map((fighter, index) => ({
      id: fighter.id, name: fighter.name, team: "player",
      x: 0.22 + index * 0.12, y: 0.70, size: 116,
    })),
    ...init.opponents.map((fighter, index) => ({
      id: fighter.id, name: fighter.name, team: "enemy",
      x: 0.78 - index * 0.10, y: 0.70, size: 116,
    })),
  ];
  combat.setEntities(entities);
  void combat.preload([...init.team, ...init.opponents].map((entry) => entry.id));
}
function setupCombatActions(combat, api, init) {
  const status = document.getElementById("combat-status");
  const actions = document.getElementById("combat-actions");
  if (!actions) return;

  const attacker = init.team[0];
  const defender = init.opponents[0];
  if (!attacker || !defender) {
    actions.querySelectorAll("button").forEach((node) => { node.disabled = true; });
    if (status) status.textContent = "Sin combatientes";
    return;
  }

  actions.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button || button.disabled) return;

    const action = button.dataset.action;
    actions.querySelectorAll("button").forEach((node) => { node.disabled = true; });
    const turnId = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    const idempotencyKey = crypto.randomUUID ? crypto.randomUUID() : turnId;

    try {
      if (status) status.textContent = action === "special" ? "Especial..." : "Acción...";
      combat.setPose(
        attacker.id,
        action === "defend" ? "hit" : "attack",
        { impact: false },
      );

      if (action === "special") {
        await playCutIn(attacker.id, {
          duration: init.asset_contract.cut_in_duration_ms || 1500,
          name: attacker.name,
          subtitle: "Habilidad especial",
        });
      } else {
        await new Promise((resolve) => window.setTimeout(resolve, 180));
      }

      const result = await api.combatAction({
        action,
        attacker_id: attacker.id,
        defender_id: defender.id,
        turn_id: turnId,
        idempotency_key: idempotencyKey,
      });

      combat.setPose(attacker.id, "idle");
      if (result.defender_hp === 0) combat.setPose(defender.id, "hit");
      const enemyHp = Math.max(0, Number(result.defender_hp ?? 0));
      const enemyMaxHp = Math.max(1, Number(result.defender_max_hp ?? 100));
      const enemyFill = document.getElementById("enemy-hp-fill");
      const enemyValue = document.getElementById("enemy-hp-value");
      const enemyBar = enemyFill?.closest(".hp-bar");
      if (enemyFill) enemyFill.style.width = `${Math.min(100, (enemyHp / enemyMaxHp) * 100)}%`;
      if (enemyValue) enemyValue.textContent = `${enemyHp} / ${enemyMaxHp}`;
      if (enemyBar) enemyBar.setAttribute("aria-valuenow", String(enemyHp));
      if (status) {
        const critical = result.critical ? " · CRÍTICO" : "";
        status.textContent = "-" + result.damage + " HP · " + result.defender_hp + "/" + result.defender_max_hp + critical;
      }
      tg?.HapticFeedback?.impactOccurred?.(result.critical ? "medium" : "light");
    } catch (error) {
      combat.setPose(attacker.id, "idle");
      if (status) status.textContent = "Error de combate";
      tg?.showAlert?.(error instanceof Error ? error.message : "No se pudo ejecutar el turno.");
    } finally {
      actions.querySelectorAll("button").forEach((node) => { node.disabled = false; });
    }
  });
}
function setupStore(api) {
  document.querySelectorAll("[data-purchase]").forEach((button) => {
    button.addEventListener("click", async () => {
      const product = button.dataset.purchase || "";
      button.disabled = true;
      try {
        const invoice = await api.createInvoice(product);
        if (tg?.openInvoice) {
          tg.openInvoice(invoice.invoice_link);
        } else if (tg?.openTelegramLink) {
          tg.openTelegramLink(invoice.invoice_link);
        } else {
          window.open(invoice.invoice_link, "_blank", "noopener,noreferrer");
        }
      } catch (error) {
        tg?.showAlert?.(error instanceof Error ? error.message : "No se pudo crear la factura.");
      } finally {
        button.disabled = false;
      }
    });
  });
}
function setupReferralShare() {
  const button = document.getElementById("share-referral");
  if (!button) return;

  button.addEventListener("click", async () => {
    const referralUrl = new URL(window.location.href);
    referralUrl.hash = "#referral";

    const shareText = "Vení a jugar WaifuMon conmigo.";
    const telegramShare = `https://t.me/share/url?url=${encodeURIComponent(referralUrl.href)}&text=${encodeURIComponent(shareText)}`;

    if (tg?.openTelegramLink) {
      tg.openTelegramLink(telegramShare);
      return;
    }

    if (navigator.share) {
      await navigator.share({ title: "WaifuMon", text: shareText, url: referralUrl.href }).catch(() => {});
      return;
    }

    if (navigator.clipboard) {
      await navigator.clipboard.writeText(referralUrl.href);
      button.textContent = "Copiado";
      window.setTimeout(() => { button.textContent = "Compartir"; }, 1200);
    }
  });
}

function renderAdminCardPool(api, cards) {
  const grid = document.getElementById("card-pool-grid");
  const count = document.getElementById("card-pool-count");
  if (!grid) return;

  grid.replaceChildren();
  for (const card of cards) {
    const article = document.createElement("article");
    article.className = "admin-card-item";

    const image = document.createElement("img");
    image.alt = String(card.character_name || card.id || "Carta");
    image.loading = "lazy";
    try {
      image.src = api.cardAssetUrl(card.image_url);
    } catch {
      image.remove();
    }

    const title = document.createElement("strong");
    title.textContent = String(card.character_name || card.id || "Carta");

    const meta = document.createElement("small");
    meta.textContent = `${card.anime_origin || "—"} · ${card.rarity || "—"} · ${card.collection_points ?? 0} pts`;

    const id = document.createElement("code");
    id.textContent = String(card.id || "");

    article.append(image, title, meta, id);
    grid.append(article);
  }

  if (count) count.textContent = `${cards.length} carta${cards.length === 1 ? "" : "s"}`;
}

async function setupCardAdmin(api) {
  const section = document.getElementById("deck-builder-tab");
  const form = document.getElementById("create-card-form");
  const status = document.getElementById("card-admin-status");
  const submit = document.getElementById("create-card-submit");
  const imageInput = document.getElementById("card-image");
  if (!section || !form || !status || !submit || !imageInput) return;

  try {
    const response = await api.listAdminCards();
    section.hidden = false;
    renderAdminCardPool(api, response.cards || []);
    status.textContent = "Administrador autenticado. Las cartas nuevas entran al /roll al guardarse.";
  } catch {
    // A normal player receives 403 and never sees the administrative surface.
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = imageInput.files?.[0];
    if (!file) {
      status.textContent = "Seleccioná una imagen.";
      return;
    }

    const maxBytes = 10 * 1024 * 1024;
    if (file.size > maxBytes) {
      status.textContent = "La imagen supera el máximo de 10 MB.";
      return;
    }

    submit.disabled = true;
    status.textContent = "Guardando carta...";
    try {
      const formData = new FormData(form);
      const created = await api.createCard(formData);
      status.textContent = `✅ ${created.character_name} guardada. Ya forma parte del pool de /roll.`;
      form.reset();
      const points = document.getElementById("collection-points");
      const provider = document.getElementById("source-provider");
      if (points) points.value = "150";
      if (provider) provider.value = "IA (PixAI/Midjourney)";

      const response = await api.listAdminCards();
      renderAdminCardPool(api, response.cards || []);
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : "No se pudo guardar la carta.";
    } finally {
      submit.disabled = false;
    }
  });
}

async function boot() {
  setupTelegram();
  setupPlayerHeader();

  const canvas = document.getElementById("combat-canvas");
  const status = document.getElementById("combat-status");
  if (!canvas || !status) return;

  const combat = new WaifuMonCombatCanvas(canvas);
  const api = new WaifuMonApi();
  try {
    status.textContent = "Conectando...";
    const init = await api.getCombatInit();
    const stars = document.getElementById("stars-balance");
    if (stars) stars.textContent = "—";
    setupTeam(combat, init);
    setupHolographicCard(init.team[0] || init.opponents[0]);
    setupCombatActions(combat, api, init);
    setupStore(api);
    setupReferralShare();
    await setupCardAdmin(api);
    status.textContent = "Listo";
  } catch (error) {
    status.textContent = "API no disponible";
    document.querySelectorAll("[data-action], [data-purchase]").forEach((node) => { node.disabled = true; });
    tg?.showAlert?.(error instanceof Error ? error.message : "No se pudo conectar con el backend.");
  }
}

void boot();
