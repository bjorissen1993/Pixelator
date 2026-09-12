import { useEffect, useMemo, useState } from "react";
import type { AssetLabSession, AssetType, CatalogSummary, LearningSnapshot } from "@shared";
import { api } from "../api";
import { assetUrl } from "../asset";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button } from "./ui";

const DEFAULT_BATCH_SIZES = [4, 8, 12, 20] as const;

function allocateBatch(count: number, exploitRatio: number) {
  if (count <= 0) {
    return { exploit: 0, explore: 0 };
  }
  const ratio = Math.max(0, Math.min(1, exploitRatio));
  const exploit = Math.min(count, Math.max(0, Math.floor(count * ratio + 0.5)));
  return { exploit, explore: count - exploit };
}

export function AssetLabScreen() {
  const { run, busy } = useWorkspace();
  const [catalog, setCatalog] = useState<CatalogSummary | null>(null);
  const [projectId, setProjectId] = useState("");
  const [assetType, setAssetType] = useState<AssetType>("character");
  const [assetId, setAssetId] = useState("");
  const [session, setSession] = useState<AssetLabSession | null>(null);
  const [batchSize, setBatchSize] = useState(4);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReasonIds, setRejectReasonIds] = useState<string[]>([]);
  const [rejectNote, setRejectNote] = useState("");
  const [validatorFeedback, setValidatorFeedback] = useState<"" | "missed_issue" | "incorrect_detection">("");

  const assetsForType = useMemo(
    () => (catalog?.assets ?? []).filter((item) => item.projectId === projectId && item.assetType === assetType),
    [catalog, projectId, assetType],
  );

  const allowedBatchSizes = catalog?.allowedBatchSizes?.length ? catalog.allowedBatchSizes : [...DEFAULT_BATCH_SIZES];

  const refresh = (nextProject = projectId, nextType = assetType, nextAsset = assetId, nextBatch = batchSize) =>
    api.assetLabSession(nextProject, nextType, nextAsset, nextBatch).then(setSession);

  useEffect(() => {
    void api
      .assetLabCatalog()
      .then((summary) => {
        setCatalog(summary);
        setProjectId(summary.defaultProjectId);
        setAssetType(summary.defaultAssetType);
        setAssetId(summary.defaultAssetId);
        return api.assetLabSession(summary.defaultProjectId, summary.defaultAssetType, summary.defaultAssetId, 4);
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
  const learning = sessionMatches ? session?.learning ?? null : null;
  const requestedExploit = learning?.requestedExploitRatio ?? learning?.exploitRatio ?? 0.8;
  const requestedExplore = learning?.requestedExploreRatio ?? learning?.exploreRatio ?? 0.2;
  const allocation = allocateBatch(batchSize, requestedExploit);

  const applyLearning = (next: LearningSnapshot) => {
    setSession((current) => (current ? { ...current, learning: next } : current));
  };

  const reviewReasons = sessionMatches ? session?.reviewReasons ?? [] : [];

  const openReject = (candidateId: string) => {
    setRejectingId(candidateId);
    setRejectReasonIds([]);
    setRejectNote("");
    setValidatorFeedback("");
  };

  const toggleRejectReason = (reasonId: string) => {
    setRejectReasonIds((current) =>
      current.includes(reasonId) ? current.filter((item) => item !== reasonId) : [...current, reasonId],
    );
  };

  const confirmReject = (candidateId: string) => {
    if (!rejectReasonIds.length && !rejectNote.trim() && !validatorFeedback) {
      return;
    }
    void run("Rejecting candidate", async () => {
      setSession(
        await api.rejectAssetLab(candidateId, projectId, assetType, assetId, {
          reasonIds: rejectReasonIds,
          note: rejectNote.trim(),
          validatorFeedback: validatorFeedback || null,
        }),
      );
      setRejectingId(null);
    });
  };

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
          <div className="chip-row asset-lab-generate">
            <label className="field asset-lab-batch">
              <span>Batch</span>
              <select
                value={batchSize}
                disabled={!!busy}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  setBatchSize(next);
                  if (projectId && assetType && assetId) {
                    void refresh(projectId, assetType, assetId, next).catch(() => undefined);
                  }
                }}
              >
                {allowedBatchSizes.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <Button
              disabled={!!busy || !canGenerate}
              onClick={() =>
                run(
                  `Creating ${batchSize} asset-lab candidates`,
                  async () => {
                    setSession(await api.generateAssetLab(projectId, assetType, assetId, batchSize));
                  },
                  { generating: false },
                )
              }
            >
              Generate {batchSize} candidates
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
          <h2>Learning</h2>
        </div>
        <p className="hint">
          Recipe optimization only. The model is not being retrained. Asset-specific conclusions stay on this asset.
        </p>
        <div className="learning-stats">
          <div className="learning-stat">
            <span>Attempts</span>
            <strong>{learning?.stats.attempts ?? 0}</strong>
          </div>
          <div className="learning-stat">
            <span>Accepted</span>
            <strong>{learning?.stats.accepted ?? 0}</strong>
          </div>
          <div className="learning-stat">
            <span>Rejected</span>
            <strong>{learning?.stats.rejected ?? 0}</strong>
          </div>
          <div className="learning-stat">
            <span>Success rate</span>
            <strong>{Math.round((learning?.stats.successRate ?? 0) * 100)}%</strong>
          </div>
        </div>
        <p className="sprite-meta">
          Requested {Math.round(requestedExploit * 100)}% exploit / {Math.round(requestedExplore * 100)}% explore.
          Allocated for a batch of {batchSize}: {allocation.exploit} exploit / {allocation.explore} explore (
          {Math.round((allocation.exploit / batchSize) * 100)}% / {Math.round((allocation.explore / batchSize) * 100)}%).
        </p>
        <div className="learning-evidence">
          <div>
            <h3>Automatic evidence</h3>
            {(learning?.stats.topAutomaticReasons ?? []).length ? (
              <ul className="canonical-checklist">
                {(learning?.stats.topAutomaticReasons ?? []).map((reason) => (
                  <li key={`auto-${reason}`}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="hint">No automatic validator rejections recorded yet.</p>
            )}
          </div>
          <div>
            <h3>Manual evidence</h3>
            {(learning?.stats.topManualReasons ?? []).length ? (
              <ul className="canonical-checklist">
                {(learning?.stats.topManualReasons ?? []).map((reason) => (
                  <li key={`manual-${reason}`}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="hint">No manual review rejections recorded yet.</p>
            )}
          </div>
        </div>
        <div className="learning-adjustments">
          {(learning?.recommendations ?? []).map((item) => (
            <article className={`learning-adjustment ${item.disabled ? "is-disabled" : ""}`} key={item.id}>
              <header>
                <strong>
                  {item.kind.replace("_", " ")} · {String(item.value)}
                </strong>
                <span className="sprite-meta">
                  {item.pinned ? "pinned" : item.applied ? "active" : item.disabled ? "disabled" : "recorded"} ·{" "}
                  {Math.round(item.confidence * 100)}% · {item.evidence} evidence
                </span>
              </header>
              <p className="hint">{item.explanation}</p>
              <p className="sprite-meta">Source {item.source}</p>
              <div className="chip-row">
                <Button
                  disabled={!!busy || item.disabled}
                  onClick={() =>
                    run("Disabling learned recommendation", async () => {
                      applyLearning(
                        await api.controlAssetLabLearning({
                          projectId,
                          assetType,
                          assetId,
                          recommendationId: item.id,
                        }),
                      );
                    })
                  }
                >
                  Disable
                </Button>
                {item.kind.endsWith("fragment") ? (
                  <Button
                    disabled={!!busy || item.pinned}
                    onClick={() =>
                      run("Pinning prompt fragment", async () => {
                        applyLearning(
                          await api.controlAssetLabLearning({
                            projectId,
                            assetType,
                            assetId,
                            pinKind: item.kind,
                            pinValue: item.value,
                          }),
                        );
                      })
                    }
                  >
                    Pin
                  </Button>
                ) : (
                  <Button
                    disabled={!!busy || item.pinned}
                    onClick={() =>
                      run("Pinning setting", async () => {
                        applyLearning(
                          await api.controlAssetLabLearning({
                            projectId,
                            assetType,
                            assetId,
                            pinKind: item.kind,
                            pinValue: item.value,
                          }),
                        );
                      })
                    }
                  >
                    Pin
                  </Button>
                )}
              </div>
            </article>
          ))}
        </div>
        {!learning?.recommendations.length ? <p className="hint">No learned adjustments yet for this asset.</p> : null}
        <h3>Next recipe</h3>
        {(learning?.why ?? []).map((line) => (
          <p className="hint" key={line}>
            {line}
          </p>
        ))}
        {learning?.nextRecipe ? (
          <p className="sprite-meta">
            Guidance {learning.nextRecipe.guidance} · steps {learning.nextRecipe.steps}
            {learning.nextRecipe.referenceStrength != null ? ` · ref ${learning.nextRecipe.referenceStrength}` : ""}
          </p>
        ) : null}
        <div className="chip-row">
          <Button
            disabled={!!busy || !assetId}
            onClick={() =>
              run("Resetting asset learning", async () => {
                applyLearning(
                  await api.controlAssetLabLearning({ projectId, assetType, assetId, resetScope: "asset" }),
                );
              })
            }
          >
            Reset asset
          </Button>
          <Button
            disabled={!!busy || !assetId}
            onClick={() =>
              run("Resetting asset-type learning", async () => {
                applyLearning(
                  await api.controlAssetLabLearning({ projectId, assetType, assetId, resetScope: "asset_type" }),
                );
              })
            }
          >
            Reset asset type
          </Button>
          <Button
            disabled={!!busy || !assetId}
            onClick={() =>
              run("Resetting project learning", async () => {
                applyLearning(
                  await api.controlAssetLabLearning({ projectId, assetType, assetId, resetScope: "project" }),
                );
              })
            }
          >
            Reset project
          </Button>
        </div>
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
                <span className="sprite-meta">
                  {candidate.status}
                  {candidate.recipeMode ? ` · ${candidate.recipeMode}` : ""}
                </span>
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
              {candidate.manualRejectReasons?.length || candidate.manualNote || candidate.validatorFeedback ? (
                <div className="manual-review-summary">
                  {candidate.manualRejectReasons?.length ? (
                    <ul className="canonical-checklist">
                      {candidate.manualRejectReasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  ) : null}
                  {candidate.manualNote ? <p className="hint">Note: {candidate.manualNote}</p> : null}
                  {candidate.validatorFeedback === "missed_issue" ? (
                    <p className="sprite-meta">False validator result: missed an issue</p>
                  ) : null}
                  {candidate.validatorFeedback === "incorrect_detection" ? (
                    <p className="sprite-meta">False validator result: incorrectly detected an issue</p>
                  ) : null}
                </div>
              ) : null}
              {rejectingId === candidate.id ? (
                <div className="reject-panel">
                  <p className="sprite-meta">Why reject this candidate?</p>
                  <div className="reject-reasons">
                    {reviewReasons.map((reason) => (
                      <label className="reject-reason" key={reason.id}>
                        <input
                          type="checkbox"
                          checked={rejectReasonIds.includes(reason.id)}
                          onChange={() => toggleRejectReason(reason.id)}
                        />
                        <span>{reason.label}</span>
                      </label>
                    ))}
                  </div>
                  <label className="field">
                    <span>Note</span>
                    <input
                      value={rejectNote}
                      maxLength={160}
                      placeholder="Optional short note"
                      onChange={(event) => setRejectNote(event.target.value)}
                    />
                  </label>
                  <fieldset className="reject-feedback">
                    <legend>False validator result</legend>
                    <label>
                      <input
                        type="radio"
                        name={`validator-feedback-${candidate.id}`}
                        checked={validatorFeedback === ""}
                        onChange={() => setValidatorFeedback("")}
                      />
                      <span>None</span>
                    </label>
                    <label>
                      <input
                        type="radio"
                        name={`validator-feedback-${candidate.id}`}
                        checked={validatorFeedback === "missed_issue"}
                        onChange={() => setValidatorFeedback("missed_issue")}
                      />
                      <span>Missed an issue</span>
                    </label>
                    <label>
                      <input
                        type="radio"
                        name={`validator-feedback-${candidate.id}`}
                        checked={validatorFeedback === "incorrect_detection"}
                        onChange={() => setValidatorFeedback("incorrect_detection")}
                      />
                      <span>Incorrectly detected an issue</span>
                    </label>
                  </fieldset>
                  <div className="chip-row">
                    <Button
                      variant="danger"
                      disabled={!!busy || (!rejectReasonIds.length && !rejectNote.trim() && !validatorFeedback)}
                      onClick={() => confirmReject(candidate.id)}
                    >
                      Confirm reject
                    </Button>
                    <Button variant="ghost" disabled={!!busy} onClick={() => setRejectingId(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
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
                    onClick={() => openReject(candidate.id)}
                  >
                    Reject
                  </Button>
                </div>
              )}
            </article>
          ))}
        </div>
        {!session?.candidates.length ? <p className="hint">No candidates yet.</p> : null}
      </section>
    </div>
  );
}

export const CanonicalBaseScreen = AssetLabScreen;
