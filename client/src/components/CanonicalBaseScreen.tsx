import { useEffect, useMemo, useState } from "react";
import type { AssetLabSession, AssetType, CatalogSummary } from "@shared";
import { api } from "../api";
import { assetUrl } from "../asset";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button } from "./ui";

export function AssetLabScreen() {
  const { run, busy } = useWorkspace();
  const [catalog, setCatalog] = useState<CatalogSummary | null>(null);
  const [projectId, setProjectId] = useState("");
  const [assetType, setAssetType] = useState<AssetType>("character");
  const [assetId, setAssetId] = useState("");
  const [session, setSession] = useState<AssetLabSession | null>(null);

  const assetsForType = useMemo(
    () => (catalog?.assets ?? []).filter((item) => item.projectId === projectId && item.assetType === assetType),
    [catalog, projectId, assetType],
  );

  const refresh = (nextProject = projectId, nextType = assetType, nextAsset = assetId) =>
    api.assetLabSession(nextProject, nextType, nextAsset).then(setSession);

  useEffect(() => {
    void api
      .assetLabCatalog()
      .then((summary) => {
        setCatalog(summary);
        setProjectId(summary.defaultProjectId);
        setAssetType(summary.defaultAssetType);
        setAssetId(summary.defaultAssetId);
        return api.assetLabSession(summary.defaultProjectId, summary.defaultAssetType, summary.defaultAssetId);
      })
      .then(setSession)
      .catch(() => undefined);
  }, []);

  const selectProject = (next: string) => {
    const project = catalog?.projects.find((item) => item.id === next);
    const first = (catalog?.assets ?? []).find((item) => item.projectId === next);
    const nextType = (project?.defaultAssetType || first?.assetType || "character") as AssetType;
    const nextAsset =
      (project?.defaultAssetId &&
      (catalog?.assets ?? []).some((item) => item.projectId === next && item.assetId === project.defaultAssetId)
        ? project.defaultAssetId
        : first?.assetId) ?? "";
    setProjectId(next);
    setAssetType(nextType);
    setAssetId(nextAsset);
    setSession(null);
    if (nextAsset) {
      void refresh(next, nextType, nextAsset).catch(() => undefined);
    }
  };

  const selectType = (next: AssetType) => {
    const first = (catalog?.assets ?? []).find((item) => item.projectId === projectId && item.assetType === next);
    const nextAsset = first?.assetId ?? "";
    setAssetType(next);
    setAssetId(nextAsset);
    setSession(null);
    if (nextAsset) {
      void refresh(projectId, next, nextAsset).catch(() => undefined);
    }
  };

  const selectAsset = (next: string) => {
    setAssetId(next);
    setSession(null);
    void refresh(projectId, assetType, next).catch(() => undefined);
  };

  const sessionMatches =
    session?.projectId === projectId && session?.assetType === assetType && session?.assetId === assetId;
  const checklist = sessionMatches ? session?.reviewChecklist ?? [] : [];
  const canGenerate = sessionMatches && !!session?.generationEnabled;

  return (
    <div className="stack canonical-base">
      <section className="block">
        <div className="block-head">
          <div>
            <h2>Asset Lab</h2>
            <p className="hint">
              Canonical reference review for the selected asset. Pixelator is a general-purpose pixel-art
              generator; Chimera / Berwynn is only the current vertical-slice test. Production Studio
              generation is unchanged.
            </p>
          </div>
          <div className="chip-row">
            <Button
              disabled={!!busy || !canGenerate}
              onClick={() =>
                run(
                  "Creating asset-lab candidates",
                  async () => {
                    setSession(await api.generateAssetLab(projectId, assetType, assetId, 4));
                  },
                  { generating: false },
                )
              }
            >
              Generate 4 candidates
            </Button>
          </div>
        </div>
        <div className="asset-lab-selectors">
          <label className="field">
            <span>Project</span>
            <select
              value={projectId}
              disabled={(catalog?.projects.length ?? 0) <= 1}
              onChange={(event) => selectProject(event.target.value)}
            >
              {(catalog?.projects ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Asset type</span>
            <select value={assetType} onChange={(event) => selectType(event.target.value as AssetType)}>
              <option value="character">Character</option>
              <option value="portrait">Portrait</option>
              <option value="item">Item</option>
              <option value="prop">Prop</option>
              <option value="tile">Tile</option>
              <option value="background">Background</option>
              <option value="ui">UI</option>
              <option value="vfx">VFX</option>
            </select>
          </label>
          <label className="field">
            <span>Asset</span>
            <select value={assetId} onChange={(event) => selectAsset(event.target.value)} disabled={!assetsForType.length}>
              {assetsForType.map((item) => (
                <option key={item.assetId} value={item.assetId}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="sprite-meta">
          {sessionMatches && session
            ? `${session.projectName} → ${session.assetType} → ${session.assetName}`
            : assetId
              ? "Loading selected asset…"
              : "No asset selected"}
          {sessionMatches && session?.state ? ` · ${session.state}` : ""}
          {sessionMatches && session?.direction ? ` · ${session.direction}` : ""}
        </p>
        <p className="hint">{sessionMatches ? session?.canonicalLabel : ""}</p>
        {checklist.length ? (
          <ul className="canonical-checklist">
            {checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="hint">No review checklist for this asset yet.</p>
        )}
        <p className="sprite-meta">
          Model {sessionMatches && session?.modelId ? session.modelId : canGenerate ? "configured" : "not implemented"} · isolated Asset Lab
          {canGenerate ? " · raw 512×512 · no crop / resize / background removal" : ""}
        </p>
        {sessionMatches && !canGenerate ? (
          <p className="hint">Generation for this asset type is not implemented yet. Architecture and validators are in place.</p>
        ) : null}
      </section>

      <section className="block">
        <div className="block-head">
          <h2>Accepted canonical reference</h2>
        </div>
        {sessionMatches && session?.accepted ? (
          <div className="canonical-accepted">
            <img
              alt={`Accepted ${session.assetName} reference`}
              className="canonical-preview"
              src={assetUrl(session.accepted.path, session.accepted.createdAt)}
            />
            <div>
              <p>Accepted seed {session.accepted.seed}. This is the only allowed later identity/reference source for this asset.</p>
              <p className="hint">
                {session.referenceUnlocked || session.ipAdapterUnlocked
                  ? "Reference-conditioned follow-up is unlocked for this accepted asset."
                  : "Reference-conditioned follow-up is still locked."}{" "}
                Direction generation remains locked.
              </p>
            </div>
          </div>
        ) : (
          <p className="hint">No canonical reference accepted yet. Review candidates below.</p>
        )}
      </section>

      <section className="block">
        <div className="block-head">
          <h2>Review panel</h2>
        </div>
        <div className="canonical-grid">
          {(sessionMatches ? session?.candidates ?? [] : []).map((candidate) => (
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
                  alt={`${session?.assetName ?? "Asset"} candidate ${candidate.seed}`}
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
                <p className="hint">Passed automatic checks. Confirm the checklist by eye before accept.</p>
              )}
              <div className="chip-row">
                <Button
                  disabled={!!busy || !candidate.valid || candidate.status === "accepted"}
                  onClick={() =>
                    run("Accepting canonical reference", async () => {
                      setSession(await api.acceptAssetLab(candidate.id, projectId, assetType, assetId));
                    })
                  }
                >
                  Accept
                </Button>
                <Button
                  variant="danger"
                  disabled={!!busy || candidate.status === "rejected"}
                  onClick={() =>
                    run("Rejecting candidate", async () => {
                      setSession(await api.rejectAssetLab(candidate.id, projectId, assetType, assetId));
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

export const CanonicalBaseScreen = AssetLabScreen;
