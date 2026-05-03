'use client';

import type { WorldSnapshot } from '@/lib/ws';

// We import Phaser dynamically so SSR doesn't choke on `window`.
let Phaser: typeof import('phaser') | null = null;
let game: Phaser.Game | null = null;
let scene: ArenaScene | null = null;

const SPRITE_COLORS: Record<string, number> = {
  scholar: 0x7df9ff, // ATLAS
  robot: 0xff6b6b,   // NOVA
  trickster: 0xc77dff, // HYDRA
  monk: 0xfff36b,    // SAGE
  cipher: 0x6bff95,  // CIPHER
};

const POS_GRID: Record<string, [number, number]> = {
  atlas: [180, 220],
  nova: [380, 160],
  hydra: [560, 260],
  sage: [280, 360],
  cipher: [500, 400],
};

class ArenaScene {
  private sceneRef: any = null;
  private sprites: Record<string, any> = {};
  private labels: Record<string, any> = {};
  private bubbles: Record<string, any> = {};

  get ready() { return this.sceneRef !== null; }

  attach(s: any) {
    this.sceneRef = s;
    this.drawTown();
  }

  private drawTown() {
    const s = this.sceneRef;
    s.add.rectangle(360, 280, 720, 560, 0x1a1a2e); // ground
    // Bank
    s.add.rectangle(120, 100, 140, 80, 0x4a3aff).setStrokeStyle(2, 0x7df9ff);
    s.add.text(60, 90, 'BANK', { fontSize: '14px', color: '#7df9ff' });
    // Casino
    s.add.rectangle(600, 100, 140, 80, 0xff3a6b).setStrokeStyle(2, 0xfff36b);
    s.add.text(550, 90, 'CASINO', { fontSize: '14px', color: '#fff36b' });
    // Lounge
    s.add.rectangle(360, 480, 200, 80, 0x3aff7d).setStrokeStyle(2, 0xc77dff);
    s.add.text(320, 470, 'LOUNGE', { fontSize: '14px', color: '#c77dff' });
  }

  upsertSprite(agent: WorldSnapshot['agents'][number]) {
    if (!this.sceneRef) return;
    const s = this.sceneRef;
    const [x, y] = POS_GRID[agent.agent_id] || [360, 280];
    const color = SPRITE_COLORS[agent.sprite] || 0xffffff;
    let body = this.sprites[agent.agent_id];
    if (!body) {
      body = s.add.rectangle(x, y, 18, 24, color).setStrokeStyle(2, 0x000000);
      this.sprites[agent.agent_id] = body;
      this.labels[agent.agent_id] = s.add.text(x - 24, y + 18, agent.display_name, {
        fontSize: '10px',
        color: '#ffffff',
      });
    }
    body.setVisible(agent.alive);
    this.labels[agent.agent_id].setVisible(agent.alive);
    this.labels[agent.agent_id].setText(`${agent.display_name} $${agent.balance.toFixed(2)}`);
    if (!agent.alive) body.setAlpha(0.2);
  }

  showThought(agentId: string, text: string) {
    if (!this.sceneRef) return;
    const s = this.sceneRef;
    const body = this.sprites[agentId];
    if (!body) return;
    if (this.bubbles[agentId]) this.bubbles[agentId].destroy();
    const bubble = s.add.text(body.x + 12, body.y - 28, text.slice(0, 60), {
      fontSize: '9px',
      color: '#000000',
      backgroundColor: '#ffffffaa',
      padding: { x: 4, y: 2 },
      wordWrap: { width: 180 },
    });
    this.bubbles[agentId] = bubble;
    s.time.delayedCall(2200, () => bubble.destroy());
  }
}

export function ensureGame(parent: HTMLElement): any {
  if (game) return game;
  try {
    if (!Phaser) {
      const mod = require('phaser');
      Phaser = mod.default || mod;
    }
    scene = new ArenaScene();
    const config: any = {
      type: (Phaser as any).AUTO,
      parent,
      width: 720,
      height: 560,
      backgroundColor: '#0f0f1a',
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
    console.error('[Arena] Phaser init failed:', err);
    return null;
  }
}

export function syncSnapshot(snapshot: WorldSnapshot) {
  if (!scene || !scene.ready) return;
  try {
    for (const agent of snapshot.agents) {
      scene.upsertSprite(agent);
    }
    // Pop a thought bubble for the latest action of each agent
    const latestPerAgent = new Map<string, WorldSnapshot['recent_thoughts'][number]>();
    for (const t of snapshot.recent_thoughts) {
      if (!latestPerAgent.has(t.agent_id)) latestPerAgent.set(t.agent_id, t);
    }
    latestPerAgent.forEach((t, agentId) => scene!.showThought(agentId, t.monologue || t.action));
  } catch (err) {
    console.error('[Arena] syncSnapshot failed:', err);
  }
}
