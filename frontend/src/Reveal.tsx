/* Screen 3 — Creation Reveal (spec §17, §7 REVEAL). The record lands first; the
   hero render resolves inside the fusion animation, so we poll image_status. */
import { useEffect, useRef, useState } from "react";
import type { Go } from "./App";
import { api, type CreatureDetail } from "./api";
import { Asset, Badge, Btn, Loading, Panel, RarityBadge, Stage, StatRow } from "./ui";

const POLL_MS = 1500;

export function Reveal({ go, creatureId }: { go: Go; creatureId: number }) {
  const [creature, setCreature] = useState<CreatureDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const row = await api.getCreature(creatureId);
        if (cancelled) return;
        setCreature(row);
        if (row.image_status === "pending") {
          timer.current = setTimeout(poll, POLL_MS) as unknown as number;
        }
      } catch {
        if (!cancelled) setError("That chimera could not be found.");
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [creatureId]);

  if (error) return <div className="error">{error}</div>;
  if (!creature) return <Loading label="OPENING THE FUSION CHAMBER" />;

  const rendering = creature.image_status === "pending";

  return (
    <div className="reveal">
      <section className="reveal__hero">
        <div className="reveal__intro">
          <p className="eyebrow">NEW CHIMERA</p>
          <h1 className="display display--xl">CREATED!</h1>
          <div className="rule" />
          <p className="lede">Your fusion is complete. A brand new chimera is born!</p>

          <h2 className="reveal__name">{creature.name.toUpperCase()}</h2>
          <div className="reveal__badges">
            <RarityBadge rarity={creature.rarity} />
            {creature.image_status === "failed" && <Badge tone="red">ART PENDING</Badge>}
          </div>
          <p className="reveal__role">{creature.role || creature.title}</p>
        </div>

        <Stage creature={creature} fusing={rendering} caption="RENDERING" />

        <div className="reveal__side">
          <Panel title="TOP FACTS" accent="cyan">
            {creature.strengths.map((s, i) => (
              <div className="fact" key={`s${i}`}>
                <Asset slot={`icons/fact_strength`} label="" className="fact__icon" />
                <div>
                  <div className="fact__title">STRENGTH</div>
                  <div className="fact__blurb">{s}</div>
                </div>
              </div>
            ))}
            <div className="fact">
              <Asset slot="icons/fact_fun" label="" className="fact__icon" />
              <div>
                <div className="fact__title">DID YOU KNOW</div>
                <div className="fact__blurb">{creature.fun_fact}</div>
              </div>
            </div>
          </Panel>

          <Panel title="AWESOME ABILITIES" accent="purple">
            {creature.abilities.map((a) => (
              <div className="ability" key={a.name}>
                <Asset slot={`icons/ability`} label="" className="ability__icon" />
                <div>
                  <div className="ability__name">{a.name.toUpperCase()}</div>
                  <div className="ability__blurb">{a.blurb}</div>
                </div>
              </div>
            ))}
          </Panel>
        </div>
      </section>

      <section className="reveal__lower">
        <Panel title="FUSED FROM" accent="cyan">
          <div className="fused">
            {creature.sources.map((slug, i) => (
              <div className="fused__item" key={slug}>
                {i > 0 && <span className="fused__plus">+</span>}
                <Asset slot={`sources/${slug}`} label={slug} className="fused__art" />
                <span className="fused__name">{slug.replace(/[_-]/g, " ").toUpperCase()}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="CHIMERA STATS" accent="teal">
          <StatRow stats={creature.core_stats} />
        </Panel>

        <Panel title="WATCH OUT FOR" accent="gold">
          <ul className="bullets">
            {creature.weaknesses.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Panel>
      </section>

      <footer className="reveal__foot">
        <Btn accent="purple" size="lg" onClick={() => go({ name: "codex", id: creature.id })}>
          ADD TO CODEX
        </Btn>
        <Btn accent="cyan" size="lg" onClick={() => go({ name: "lab" })}>
          MAKE ANOTHER
        </Btn>
        <Btn accent="gold" size="lg" onClick={() => go({ name: "arena" })}>
          ENTER BRACKET
        </Btn>
      </footer>
    </div>
  );
}
