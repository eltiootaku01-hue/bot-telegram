import { WaifuMonCombatCanvas, playCutIn } from "./combat.js";
import { WaifuMonApi } from "./api.js";

const tg = window.Telegram?.WebApp;

const DEFAULT_TEAM = [
  { id: "cari", name: "Cari", team: "player", x: 0.18, y: 0.70, size: 116 },
  { id: "cami", name: "Cami", team: "player", x: 0.38, y: 0.70, size: 116 },
  { id: "sunna", name: "Sunna", team: "player", x: 0.58, y: 0.70, size: 116 },
  { id: "training-dummy", name: "Dummy", team: "enemy", x: 0.82, y: 0.70, size: 132 },
];

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

function spriteUrl(characterId) {
  return new URL(`../../assets/production/sprites/${characterId}_idle.png`, import.meta.url).href;
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
      combat.setPose(attacker.id, action === "defend" ? "hit" : "attack");

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
    const userId = tg?.initDataUnsafe?.user?.id;
    if (userId) referralUrl.searchParams.set("ref", String(userId));

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

function boot() {
  setupTelegram();
  setupPlayerHeader();

  const canvas = document.getElementById("combat-canvas");
  if (!canvas) return;

  const combat = new WaifuMonCombatCanvas(canvas);
  setupTeam(combat);
  setupCombatActions(combat);
  setupStore();
  setupReferralShare();
}

boot();
