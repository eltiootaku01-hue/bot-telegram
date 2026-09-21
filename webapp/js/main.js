import { WaifuMonCombatCanvas, playCutIn } from "./combat.js";

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

function setupTeam(combat) {
  const grid = document.getElementById("team-grid");
  const count = document.getElementById("team-count");
  if (!grid) return;

  const team = DEFAULT_TEAM.filter((entry) => entry.team === "player");
  grid.replaceChildren();

  for (const member of team) {
    const slot = document.createElement("article");
    slot.className = "team-slot";

    const image = document.createElement("img");
    image.alt = member.name;
    image.loading = "lazy";
    image.decoding = "async";
    image.src = spriteUrl(member.id);
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

  if (count) count.textContent = `${team.length}/3`;
  combat.setEntities(DEFAULT_TEAM);
  void combat.preload(DEFAULT_TEAM.map((entry) => entry.id));
}

function setupCombatActions(combat) {
  const status = document.getElementById("combat-status");
  const actions = document.getElementById("combat-actions");
  if (!actions) return;

  actions.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button || button.disabled) return;

    const action = button.dataset.action;
    actions.querySelectorAll("button").forEach((node) => {
      node.disabled = true;
    });

    try {
      if (status) status.textContent = action === "special" ? "Especial..." : "Acción...";

      if (action === "special") {
        combat.setPose("sunna", "attack");
        await playCutIn("sunna", {
          duration: 1500,
          name: "Sunna",
          subtitle: "Habilidad especial",
        });
        combat.setPose("sunna", "idle");
      } else {
        combat.setPose("sunna", action === "attack" ? "attack" : "hit");
        await new Promise((resolve) => window.setTimeout(resolve, 260));
        combat.setPose("sunna", "idle");
      }

      // Visual-only path: no damage, HP or multiplier is calculated here.
      if (status) status.textContent = `Acción: ${action}`;
      tg?.HapticFeedback?.impactOccurred?.("light");
    } finally {
      actions.querySelectorAll("button").forEach((node) => {
        node.disabled = false;
      });
    }
  });
}

function setupStore() {
  document.querySelectorAll("[data-purchase]").forEach((button) => {
    button.addEventListener("click", () => {
      const product = button.dataset.purchase || "unknown";
      tg?.showPopup?.({
        title: "Telegram Stars",
        message: `${product}: la factura debe ser creada y validada por el bot.`,
        buttons: [{ type: "close" }],
      });
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
