import { LightweightCombatEffects, deterministicScrapBurst } from "./effects.js";

const SPRITE_SIZE = 128;
const CUT_IN_DURATION_MS = 1500;
const IMPACT_SHAKE_MS = 200;
const HIT_FLASH_FRAMES = 3;
const POSES = ["idle", "attack", "hit"];
const ASSET_FILTER = "contrast(1.3) saturate(1.5) hue-rotate(-10deg)";

function spriteUrl(characterId, pose = "idle") {
  return new URL(`../../assets/production/sprites/${characterId}_${pose}.png`, import.meta.url).href;
}

function cardUrl(characterId) {
  return new URL(`../../assets/production/cards/${characterId}--normal.jpg`, import.meta.url).href;
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.decoding = "async";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`No se pudo cargar: ${src}`));
    image.src = src;
  });
}

function drawFallback(ctx, x, y, size, label, hostile = false) {
  ctx.fillStyle = hostile ? "#2a0b0b" : "#1b0a27";
  ctx.fillRect(x, y, size, size);
  ctx.strokeStyle = hostile ? "#ff2a2a" : "#b026ff";
  ctx.lineWidth = Math.max(2, size * 0.025);
  ctx.strokeRect(x + 1, y + 1, size - 2, size - 2);
  ctx.fillStyle = hostile ? "#ff7676" : "#dd9bff";
  ctx.font = `900 ${Math.max(14, size * 0.12)}px "Cascadia Mono", Consolas, monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label.slice(0, 12), x + size / 2, y + size / 2);
}

export class WaifuMonCombatCanvas {
  constructor(canvas, { width = 768, height = 432 } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d", { alpha: false });
    this.width = width;
    this.height = height;
    this.entities = [];
    this.images = new Map();
    this.reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
    this.shakeUntil = 0;
    this.shakeFrameId = 0;
    this.hitFlashFrames = 0;
    this.effects = new LightweightCombatEffects();
  }

  setEntities(entities) {
    this.entities = entities.map((entity) => ({
      id: entity.id,
      name: entity.name ?? entity.id,
      team: entity.team ?? "player",
      pose: entity.pose ?? "idle",
      x: Number(entity.x ?? (entity.team === "enemy" ? 0.72 : 0.28)),
      y: Number(entity.y ?? 0.64),
      size: Number(entity.size ?? 128),
    }));
    this.render();
  }

  async preload(characterIds) {
    const ids = [...new Set(characterIds)];
    await Promise.all(ids.map(async (id) => {
      await Promise.all(POSES.map(async (pose) => {
        const key = `${id}:${pose}`;
        if (this.images.has(key)) return;
        try {
          this.images.set(key, await loadImage(spriteUrl(id, pose)));
        } catch {
          this.images.set(key, null);
        }
      }));
    }));
    this.render();
  }

  setPose(characterId, pose, { impact = pose === "hit" } = {}) {
    const entity = this.entities.find((candidate) => candidate.id === characterId);
    if (!entity) return;

    entity.pose = pose;
    const x = this.width * entity.x;
    const y = this.height * entity.y - entity.size * 0.55;

    if (pose === "attack") {
      this.effects.slash(x + entity.size * 0.35, y, { direction: entity.team === "enemy" ? -1 : 1 });
      this._ensureEffectsFrame();
    }
    if (pose === "hit") {
      this.effects.burst(x, y, { count: 12, power: 0.72, size: 2.1 });
      this._ensureEffectsFrame();
    }

    if (pose === "hit" && impact) {
      this.triggerImpact();
      return;
    }
    this.render();
  }

  triggerAction(characterId, action, targetId = null) {
    const actor = this.entities.find((entity) => entity.id === characterId);
    const target = targetId
      ? this.entities.find((entity) => entity.id === targetId)
      : null;
    if (!actor) return;

    const actorX = this.width * actor.x;
    const actorY = this.height * actor.y - actor.size * 0.55;
    const targetX = target ? this.width * target.x : actorX + 80;
    const targetY = target
      ? this.height * target.y - target.size * 0.55
      : actorY;

    if (action === "special") {
      const burst = deterministicScrapBurst(characterId.length + action.length);
      this.effects.burst(targetX, targetY, burst);
    } else if (action === "attack") {
      this.effects.slash(actorX + actor.size * 0.35, actorY, { direction: 1 });
    } else if (action === "defend") {
      this.effects.burst(actorX, actorY, { count: 8, power: 0.5, size: 1.8, flash: 0.05 });
    }
    this._ensureEffectsFrame();
    this.render();
  }

  triggerImpact() {
    this.hitFlashFrames = HIT_FLASH_FRAMES;
    if (!this.reducedMotion) {
      this.shakeUntil = performance.now() + IMPACT_SHAKE_MS;
    }
    if (!this.shakeFrameId) {
      this.shakeFrameId = requestAnimationFrame(() => this._impactFrame());
    }
    this.render();
  }

  _impactFrame() {
    this.shakeFrameId = 0;
    this.effects.step(1 / 60);
    this.render();
    if (performance.now() < this.shakeUntil || this.hitFlashFrames > 0 || this.effects.active) {
      this.shakeFrameId = requestAnimationFrame(() => this._impactFrame());
    } else {
      this.shakeUntil = 0;
    }
  }

  _ensureEffectsFrame() {
    if (this.shakeFrameId) return;
    this.shakeFrameId = requestAnimationFrame(() => this._impactFrame());
  }

  render() {
    const ctx = this.ctx;
    const scaleX = this.canvas.width / this.width;
    const scaleY = this.canvas.height / this.height;
    const now = performance.now();
    const shaking = !this.reducedMotion && now < this.shakeUntil;

    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.scale(scaleX, scaleY);

    if (shaking) {
      ctx.translate(Math.random() * 10, Math.random() * 10);
    }

    ctx.fillStyle = "rgba(176, 38, 255, 0.05)";
    ctx.fillRect(0, this.height * 0.7, this.width, this.height * 0.3);

    for (const entity of this.entities) {
      const px = this.width * entity.x;
      const py = this.height * entity.y;
      const size = entity.size;
      const image = this.images.get(`${entity.id}:${entity.pose}`) ?? this.images.get(`${entity.id}:idle`);

      ctx.save();
      ctx.filter = ASSET_FILTER;
      if (image) {
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(image, px - size / 2, py - size, size, size);
      } else {
        drawFallback(ctx, px - size / 2, py - size, size, entity.name, entity.team === "enemy");
      }
      ctx.restore();

      ctx.fillStyle = "rgba(0,0,0,0.68)";
      ctx.fillRect(px - size / 2, py + 8, size, 20);
      ctx.fillStyle = "#f6f0ff";
      ctx.font = '900 12px "Cascadia Mono", Consolas, monospace';
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(entity.name.toUpperCase(), px, py + 18);
    }

    this.effects.draw(ctx);

    if (this.hitFlashFrames > 0) {
      ctx.fillStyle = "#ff2a2a";
      ctx.globalAlpha = 0.4;
      ctx.fillRect(0, 0, this.width, this.height);
      ctx.globalAlpha = 1;
      this.hitFlashFrames -= 1;
    }

    ctx.restore();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }
}

export async function playCutIn(characterId, {
  duration = CUT_IN_DURATION_MS,
  name = characterId,
  subtitle = "Habilidad especial",
} = {}) {
  const overlay = document.getElementById("cut-in");
  const image = document.getElementById("cut-in-image");
  const nameNode = document.getElementById("cut-in-name");
  const subtitleNode = document.getElementById("cut-in-subtitle");

  if (!overlay || !image || !nameNode || !subtitleNode) return;

  const src = cardUrl(characterId);
  try {
    await loadImage(src);
    image.src = src;
  } catch {
    image.removeAttribute("src");
  }

  image.alt = name;
  nameNode.textContent = name;
  subtitleNode.textContent = subtitle;

  overlay.classList.remove("is-active");
  void overlay.offsetWidth;
  overlay.classList.add("is-active");
  overlay.setAttribute("aria-hidden", "false");

  await new Promise((resolve) => window.setTimeout(resolve, duration));

  overlay.classList.remove("is-active");
  overlay.setAttribute("aria-hidden", "true");
}

export function getSpriteAssetContract() {
  return {
    directory: "assets/production/sprites/",
    size: SPRITE_SIZE,
    poses: [...POSES],
    cutInDurationMs: CUT_IN_DURATION_MS,
  };
}
