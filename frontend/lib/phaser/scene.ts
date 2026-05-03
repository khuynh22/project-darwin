"use client";

import type { WorldSnapshot, AgentSnap, ThoughtSnap } from "@/lib/ws";

// We import Phaser dynamically so SSR doesn't choke on `window`.
let Phaser: typeof import("phaser") | null = null;
let game: Phaser.Game | null = null;
let scene: ArenaScene | null = null;

const SPRITE_COLORS: Record<string, number> = {
  scholar: 0x7df9ff,
  robot: 0xff6b6b,
  trickster: 0xc77dff,
  monk: 0xfff36b,
  cipher: 0x6bff95,
  knight: 0xff9f43,
  rogue: 0xe74c3c,
  healer: 0x2ecc71,
  mage: 0x9b59b6,
  ranger: 0x1abc9c,
};

// --- Venue definitions ---
type VenueDef = {
  x: number;
  y: number;
  w: number;
  h: number;
  color: number;
  border: number;
  label: string;
};

const VENUES: Record<string, VenueDef> = {
  workplace: {
    x: 110,
    y: 110,
    w: 150,
    h: 90,
    color: 0x1e2d4a,
    border: 0x7df9ff,
    label: "WORKPLACE",
  },
  bank: {
    x: 360,
    y: 80,
    w: 130,
    h: 75,
    color: 0x2a2080,
    border: 0x7df9ff,
    label: "BANK",
  },
  casino: {
    x: 610,
    y: 110,
    w: 140,
    h: 90,
    color: 0x5c1a2a,
    border: 0xfff36b,
    label: "CASINO",
  },
  marketplace: {
    x: 160,
    y: 340,
    w: 170,
    h: 95,
    color: 0x1a3a2a,
    border: 0x6bff95,
    label: "MARKET",
  },
  lounge: {
    x: 440,
    y: 380,
    w: 160,
    h: 90,
    color: 0x2a1a3a,
    border: 0xc77dff,
    label: "LOUNGE",
  },
  alley: {
    x: 630,
    y: 430,
    w: 120,
    h: 80,
    color: 0x1a0a0a,
    border: 0xff4444,
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
};

type AgentVisual = {
  container: any;
  body: any;
  head: any;
  eyeL: any;
  eyeR: any;
  label: any;
  bubble: any;
};

class ArenaScene {
  private sceneRef: any = null;
  private agents: Record<string, AgentVisual> = {};
  private venueGlow: Record<string, any> = {};

  get ready() {
    return this.sceneRef !== null;
  }

  attach(s: any) {
    this.sceneRef = s;
    this.drawTown();
  }

  private drawTown() {
    const s = this.sceneRef;
    // Background
    s.add.rectangle(360, 280, 720, 560, 0x0f0f1a);

    // Draw venues
    for (const [key, v] of Object.entries(VENUES)) {
      // Venue background with rounded corners (approximated with rectangle)
      const rect = s.add
        .rectangle(v.x, v.y, v.w, v.h, v.color)
        .setStrokeStyle(1.5, v.border)
        .setAlpha(0.7);
      this.venueGlow[key] = rect;

      // Venue label
      s.add
        .text(v.x - v.w / 2 + 8, v.y - v.h / 2 + 4, v.label, {
          fontSize: "10px",
          color: "#" + v.border.toString(16).padStart(6, "0"),
          fontStyle: "bold",
        })
        .setAlpha(0.8);
    }

    // Subtle connecting paths between venues (decorative)
    const g = s.add.graphics();
    g.lineStyle(1, 0xffffff, 0.05);
    const venueKeys = Object.keys(VENUES);
    for (let i = 0; i < venueKeys.length; i++) {
      for (let j = i + 1; j < venueKeys.length; j++) {
        const a = VENUES[venueKeys[i]];
        const b = VENUES[venueKeys[j]];
        g.lineBetween(a.x, a.y, b.x, b.y);
      }
    }
  }

  private createAgentSprite(x: number, y: number, color: number): any {
    const s = this.sceneRef;
    const container = s.add.container(x, y);

    // Body (rectangle with slight depth effect)
    const body = s.add
      .rectangle(0, 2, 14, 18, color)
      .setStrokeStyle(1, 0x000000);

    // Head (circle)
    const head = s.add.circle(0, -10, 6, color).setStrokeStyle(1, 0x000000);

    // Eyes
    const eyeL = s.add.circle(-2, -11, 1.2, 0xffffff);
    const eyeR = s.add.circle(2, -11, 1.2, 0xffffff);

    // Pupils
    const pupilL = s.add.circle(-2, -11, 0.5, 0x000000);
    const pupilR = s.add.circle(2, -11, 0.5, 0x000000);

    container.add([body, head, eyeL, eyeR, pupilL, pupilR]);
    return { container, body, head, eyeL, eyeR };
  }

  private getVenuePosition(
    venueName: string,
    index: number,
    totalAtVenue: number,
    spouse?: string | null,
  ): [number, number] {
    const venue = VENUES[venueName] || VENUES.workplace;
    // Spread agents horizontally within the venue
    const spread = Math.min(28, (venue.w - 30) / Math.max(totalAtVenue, 1));
    const startX = venue.x - ((totalAtVenue - 1) * spread) / 2;
    let x = startX + index * spread;
    const y = venue.y + 8; // slightly below venue center

    // Married agents get pulled closer together
    if (spouse) {
      x += index % 2 === 0 ? -5 : 5;
    }
    return [x, y];
  }

  upsertSprite(
    agent: AgentSnap,
    targetVenue: string,
    venueIndex: number,
    totalAtVenue: number,
  ) {
    if (!this.sceneRef) return;
    const s = this.sceneRef;
    const color = SPRITE_COLORS[agent.sprite] || 0xffffff;
    let vis = this.agents[agent.agent_id];

    if (!vis) {
      // Initial position at venue center
      const venue = VENUES[targetVenue] || VENUES.workplace;
      const parts = this.createAgentSprite(venue.x, venue.y, color);
      const label = s.add.text(venue.x - 20, venue.y + 18, agent.display_name, {
        fontSize: "8px",
        color: "#ffffff",
        fontStyle: "bold",
      });
      vis = { ...parts, label, bubble: null };
      this.agents[agent.agent_id] = vis;
    }

    if (!agent.alive) {
      vis.container.setAlpha(0.15);
      vis.label.setAlpha(0.15);
      vis.label.setText(`${agent.display_name} DEAD`);
      return;
    }

    vis.container.setAlpha(1);
    vis.label.setAlpha(1);
    vis.label.setText(`${agent.display_name} $${agent.balance.toFixed(2)}`);

    // Animate movement to target venue position
    const [tx, ty] = this.getVenuePosition(
      targetVenue,
      venueIndex,
      totalAtVenue,
      agent.spouse,
    );

    // Kill existing tweens to prevent stacking
    s.tweens.killTweensOf(vis.container);
    s.tweens.killTweensOf(vis.label);

    s.tweens.add({
      targets: vis.container,
      x: tx,
      y: ty,
      duration: 600,
      ease: "Quad.easeInOut",
    });

    s.tweens.add({
      targets: vis.label,
      x: tx - 20,
      y: ty + 18,
      duration: 600,
      ease: "Quad.easeInOut",
    });

    // Subtle bobbing idle animation
    s.tweens.add({
      targets: vis.container,
      y: ty - 2,
      duration: 1200,
      ease: "Sine.easeInOut",
      yoyo: true,
      repeat: -1,
      delay: 700, // wait for movement to finish
    });
  }

  showThought(agentId: string, text: string) {
    if (!this.sceneRef) return;
    const s = this.sceneRef;
    const vis = this.agents[agentId];
    if (!vis) return;
    if (vis.bubble) vis.bubble.destroy();
    const bubble = s.add.text(
      vis.container.x + 10,
      vis.container.y - 30,
      text.slice(0, 50),
      {
        fontSize: "8px",
        color: "#000000",
        backgroundColor: "#ffffffcc",
        padding: { x: 3, y: 2 },
        wordWrap: { width: 140 },
      },
    );
    vis.bubble = bubble;
    // Fade out the bubble
    s.tweens.add({
      targets: bubble,
      alpha: 0,
      duration: 800,
      delay: 1800,
      onComplete: () => bubble.destroy(),
    });
  }
}

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
      width: 720,
      height: 560,
      backgroundColor: "#0f0f1a",
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

export function syncSnapshot(snapshot: WorldSnapshot) {
  if (!scene || !scene.ready) return;
  try {
    // Build a map of agentId -> latest action from recent_thoughts
    const latestAction = new Map<string, string>();
    const latestThought = new Map<string, ThoughtSnap>();
    for (const t of snapshot.recent_thoughts) {
      if (!latestAction.has(t.agent_id)) {
        latestAction.set(t.agent_id, t.action);
        latestThought.set(t.agent_id, t);
      }
    }

    // Group alive agents by their target venue
    const venueAgents: Record<string, AgentSnap[]> = {};
    for (const agent of snapshot.agents) {
      if (!agent.alive) continue;
      const action = latestAction.get(agent.agent_id) || "work";
      const venue = ACTION_VENUE[action] || "workplace";
      if (!venueAgents[venue]) venueAgents[venue] = [];
      venueAgents[venue].push(agent);
    }

    // Place married agents at the same venue
    const spouseVenue = new Map<string, string>();
    for (const agent of snapshot.agents) {
      if (agent.alive && agent.spouse) {
        const myAction = latestAction.get(agent.agent_id) || "work";
        const myVenue = ACTION_VENUE[myAction] || "workplace";
        spouseVenue.set(agent.agent_id, myVenue);
      }
    }

    // Update each agent
    for (const agent of snapshot.agents) {
      let targetVenue: string;
      if (!agent.alive) {
        targetVenue = "workplace";
      } else if (agent.spouse && spouseVenue.has(agent.spouse)) {
        // Follow spouse if married (use first alphabetically as "anchor")
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

    // Pop thought bubbles for latest action of each agent
    latestThought.forEach((t, agentId) =>
      scene!.showThought(agentId, t.monologue || t.action),
    );
  } catch (err) {
    console.error("[Arena] syncSnapshot failed:", err);
  }
}
