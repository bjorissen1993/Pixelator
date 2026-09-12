import { useEffect, useState } from "react";
import type { CanonicalBaseSession } from "@shared";
import { api } from "../api";
import { assetUrl } from "../asset";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button } from "./ui";

const TARGET = [
  "Single character only",
  "Full body, front/south-facing, centered, readable silhouette",
  "Elderly male spirit, short messy grey/white hair, thick beard",
  "Tired but kind stern face, broad slightly hunched shoulders",
  "Worn dark village tunic, faded chief mantle, simple cloth/leather belt",
  "No armor, no shoulder armor, no weapons",
  "Lower body fades into a spectral ghost tail — no legs, no boots",
  "Pale subtle blue spirit aura, melancholic protective presence",
  "Plain or transparent background",
];

export function CanonicalBaseScreen() {
  const { run, busy } = useWorkspace();
  const [session, setSession] = useState<CanonicalBaseSession | null>(null);

  const refresh = () =>
    api.canonicalBaseSession().then(setSession);

  useEffect(() => {
    void refresh().catch(() => undefined);
  }, []);

  return (
    <div className="stack canonical-base">
      <section className="block">
        <div className="block-head">
          <div>
            <h2>Canonical Berwynn base</h2>
            <p className="hint">
              Isolated south-facing identity creation. Studio generation and the current direction set
              are not used as the identity source. IP-Adapter stays locked until one valid base is accepted.
              Eight directions stay locked.
            </p>
          </div>
          <div className="chip-row">
            <Button
              disabled={!!busy}
              onClick={() =>
                run(
                  "Creating canonical Berwynn candidates",
                  async () => {
                    setSession(await api.generateCanonicalBase(4));
                  },
                  { generating: false },
                )
              }
            >
              Generate 4 candidates
            </Button>
          </div>
        </div>
        <ul className="canonical-checklist">
          {TARGET.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="sprite-meta">
          Model {session?.modelId || "PublicPrompts/All-In-One-Pixel-Model"} · raw 512×512 · no crop / resize /
          background removal
        </p>
      </section>

      <section className="block">
        <div className="block-head">
          <h2>Accepted canonical base</h2>
        </div>
        {session?.accepted ? (
          <div className="canonical-accepted">
            <img
              alt="Accepted canonical Berwynn"
              className="canonical-preview"
              src={assetUrl(session.accepted.path, session.accepted.createdAt)}
            />
            <div>
              <p>Accepted seed {session.accepted.seed}. This is the only allowed IP-Adapter identity source.</p>
              <p className="hint">
                {session.ipAdapterUnlocked
                  ? "IP-Adapter identity propagation is unlocked."
                  : "IP-Adapter is still locked."}{" "}
                Direction generation remains locked.
              </p>
            </div>
          </div>
        ) : (
          <p className="hint">No canonical base accepted yet. Review candidates below.</p>
        )}
      </section>

      <section className="block">
        <div className="block-head">
          <h2>Review panel</h2>
        </div>
        <div className="canonical-grid">
          {(session?.candidates ?? []).map((candidate) => (
            <article
              className={`canonical-card ${candidate.valid ? "is-valid" : "is-invalid"} ${candidate.status}`}
              key={candidate.id}
            >
              <header>
                <h3>Seed {candidate.seed}</h3>
                <span className="sprite-meta">{candidate.status}</span>
              </header>
              <div className="canonical-stage">
                <img
                  alt={`Canonical candidate ${candidate.seed}`}
                  className="canonical-preview"
                  src={assetUrl(candidate.path, candidate.createdAt)}
                />
              </div>
              {candidate.rejectReasons.length ? (
                <ul className="quality-warnings invalid-base">
                  {candidate.rejectReasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : (
                <p className="hint">Passed automatic canonical checks. Confirm the ghost tail by eye before accept.</p>
              )}
              <div className="chip-row">
                <Button
                  disabled={!!busy || !candidate.valid || candidate.status === "accepted"}
                  onClick={() =>
                    run("Accepting canonical Berwynn base", async () => {
                      setSession(await api.acceptCanonicalBase(candidate.id));
                    })
                  }
                >
                  Accept
                </Button>
                <Button
                  variant="danger"
                  disabled={!!busy || candidate.status === "rejected"}
                  onClick={() =>
                    run("Rejecting canonical candidate", async () => {
                      setSession(await api.rejectCanonicalBase(candidate.id));
                    })
                  }
                >
                  Reject
                </Button>
              </div>
            </article>
          ))}
        </div>
        {!session?.candidates.length ? <p className="hint">No candidates yet.</p> : null}
      </section>
    </div>
  );
}
