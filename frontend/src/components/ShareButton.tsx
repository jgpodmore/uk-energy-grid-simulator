import { useState } from "react";

type ShareState = "idle" | "copied" | "error";

export default function ShareButton({ label, buildText }: { label: string; buildText: () => string }) {
  const [state, setState] = useState<ShareState>("idle");

  const handleClick = async () => {
    const text = buildText();
    const url = window.location.href;

    if (navigator.share) {
      try {
        await navigator.share({ title: "UK Energy Grid Simulator results", text, url });
        return;
      } catch (e) {
        // AbortError just means the user dismissed the native share sheet -
        // not a failure worth falling back from.
        if (e instanceof DOMException && e.name === "AbortError") return;
      }
    }

    try {
      await navigator.clipboard.writeText(`${text}\n\n${url}`);
      setState("copied");
    } catch {
      setState("error");
    } finally {
      setTimeout(() => setState("idle"), 2500);
    }
  };

  const displayLabel = state === "copied" ? "Copied to clipboard!" : state === "error" ? "Couldn't copy - try again" : label;

  return (
    <button type="button" className="share-btn" onClick={handleClick}>
      {displayLabel}
    </button>
  );
}
