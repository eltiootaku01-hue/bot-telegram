const MAX_PARTICLES = 96;
const DEFAULT_PARTICLE_LIFE = 0.34;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function randomSign() {
  return Math.random() < 0.5 ? -1 : 1;
}

class Particle {
  constructor({
    x,
    y,
    vx,
    vy,
    life = DEFAULT_PARTICLE_LIFE,
    size = 2,
    growth = 0,
    drag = 0.94,
    alpha = 1,
    kind = "dot",
  }) {
    this.x = x;
    this.y = y;
    this.vx = vx;
    this.vy = vy;
    this.life = life;
    this.maxLife = life;
    this.size = size;
    this.growth = growth;
    this.drag = drag;
    this.alpha = alpha;
    this.kind = kind;
  }

  step(deltaSeconds) {
    this.x += this.vx * deltaSeconds;
    this.y += this.vy * deltaSeconds;
    const damping = Math.pow(this.drag, deltaSeconds * 60);
    this.vx *= damping;
    this.vy *= damping;
    this.size = Math.max(0, this.size + this.growth * deltaSeconds);
    this.life -= deltaSeconds;
    return this.life > 0;
  }

  draw(ctx) {
    const ratio = clamp(this.life / this.maxLife, 0, 1);
    const alpha = this.alpha * ratio;
    if (alpha <= 0 || this.size <= 0) return;

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = "#ff2a2a";
    ctx.strokeStyle = "#d9ff00";

    if (this.kind === "streak") {
      ctx.lineWidth = Math.max(1, this.size * 0.5);
      ctx.beginPath();
      ctx.moveTo(this.x, this.y);
      ctx.lineTo(this.x - this.vx * 0.035, this.y - this.vy * 0.035);
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }
}

export class LightweightCombatEffects {
  constructor({ maxParticles = MAX_PARTICLES } = {}) {
    this.maxParticles = Math.max(8, Math.min(maxParticles, MAX_PARTICLES));
    this.particles = [];
    this.flash = 0;
  }

  clear() {
    this.particles.length = 0;
    this.flash = 0;
  }

  burst(x, y, {
    count = 14,
    power = 1,
    size = 2.2,
    flash = 0.18,
  } = {}) {
    const room = Math.max(0, this.maxParticles - this.particles.length);
    const amount = Math.min(room, Math.max(1, Math.floor(count)));

    for (let index = 0; index < amount; index += 1) {
      const angle = (Math.PI * 2 * index / amount) + Math.random() * 0.28;
      const speed = (80 + Math.random() * 150) * power;
      this.particles.push(new Particle({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0.18 + Math.random() * 0.24,
        size: size * (0.7 + Math.random() * 0.7),
        growth: 3,
        kind: index % 3 === 0 ? "streak" : "dot",
      }));
    }

    this.flash = Math.max(this.flash, flash);
  }

  slash(x, y, {
    direction = 1,
    power = 1,
  } = {}) {
    const room = Math.max(0, this.maxParticles - this.particles.length);
    const amount = Math.min(room, 9);

    for (let index = 0; index < amount; index += 1) {
      const spread = (Math.random() - 0.5) * 0.9;
      this.particles.push(new Particle({
        x: x + spread * 18,
        y: y + (Math.random() - 0.5) * 18,
        vx: direction * (90 + Math.random() * 100) * power,
        vy: spread * 110,
        life: 0.16 + Math.random() * 0.14,
        size: 2 + Math.random() * 1.5,
        growth: 1,
        kind: "streak",
      }));
    }
  }

  step(deltaSeconds) {
    const delta = Math.min(0.05, Math.max(0, deltaSeconds));
    this.particles = this.particles.filter((particle) => particle.step(delta));
    this.flash = Math.max(0, this.flash - delta * 1.8);
  }

  draw(ctx) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const particle of this.particles) {
      particle.draw(ctx);
    }

    if (this.flash > 0) {
      ctx.globalAlpha = Math.min(0.35, this.flash);
      ctx.fillStyle = "#ff2a2a";
      ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    }
    ctx.restore();
  }

  get active() {
    return this.particles.length > 0 || this.flash > 0;
  }
}

export function deterministicScrapBurst(seed = 0) {
  const value = Math.abs(Number(seed) || 0);
  return {
    count: 10 + (value % 8),
    power: 0.8 + (value % 5) * 0.08,
  };
}
