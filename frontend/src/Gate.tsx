/* The lab door. Full-screen PIN gate shown before the app shell — one shared
   4-digit "secret lab code" (backend/app/auth.py), sized for 8-year-old thumbs
   on an iPad. Standalone on purpose: no ui.tsx imports, gate-* classes only,
   design tokens borrowed from theme.css :root. */
import { useCallback, useEffect, useState } from "react";
import "./gate.css";

const PIN_LENGTH = 4;

/** Boot probe: is the session cookie still good? Network errors count as
    unlocked — fail-open, so a backend hiccup during dev never traps the UI
    inside the gate (the API calls themselves will surface the real error). */
export async function checkUnlocked(): Promise<boolean> {
  try {
    const res = await fetch("/api/auth/me", { credentials: "include" });
    // Only an explicit 401 locks the door. A 404 (backend without the auth
    // routes yet) or 5xx fails open — a hiccup must never brick the game.
    return res.status !== 401;
  } catch {
    return true;
  }
}

export default function Gate({ onUnlocked }: { onUnlocked: () => void }) {
  const [digits, setDigits] = useState("");
  const [busy, setBusy] = useState(false);
  const [shake, setShake] = useState(false);
  const [message, setMessage] = useState("");

  const submit = useCallback(
    async (pin: string) => {
      setBusy(true);
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include", // same-origin sends cookies anyway; explicit for clarity
          body: JSON.stringify({ pin }),
        });
        if (res.ok) {
          onUnlocked();
          return;
        }
        if (res.status === 429) {
          let detail = "Too many tries! Give the door a 5 minute rest.";
          try {
            const data = await res.json();
            if (typeof data.detail === "string") detail = data.detail;
          } catch {
            /* keep the fallback line */
          }
          setMessage(detail);
        } else {
          setMessage("Hmm, that's not it — try again!");
        }
        setShake(true);
        setDigits("");
        window.setTimeout(() => setShake(false), 450);
      } catch {
        setMessage("The lab isn't answering — check the connection.");
        setDigits("");
      } finally {
        setBusy(false);
      }
    },
    [onUnlocked],
  );

  const press = useCallback(
    (d: string) => {
      if (busy || digits.length >= PIN_LENGTH) return;
      const next = digits + d;
      setMessage("");
      setDigits(next);
      if (next.length === PIN_LENGTH) void submit(next);
    },
    [busy, digits, submit],
  );

  const erase = useCallback(() => {
    if (!busy) setDigits((cur) => cur.slice(0, -1));
  }, [busy]);

  // Physical keyboards work too (dev machines, iPad with a keyboard case).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (/^[0-9]$/.test(e.key)) press(e.key);
      else if (e.key === "Backspace") erase();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [press, erase]);

  return (
    <div className="gate" role="dialog" aria-modal="true" aria-label="Secret lab code">
      <div className={`gate-card${shake ? " gate-card--shake" : ""}`}>
        <div className="gate-avatar">
          {/* Same art the topbar wears: ui.tsx maps "ui/avatar" to this file. */}
          <img
            src="/assets/avatar/henry_headshot.webp"
            alt=""
            onError={(e) => ((e.currentTarget as HTMLImageElement).style.visibility = "hidden")}
          />
        </div>
        <div className="gate-name">HENRY</div>
        <h1 className="gate-title">SECRET LAB CODE</h1>
        <p className="gate-hint">Tap your {PIN_LENGTH}-digit code to open the lab</p>

        <div className="gate-dots" aria-label={`${digits.length} of ${PIN_LENGTH} digits entered`}>
          {Array.from({ length: PIN_LENGTH }).map((_, i) => (
            <span key={i} className={`gate-dot${i < digits.length ? " is-filled" : ""}`} />
          ))}
        </div>

        <p className="gate-message" role="status">
          {message || " "}
        </p>

        <div className="gate-pad">
          {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
            <button
              key={d}
              type="button"
              className="gate-key"
              disabled={busy}
              onClick={() => press(d)}
            >
              {d}
            </button>
          ))}
          <span className="gate-key-blank" aria-hidden="true" />
          <button type="button" className="gate-key" disabled={busy} onClick={() => press("0")}>
            0
          </button>
          <button
            type="button"
            className="gate-key gate-key--erase"
            disabled={busy}
            onClick={erase}
            aria-label="Delete last digit"
          >
            <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
              <path
                d="M9 5h11a1.5 1.5 0 0 1 1.5 1.5v11A1.5 1.5 0 0 1 20 19H9L2.5 12 9 5Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <path
                d="m11.5 9.5 5 5m0-5-5 5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
