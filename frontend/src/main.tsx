import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

/* Bundled type (UI_STANDARD §Typography) — no CDN, latin subsets only.
   Rajdhani carries every heading, name, button and stat; Inter carries body. */
import "@fontsource/rajdhani/latin-500.css";
import "@fontsource/rajdhani/latin-600.css";
import "@fontsource/rajdhani/latin-700.css";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";

import "./theme.css";

/* iOS Safari applies :active to a tapped element only when some touchstart
   listener exists on the page. This empty one turns on the pressed state
   every button and card defines in theme.css (§touch feel): the press is the
   acknowledgement, before React or the network has answered. */
document.addEventListener("touchstart", () => {}, { passive: true });

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
