"use client";

import type { WorldSnapshot, AgentSnap, ThoughtSnap } from "@/lib/ws";

let Phaser: typeof import("phaser") | null = null;
let game: Phaser.Game | null = null;
let scene: ArenaScene | null = null;

// ── Agent colors by sprite kind ──────────────────────────────────────────────
const SPRITE_COLORS: Record<string, number> = {
  // Color names matching backend COLOR_OPTIONS
  red: 0xef4444,
  blue: 0x3b82f6,
  green: 0x22c55e,
  purple: 0xa855f7,
  orange: 0xf97316,
  cyan: 0x06b6d4,
  pink: 0xec4899,
  yellow: 0xeab308,
  teal: 0x14b8a6,
  indigo: 0x6366f1,
  // Legacy names for backward compat
  scholar: 0x5bc0eb,
  robot: 0xff6b6b,
  trickster: 0xc77dff,
  monk: 0xfde74c,
  cipher: 0x6bff95,
};

// ── Venue definitions ────────────────────────────────────────────────────────
type VenueDef = {
  x: number;
  y: number;
  w: number;
  h: number;
  fill: number;
  roof: number;
  accent: number;
  icon: string;
  label: string;
};

const W = 780;
const H = 560;

const VENUES: Record<string, VenueDef> = {
  workplace: {
    x: 80,
    y: 100,
    w: 160,
    h: 100,
    fill: 0x1c2e4a,
    roof: 0x2a4a7a,
    accent: 0x5bc0eb,
    icon: "\u{1F3ED}",
    label: "FACTORY",
  },
  bank: {
    x: 310,
    y: 70,
    w: 150,
    h: 90,
    fill: 0x1a1860,
    roof: 0x3030a0,
    accent: 0xfde74c,
    icon: "\u{1F3E6}",
    label: "BANK",
  },
  casino: {
    x: 560,
    y: 90,
    w: 160,
    h: 100,
    fill: 0x4a1028,
    roof: 0x8a2040,
    accent: 0xff4757,
    icon: "\u{1F3B0}",
    label: "CASINO",
  },
  marketplace: {
    x: 100,
    y: 340,
    w: 180,
    h: 100,
    fill: 0x1a3a28,
    roof: 0x2a6a3a,
    accent: 0x2ecc71,
    icon: "\u{1F3EA}",
    label: "MARKET",
  },
  lounge: {
    x: 400,
    y: 370,
    w: 160,
    h: 95,
    fill: 0x2a1a3a,
    roof: 0x4a2a6a,
    accent: 0xc77dff,
    icon: "\u{1F37B}",
    label: "LOUNGE",
  },
  alley: {
    x: 640,
    y: 400,
    w: 120,
    h: 85,
    fill: 0x1a0a0a,
    roof: 0x2a1515,
    accent: 0xff4444,
    icon: "\u{1F5E1}",
    label: "ALLEY",
  },
};

const ACTION_VENUE: Record<string, string> = {
  work: "workplace",
  trade: "marketplace",
  bet: "casino",
  socialize: "lounge",
  sabotage: "alley",
  invest: "bank",
  steal: "alley",
  lend: "marketplace",
  charity: "marketplace",
  propose_deal: "lounge",
  skip: "workplace",
  slander: "alley",
  vouch: "lounge",
  gift: "marketplace",
  bluff: "lounge",
  extort: "alley",
  strike: "workplace",
  rest: "lounge",
  will: "bank",
  gaslight: "alley",
  bribe: "marketplace",
};

// ── Agent visual state ───────────────────────────────────────────────────────
type AgentVisual = {
  container: any;
  label: any;
  bubble: any;
};

// ── The Arena Scene ──────────────────────────────────────────────────────────
class ArenaScene {
  private sceneRef: any = null;
  private agents: Record<string, AgentVisual> = {};
  private knownAgentIds: Set<string> = new Set();

  get ready() {
    return this.sceneRef !== null;
  }

  attach(s: any) {
    this.sceneRef = s;
    this.drawWorld();
  }

  /** Remove all agent sprites -- called on reconfigure */
  clearAgents() {
    for (const [id, vis] of Object.entries(this.agents)) {
      vis.container?.destroy();
      vis.label?.destroy();
      if (vis.bubble) vis.bubble.destroy();
    }
    this.agents = {};
    this.knownAgentIds.clear();
  }

  // ── World drawing ────────────────────────────────────────────────────────
  private drawWorld() {
    const s = this.sceneRef;
    const g = s.add.graphics();

    // Sky gradient (dark blue to darker)
    g.fillStyle(0x0a0a1e, 1);
    g.fillRect(0, 0, W, H);

    // Stars
    for (let i = 0; i < 60; i++) {
      const sx = Math.random() * W;
      const sy = Math.random() * H * 0.5;
      const brightness = Math.random() * 0.5 + 0.2;
      g.fillStyle(0xffffff, brightness);
      g.fillCircle(sx, sy, Math.random() * 1.2 + 0.3);
    }

    // Ground
    g.fillStyle(0x151520, 1);
    g.fillRect(0, H * 0.45, W, H * 0.55);

    // Ground grid lines (subtle)
    g.lineStyle(1, 0xffffff, 0.03);
    for (let y = H * 0.45; y < H; y += 30) {
      g.lineBetween(0, y, W, y);
    }

    // Paths between venues (dirt roads)
    g.lineStyle(3, 0x2a2a3a, 0.4);
    const vk = Object.keys(VENUES);
    for (let i = 0; i < vk.length; i++) {
      for (let j = i + 1; j < vk.length; j++) {
        const a = VENUES[vk[i]];
        const b = VENUES[vk[j]];
        const dist = Math.hypot(a.x - b.x, a.y - b.y);
        if (dist < 350) {
          g.lineBetween(a.x, a.y + a.h / 2, b.x, b.y + b.h / 2);
        }
      }
    }

    // Draw venue buildings
    for (const v of Object.values(VENUES)) {
      this.drawBuilding(s, v);
    }
  }

  private drawBuilding(s: any, v: VenueDef) {
    const g = s.add.graphics();
    const left = v.x - v.w / 2;
    const top = v.y - v.h / 2;

    // Shadow
    g.fillStyle(0x000000, 0.3);
    g.fillRect(left + 4, top + 4, v.w, v.h);

    // Main building body
    g.fillStyle(v.fill, 1);
    g.fillRect(left, top, v.w, v.h);

    // Roof (triangle)
    g.fillStyle(v.roof, 1);
    g.fillTriangle(
      left - 8,
      top,
      v.x,
      top - 25,
      left + v.w + 8,
      top,
    );

    // Roof accent line
    g.lineStyle(2, v.accent, 0.8);
    g.lineBetween(left - 8, top, v.x, top - 25);
    g.lineBetween(v.x, top - 25, left + v.w + 8, top);

    // Windows (grid of small lit squares)
    const cols = Math.floor(v.w / 28);
    const rows = Math.floor(v.h / 28);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const wx = left + 14 + c * 28;
        const wy = top + 14 + r * 28;
        const lit = Math.random() > 0.3;
        g.fillStyle(lit ? 0xfff9c4 : 0x1a1a2e, lit ? 0.6 : 0.3);
        g.fillRect(wx, wy, 12, 12);
        g.lineStyle(1, 0x000000, 0.4);
        g.strokeRect(wx, wy, 12, 12);
      }
    }

    // Door
    g.fillStyle(v.accent, 0.3);
    g.fillRect(v.x - 8, top + v.h - 20, 16, 20);
    g.lineStyle(1, v.accent, 0.6);
    g.strokeRect(v.x - 8, top + v.h - 20, 16, 20);

    // Building outline
    g.lineStyle(1.5, v.accent, 0.5);
    g.strokeRect(left, top, v.w, v.h);

    // Label with glow effect
    const label = s.add.text(v.x, top - 32, v.label, {
      fontSize: "11px",
      color: "#" + v.accent.toString(16).padStart(6, "0"),
      fontStyle: "bold",
      align: "center",
    });
    label.setOrigin(0.5, 0.5);
    label.setAlpha(0.9);

    // Icon above label
    const icon = s.add.text(v.x, top - 46, v.icon, {
      fontSize: "14px",
    });
    icon.setOrigin(0.5, 0.5);
  }

  // ── Agent sprites ────────────────────────────────────────────────────────

  private createAgentSprite(
    x: number,
    y: number,
    color: number,
    name: string,
  ): any {
    const s = this.sceneRef;
    const container = s.add.container(x, y);

    // Feet
    const footL = s.add.ellipse(-4, 14, 6, 4, 0x222222);
    const footR = s.add.ellipse(4, 14, 6, 4, 0x222222);

    // Body (rounded rectangle via ellipse)
    const body = s.add.ellipse(0, 2, 18, 22, color);
    body.setStrokeStyle(1.5, this.darken(color, 0.4));

    // Head
    const head = s.add.circle(0, -12, 8, color);
    head.setStrokeStyle(1.5, this.darken(color, 0.4));

    // Face highlight
    const highlight = s.add.ellipse(2, -14, 4, 3, 0xffffff);
    highlight.setAlpha(0.2);

    // Eyes
    const eyeL = s.add.circle(-3, -13, 2.5, 0xffffff);
    const eyeR = s.add.circle(3, -13, 2.5, 0xffffff);
    const pupilL = s.add.circle(-2.5, -13, 1.2, 0x111111);
    const pupilR = s.add.circle(3.5, -13, 1.2, 0x111111);

    // Mouth (small smile)
    const mouth = s.add.graphics();
    mouth.lineStyle(1, 0x333333, 0.6);
    mouth.beginPath();
    mouth.arc(0, -8, 3, 0.2, Math.PI - 0.2, false);
    mouth.strokePath();

    // Arms
    const armL = s.add.ellipse(-12, 2, 5, 12, this.darken(color, 0.15));
    const armR = s.add.ellipse(12, 2, 5, 12, this.darken(color, 0.15));

    // Name tag background
    const nameTag = s.add.graphics();
    nameTag.fillStyle(0x000000, 0.6);
    nameTag.fillRoundedRect(-22, 18, 44, 12, 3);

    // Name text
    const nameText = s.add.text(0, 24, name, {
      fontSize: "7px",
      color: "#ffffff",
      fontStyle: "bold",
      align: "center",
    });
    nameText.setOrigin(0.5, 0.5);

    container.add([
      footL,
      footR,
      armL,
      armR,
      body,
      head,
      highlight,
      eyeL,
      eyeR,
      pupilL,
      pupilR,
      mouth,
      nameTag,
      nameText,
    ]);
    container.setSize(40, 50);
    return container;
  }

  private darken(color: number, factor: number): number {
    const r = Math.floor(((color >> 16) & 0xff) * (1 - factor));
    const g = Math.floor(((color >> 8) & 0xff) * (1 - factor));
    const b = Math.floor((color & 0xff) * (1 - factor));
    return (r << 16) | (g << 8) | b;
  }

  // ── Venue position computation ───────────────────────────────────────────

  private getVenuePosition(
    venueName: string,
    index: number,
    totalAtVenue: number,
    spouse?: string | null,
  ): [number, number] {
    const venue = VENUES[venueName] || VENUES.workplace;
    const maxSpread = venue.w - 50;
    const spread = Math.min(32, maxSpread / Math.max(totalAtVenue, 1));
    const startX = venue.x - ((totalAtVenue - 1) * spread) / 2;
    let x = startX + index * spread;
    const y = venue.y + venue.h / 2 - 10;

    if (spouse) {
      x += index % 2 === 0 ? -4 : 4;
    }
    return [x, y];
  }

  // ── Upsert agent ─────────────────────────────────────────────────────────

  upsertSprite(
    agent: AgentSnap,
    targetVenue: string,
    venueIndex: number,
    totalAtVenue: number,
  ) {
    if (!this.sceneRef) return;
    const s = this.sceneRef;
    const color = SPRITE_COLORS[agent.sprite] || 0xaaaaaa;
    let vis = this.agents[agent.agent_id];
    this.knownAgentIds.add(agent.agent_id);

    if (!vis) {
      const venue = VENUES[targetVenue] || VENUES.workplace;
      const container = this.createAgentSprite(
        venue.x,
        venue.y,
        color,
        agent.display_name,
      );

      // Balance label (separate from container for independent positioning)
      const label = s.add.text(venue.x, venue.y + 36, "", {
        fontSize: "8px",
        color: "#7df9ff",
        fontStyle: "bold",
        align: "center",
        backgroundColor: "#00000088",
        padding: { x: 3, y: 1 },
      });
      label.setOrigin(0.5, 0);

      vis = { container, label, bubble: null };
      this.agents[agent.agent_id] = vis;
    }

    if (!agent.alive) {
      vis.container.setAlpha(0.12);
      vis.label.setAlpha(0.12);
      vis.label.setText("DEAD");
      return;
    }

    vis.container.setAlpha(1);
    vis.label.setAlpha(1);
    vis.label.setText(`$${agent.balance.toFixed(2)}`);

    const [tx, ty] = this.getVenuePosition(
      targetVenue,
      venueIndex,
      totalAtVenue,
      agent.spouse,
    );

    // Kill existing tweens
    s.tweens.killTweensOf(vis.container);
    s.tweens.killTweensOf(vis.label);

    // Movement
    s.tweens.add({
      targets: vis.container,
      x: tx,
      y: ty,
      duration: 650,
      ease: "Quad.easeInOut",
    });

    s.tweens.add({
      targets: vis.label,
      x: tx,
      y: ty + 36,
      duration: 650,
      ease: "Quad.easeInOut",
    });

    // Idle bobbing (starts after movement completes)
    s.tweens.add({
      targets: vis.container,
      y: ty - 2,
      duration: 1500 + Math.random() * 500,
      ease: "Sine.easeInOut",
      yoyo: true,
      repeat: -1,
      delay: 700,
    });
  }

  // ── Thought bubbles ──────────────────────────────────────────────────────

  showThought(agentId: string, text: string) {
    if (!this.sceneRef) return;
    const s = this.sceneRef;
    const vis = this.agents[agentId];
    if (!vis) return;
    if (vis.bubble) vis.bubble.destroy();

    const container = s.add.container(
      vis.container.x + 15,
      vis.container.y - 35,
    );

    // Bubble background
    const bg = s.add.graphics();
    const trimmed = text.slice(0, 45);
    const bw = Math.min(150, trimmed.length * 5 + 16);
    bg.fillStyle(0xffffff, 0.92);
    bg.fillRoundedRect(-4, -4, bw, 18, 4);
    // Tail triangle
    bg.fillTriangle(-2, 14, 4, 18, 8, 14);

    const txt = s.add.text(0, 0, trimmed, {
      fontSize: "7px",
      color: "#111111",
      wordWrap: { width: 140 },
    });

    container.add([bg, txt]);
    vis.bubble = container;

    s.tweens.add({
      targets: container,
      alpha: 0,
      y: container.y - 8,
      duration: 600,
      delay: 2200,
      ease: "Quad.easeIn",
      onComplete: () => container.destroy(),
    });
  }
}

// ── Public API ──────────────────────────────────────────────────────────────

export function ensureGame(parent: HTMLElement): any {
  if (game) return game;
  try {
    if (!Phaser) {
      const mod = require("phaser");
      Phaser = mod.default || mod;
    }
    scene = new ArenaScene();
    const config: any = {
      type: (Phaser as any).AUTO,
      parent,
      width: W,
      height: H,
      backgroundColor: "#0a0a1e",
      pixelArt: true,
      scene: {
        create() {
          scene!.attach(this);
        },
      },
    };
    game = new (Phaser as any).Game(config);
    return game;
  } catch (err) {
    console.error("[Arena] Phaser init failed:", err);
    return null;
  }
}

/** Track the set of agent IDs from the last snapshot to detect roster changes */
let _lastRosterKey = "";

export function syncSnapshot(snapshot: WorldSnapshot) {
  if (!scene || !scene.ready) return;
  try {
    // Detect roster change: if the set of agent_ids changed, clear old sprites
    const currentIds = snapshot.agents
      .map((a) => a.agent_id)
      .sort()
      .join(",");
    if (_lastRosterKey && _lastRosterKey !== currentIds) {
      scene.clearAgents();
    }
    _lastRosterKey = currentIds;

    // Build action map from recent thoughts
    const latestAction = new Map<string, string>();
    const latestThought = new Map<string, ThoughtSnap>();
    for (const t of snapshot.recent_thoughts) {
      if (!latestAction.has(t.agent_id)) {
        latestAction.set(t.agent_id, t.action);
        latestThought.set(t.agent_id, t);
      }
    }

    // Group alive agents by venue
    const venueAgents: Record<string, AgentSnap[]> = {};
    for (const agent of snapshot.agents) {
      if (!agent.alive) continue;
      const action = latestAction.get(agent.agent_id) || "work";
      const venue = ACTION_VENUE[action] || "workplace";
      if (!venueAgents[venue]) venueAgents[venue] = [];
      venueAgents[venue].push(agent);
    }

    // Married agent venue tracking
    const spouseVenue = new Map<string, string>();
    for (const agent of snapshot.agents) {
      if (agent.alive && agent.spouse) {
        const myAction = latestAction.get(agent.agent_id) || "work";
        spouseVenue.set(
          agent.agent_id,
          ACTION_VENUE[myAction] || "workplace",
        );
      }
    }

    // Update each agent
    for (const agent of snapshot.agents) {
      let targetVenue: string;
      if (!agent.alive) {
        targetVenue = "workplace";
      } else if (agent.spouse && spouseVenue.has(agent.spouse)) {
        const myVenue =
          ACTION_VENUE[latestAction.get(agent.agent_id) || "work"] ||
          "workplace";
        const theirVenue = spouseVenue.get(agent.spouse) || "workplace";
        targetVenue = agent.agent_id < agent.spouse ? myVenue : theirVenue;
      } else {
        const action = latestAction.get(agent.agent_id) || "work";
        targetVenue = ACTION_VENUE[action] || "workplace";
      }

      const agentsAtVenue = venueAgents[targetVenue] || [agent];
      const index = agentsAtVenue.findIndex(
        (a) => a.agent_id === agent.agent_id,
      );
      scene.upsertSprite(
        agent,
        targetVenue,
        Math.max(0, index),
        agentsAtVenue.length,
      );
    }

    // Thought bubbles
    latestThought.forEach((t, agentId) =>
      scene!.showThought(agentId, t.monologue || t.action),
    );
  } catch (err) {
    console.error("[Arena] syncSnapshot failed:", err);
  }
}
