/* Summon New Creature — the holo-modal over the Fusion Lab (spec: hybrid
   library, ARCHITECTURE.md). Henry types ANY animal; the backend either
   matches it into the library, asks "did you mean?", conjures a brand-new
   part (portrait paints in the background), or answers with a kind, playful
   redirect. Purple/fusion treatment throughout — this is creation magic,
   clearly not a library browse. */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, refreshLibrary, type SourceCreature } from "./api";
import { Asset, Btn, FitText, PartImg } from "./ui";

type State =
  | { kind: "idle" }
  | { kind: "busy"; query: string }
  | { kind: "disambiguate"; candidates: SourceCreature[] }
  | { kind: "conjuring"; source: SourceCreature }
  | { kind: "redirect"; message: string };

const CATEGORY_TINT: Record<string, "purple" | "gold" | "teal"> = {
  mythic: "purple",
  extinct: "gold",
  living: "teal",
};

export function SummonModal({
  initialQuery = "",
  onClose,
  onMatched,
  onConjured,
}: {
  initialQuery?: string;
  onClose: () => void;
  /** An existing part resolved — the lab flies it into the active slot. */
  onMatched: (source: SourceCreature) => void;
  /** A brand-new part landed — the lab adds it to the rail AND the slot. */
  onConjured: (source: SourceCreature) => void;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [state, setState] = useState<State>({ kind: "idle" });
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (state.kind === "idle" || state.kind === "redirect") inputRef.current?.focus();
  }, [state.kind]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setState({ kind: "busy", query: q });
    try {
      const res = await api.summon(q);
      if (res.status === "matched" && res.source) {
        onMatched(res.source);
        onClose();
      } else if (res.status === "disambiguate" && res.candidates.length) {
        setState({ kind: "disambiguate", candidates: res.candidates.slice(0, 3) });
      } else if (res.status === "conjured" && res.source) {
        onConjured(res.source);
        refreshLibrary().catch(() => {});
        setState({ kind: "conjuring", source: res.source });
      } else {
        setState({
          kind: "redirect",
          message:
            res.message ||
            "The summoning circle only answers to creatures — try any animal you can think of!",
        });
      }
    } catch (e) {
      setState({
        kind: "redirect",
        message:
          e instanceof ApiError && e.status < 500
            ? e.message
            : "The summoning circle flickered! Take a breath and try again.",
      });
    }
  }, [query, onClose, onMatched, onConjured]);

  const busy = state.kind === "busy";

  return (
    <div className="summon-overlay" onClick={onClose} role="presentation">
      <div
        className="panel panel--purple summon-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Summon a new creature"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="panel__head">
          <h2>
            <Asset slot="icons/nav_fusion" label="" className="panel__icon" tint="purple" />
            SUMMON NEW CREATURE
          </h2>
          <button type="button" className="summon-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        <div className="panel__body summon-body">
          {state.kind === "conjuring" ? (
            <div className="summon-conjuring">
              <div className="summon-circle" aria-hidden="true">
                <span className="summon-circle__ring" />
                <span className="summon-circle__ring summon-circle__ring--slow" />
                <span className="summon-circle__core" />
              </div>
              <div className="summon-conjuring__name">
                <FitText className="summon-conjuring__title">
                  {state.source.name.toUpperCase()}
                </FitText>
                <span className="summon-conjuring__sub">ANSWERED THE CALL</span>
              </div>
              <p className="summon-conjuring__line">{state.source.blurb}</p>
              <p className="summon-conjuring__note">
                It is already in your build — its portrait is being painted right now!
              </p>
              <Btn accent="purple" size="lg" onClick={onClose}>
                KEEP BUILDING
              </Btn>
            </div>
          ) : state.kind === "disambiguate" ? (
            <div className="summon-choice">
              <p className="summon-lead">DID YOU MEAN…</p>
              <div className="summon-cands">
                {state.candidates.map((c) => (
                  <button
                    key={c.slug}
                    type="button"
                    className="summon-cand"
                    onClick={() => {
                      onMatched(c);
                      onClose();
                    }}
                  >
                    <span className="summon-cand__art">
                      <PartImg source={c} />
                    </span>
                    <span className="summon-cand__plate">
                      <Asset
                        slot={`icons/cat_${c.category}`}
                        label=""
                        className="summon-cand__cat"
                        tint={CATEGORY_TINT[c.category] ?? "teal"}
                      />
                      <FitText className="summon-cand__name">{c.name.toUpperCase()}</FitText>
                    </span>
                  </button>
                ))}
              </div>
              <Btn accent="ghost" onClick={() => setState({ kind: "idle" })}>
                NEITHER — TYPE ANOTHER
              </Btn>
            </div>
          ) : (
            <form
              className="summon-form"
              onSubmit={(e) => {
                e.preventDefault();
                submit();
              }}
            >
              {state.kind === "redirect" && (
                <p className="summon-redirect">{state.message}</p>
              )}
              <label className="summon-input">
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  maxLength={80}
                  disabled={busy}
                  placeholder="Type any animal — real, extinct, or legendary!"
                  aria-label="Creature to summon"
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              {busy ? (
                <div className="summon-busy" role="status">
                  <div className="summon-circle summon-circle--sm" aria-hidden="true">
                    <span className="summon-circle__ring" />
                    <span className="summon-circle__core" />
                  </div>
                  <span className="summon-busy__label">
                    READING THE SUMMONING CIRCLE…
                  </span>
                </div>
              ) : (
                <Btn accent="purple" size="lg" icon="icons/nav_fusion" disabled={!query.trim()}
                     onClick={submit}>
                  SUMMON
                </Btn>
              )}
              <p className="summon-hint">
                Dinosaurs, deep-sea monsters, legends — even ones you invent yourself.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

/** The permanent purple card pinned at the start of the picker rail. */
export function SummonRailCard({ onOpen }: { onOpen: () => void }) {
  return (
    <button type="button" className="pcard pcard--summon" onClick={onOpen} title="Summon a new creature">
      <span className="pcard__art summoncard">
        <span className="summoncard__halo" aria-hidden="true" />
        <Asset slot="icons/nav_fusion" label="" className="summoncard__glyph" tint="purple" />
        <span className="summoncard__sparks" aria-hidden="true" />
      </span>
      <span className="pcard__plate">
        <FitText className="pcard__name">SUMMON NEW</FitText>
      </span>
    </button>
  );
}
