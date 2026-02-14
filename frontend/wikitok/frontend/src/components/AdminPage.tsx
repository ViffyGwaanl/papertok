import { useEffect, useMemo, useState } from 'react';

import { API_BASE, apiUrl } from '../lib/apiBase';

type AdminConfigResp = {
  defaults: Record<string, any>;
  db: Record<string, any>;
  effective: Record<string, any>;
  meta: {
    admin_token_required: boolean;
    editable: string[];
  };
};

type JobsResp = {
  supported: Record<string, string>;
  jobs: any[];
};

type WorkerLogsMeta = {
  err: null | { path: string; size: number; mtime: number };
  out: null | { path: string; size: number; mtime: number };
};

export function AdminPage() {
  const [token, setToken] = useState<string>(() => {
    try {
      return localStorage.getItem('papertok_admin_token') || '';
    } catch {
      return '';
    }
  });

  const [cfg, setCfg] = useState<AdminConfigResp | null>(null);
  const [status, setStatus] = useState<any>(null);
  const [jobs, setJobs] = useState<JobsResp | null>(null);
  const [workerMeta, setWorkerMeta] = useState<WorkerLogsMeta | null>(null);
  const [jobLog, setJobLog] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [jobMsg, setJobMsg] = useState<string | null>(null);

  const headers = useMemo(() => {
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token.trim()) h['X-Admin-Token'] = token.trim();
    return h;
  }, [token]);

  const workerErrSize = workerMeta?.err?.size ?? 0;
  const workerOutSize = workerMeta?.out?.size ?? 0;
  const workerWarnBytes = 5_000_000; // 5MB
  const workerLogsTooBig = workerErrSize > workerWarnBytes || workerOutSize > workerWarnBytes;

  const refresh = async () => {
    setLoading(true);
    setError(null);
    setSaveMsg(null);
    setJobMsg(null);
    try {
      const [rCfg, rStatus, rJobs, rMeta] = await Promise.all([
        fetch(apiUrl('/api/admin/config'), { headers }),
        fetch(apiUrl('/api/admin/status'), { headers }),
        fetch(apiUrl('/api/admin/jobs'), { headers }),
        fetch(apiUrl('/api/admin/jobs/worker_logs/meta'), { headers }),
      ]);

      if (!rCfg.ok) {
        const t = await rCfg.text();
        throw new Error(`config HTTP ${rCfg.status}: ${t}`);
      }
      if (!rStatus.ok) {
        const t = await rStatus.text();
        throw new Error(`admin status HTTP ${rStatus.status}: ${t}`);
      }
      if (!rJobs.ok) {
        const t = await rJobs.text();
        throw new Error(`jobs HTTP ${rJobs.status}: ${t}`);
      }
      if (!rMeta.ok) {
        const t = await rMeta.text();
        throw new Error(`worker_logs meta HTTP ${rMeta.status}: ${t}`);
      }

      const jCfg = (await rCfg.json()) as AdminConfigResp;
      const jStatus = await rStatus.json();
      const jJobs = (await rJobs.json()) as JobsResp;
      const jMeta = (await rMeta.json()) as WorkerLogsMeta;
      setCfg(jCfg);
      setStatus(jStatus);
      setJobs(jJobs);
      setWorkerMeta(jMeta);
    } catch (e: any) {
      setError(e?.message || 'Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const effective = cfg?.effective || {};

  const save = async () => {
    if (!cfg) return;
    setLoading(true);
    setError(null);
    setSaveMsg(null);

    try {
      const payload: Record<string, any> = {
        feed_require_explain: Boolean(effective.feed_require_explain),
        feed_require_image_captions: Boolean(effective.feed_require_image_captions),
        feed_require_generated_images: Boolean(effective.feed_require_generated_images),
        paper_images_display_provider: effective.paper_images_display_provider,
        image_caption_context_chars: Number(effective.image_caption_context_chars),
        image_caption_context_strategy: effective.image_caption_context_strategy,
        image_caption_context_occurrences: Number(effective.image_caption_context_occurrences),
      };

      const r = await fetch(`${API_BASE}/api/admin/config`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`save HTTP ${r.status}: ${t}`);
      }

      setSaveMsg('Saved');
      await refresh();
    } catch (e: any) {
      setError(e?.message || 'Failed to save');
    } finally {
      setLoading(false);
    }
  };

  const enqueueJob = async (jobType: string, payload: any = {}) => {
    setLoading(true);
    setError(null);
    setJobMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/admin/jobs/${jobType}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload || {}),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`enqueue HTTP ${r.status}: ${t}`);
      }
      setJobMsg(`Enqueued: ${jobType}`);
      await refresh();
    } catch (e: any) {
      setError(e?.message || 'Failed to enqueue job');
    } finally {
      setLoading(false);
    }
  };

  const kickWorkerNow = async () => {
    setLoading(true);
    setError(null);
    setJobMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/admin/jobs/worker/kick`, {
        method: 'POST',
        headers,
        body: JSON.stringify({}),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`kick HTTP ${r.status}: ${t}`);
      }
      setJobMsg('Kicked worker (non-disruptive)');
      await refresh();
    } catch (e: any) {
      setError(e?.message || 'Failed to kick worker');
    } finally {
      setLoading(false);
    }
  };

  const truncateWorkerLogs = async () => {
    setLoading(true);
    setError(null);
    setJobMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/admin/jobs/worker_logs/truncate`, {
        method: 'POST',
        headers,
        body: JSON.stringify({}),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`truncate HTTP ${r.status}: ${t}`);
      }
      setJobMsg('Cleared job_worker launchd logs');
      await refresh();
    } catch (e: any) {
      setError(e?.message || 'Failed to clear logs');
    } finally {
      setLoading(false);
    }
  };

  const viewJobLog = async (jobId: number) => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/admin/jobs/${jobId}/log?tail_lines=200`, { headers });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`log HTTP ${r.status}: ${t}`);
      }
      const j = await r.json();
      setJobLog(j.log || '');
    } catch (e: any) {
      setError(e?.message || 'Failed to load job log');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen w-full overflow-y-auto overscroll-contain touch-pan-y bg-black text-white p-4 safe-pt-4 [-webkit-overflow-scrolling:touch]">
      <div className="max-w-4xl mx-auto space-y-4 pb-24">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xl font-bold">PaperTok Admin</div>
          <div className="flex items-center gap-2">
            <button
              className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20"
              onClick={() => (window.location.href = '/')}
            >
              Back
            </button>
            <button
              className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20"
              onClick={refresh}
              disabled={loading}
            >
              Refresh
            </button>
          </div>
        </div>

        <div className="border border-white/10 rounded p-3 space-y-2">
          <div className="text-sm font-semibold">Admin Token (optional)</div>
          <div className="text-xs text-white/60">
            If PAPERTOK_ADMIN_TOKEN is set on server, requests to /api/admin/* require header X-Admin-Token.
          </div>
          <input
            type="password"
            value={token}
            onChange={(e) => {
              const v = e.target.value;
              setToken(v);
              try {
                localStorage.setItem('papertok_admin_token', v);
              } catch {}
            }}
            placeholder="(empty)"
            className="w-full bg-gray-900 border border-white/10 rounded px-3 py-2 text-sm"
          />
        </div>

        {error && (
          <div className="border border-red-500/30 bg-red-500/10 rounded p-3 text-sm text-red-200 whitespace-pre-wrap">
            {error}
          </div>
        )}
        {saveMsg && (
          <div className="border border-green-500/30 bg-green-500/10 rounded p-3 text-sm text-green-200">
            {saveMsg}
          </div>
        )}
        {jobMsg && (
          <div className="border border-green-500/30 bg-green-500/10 rounded p-3 text-sm text-green-200">
            {jobMsg}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-white/10 rounded p-3 space-y-3">
            <div className="text-sm font-semibold">Config (DB-backed)</div>

            <label className="block text-sm">
              <div className="text-white/70 mb-1">Feed require explanation</div>
              <select
                value={effective.feed_require_explain ? '1' : '0'}
                onChange={(e) =>
                  setCfg((prev) =>
                    prev
                      ? {
                          ...prev,
                          effective: {
                            ...prev.effective,
                            feed_require_explain: e.target.value === '1',
                          },
                        }
                      : prev
                  )
                }
                className="w-full bg-gray-900 border border-white/10 rounded px-3 py-2 text-sm"
              >
                <option value="1">Yes (skip unprocessed)</option>
                <option value="0">No (show all)</option>
              </select>
            </label>

            <label className="block text-sm">
              <div className="text-white/70 mb-1">Feed require image captions</div>
              <select
                value={effective.feed_require_image_captions ? '1' : '0'}
                onChange={(e) =>
                  setCfg((prev) =>
                    prev
                      ? {
                          ...prev,
                          effective: {
                            ...prev.effective,
                            feed_require_image_captions: e.target.value === '1',
                          },
                        }
                      : prev
                  )
                }
                className="w-full bg-gray-900 border border-white/10 rounded px-3 py-2 text-sm"
              >
                <option value="1">Yes (hide papers missing captions)</option>
                <option value="0">No</option>
              </select>
            </label>

            <label className="block text-sm">
              <div className="text-white/70 mb-1">Feed require generated images (any provider)</div>
              <select
                value={effective.feed_require_generated_images ? '1' : '0'}
                onChange={(e) =>
                  setCfg((prev) =>
                    prev
                      ? {
                          ...prev,
                          effective: {
                            ...prev.effective,
                            feed_require_generated_images: e.target.value === '1',
                          },
                        }
                      : prev
                  )
                }
                className="w-full bg-gray-900 border border-white/10 rounded px-3 py-2 text-sm"
              >
                <option value="1">Yes (hide papers with no generated images)</option>
                <option value="0">No</option>
              </select>
            </label>

            <label className="block text-sm">
              <div className="text-white/70 mb-1">Primary feed image provider (ordering)</div>
              <select
                value={effective.paper_images_display_provider || 'seedream'}
                onChange={(e) =>
                  setCfg((prev) =>
                    prev
                      ? {
                          ...prev,
                          effective: {
                            ...prev.effective,
                            paper_images_display_provider: e.target.value,
                          },
                        }
                      : prev
                  )
                }
                className="w-full bg-gray-900 border border-white/10 rounded px-3 py-2 text-sm"
              >
                <option value="seedream">seedream</option>
                <option value="glm">glm</option>
                <option value="auto">auto</option>
              </select>
            </label>

            <label className="block text-sm">
              <div className="text-white/70 mb-1">Caption context chars</div>
              <input
                type="number"
                value={Number(effective.image_caption_context_chars || 2000)}
                onChange={(e) =>
                  setCfg((prev) =>
                    prev
                      ? {
                          ...prev,
                          effective: {
                            ...prev.effective,
                            image_caption_context_chars: Number(e.target.value),
                          },
                        }
                      : prev
                  )
                }
                className="w-full bg-gray-900 border border-white/10 rounded px-3 py-2 text-sm"
              />
            </label>

            <label className="block text-sm">
              <div className="text-white/70 mb-1">Caption context strategy</div>
              <select
                value={effective.image_caption_context_strategy || 'merge'}
                onChange={(e) =>
                  setCfg((prev) =>
                    prev
                      ? {
                          ...prev,
                          effective: {
                            ...prev.effective,
                            image_caption_context_strategy: e.target.value,
                          },
                        }
                      : prev
                  )
                }
                className="w-full bg-gray-900 border border-white/10 rounded px-3 py-2 text-sm"
              >
                <option value="merge">merge</option>
                <option value="last">last</option>
              </select>
            </label>

            <label className="block text-sm">
              <div className="text-white/70 mb-1">Caption context occurrences</div>
              <input
                type="number"
                value={Number(effective.image_caption_context_occurrences || 3)}
                onChange={(e) =>
                  setCfg((prev) =>
                    prev
                      ? {
                          ...prev,
                          effective: {
                            ...prev.effective,
                            image_caption_context_occurrences: Number(e.target.value),
                          },
                        }
                      : prev
                  )
                }
                className="w-full bg-gray-900 border border-white/10 rounded px-3 py-2 text-sm"
              />
            </label>

            <button
              className="w-full px-3 py-2 text-sm rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50"
              onClick={save}
              disabled={loading || !cfg}
            >
              Save
            </button>

            <div className="text-xs text-white/50">
              Note: background jobs read DB config at job start; the feed uses it per request.
            </div>
          </div>

          <div className="border border-white/10 rounded p-3 space-y-2">
            <div className="text-sm font-semibold">Status (/api/status)</div>
            <pre className="text-xs text-white/70 whitespace-pre-wrap break-words max-h-[50vh] overflow-auto">
              {status ? JSON.stringify(status, null, 2) : '(loading...)'}
            </pre>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-white/10 rounded p-3 space-y-3">
            <div className="text-sm font-semibold">Jobs</div>

            <div className="space-y-2">
              <div className="space-y-2 border border-white/10 rounded p-2">
                <div className="text-xs text-white/70">Image captions (scoped)</div>

                <label className="block text-xs text-white/60">
                  Scope
                  <select
                    className="mt-1 w-full bg-gray-900 border border-white/10 rounded px-2 py-1 text-sm"
                    value={(cfg as any)?.effective?._caption_scope || 'latest'}
                    onChange={(e) =>
                      setCfg((prev) =>
                        prev
                          ? {
                              ...prev,
                              effective: {
                                ...(prev as any).effective,
                                _caption_scope: e.target.value,
                              },
                            }
                          : prev
                      )
                    }
                  >
                    <option value="latest">latest Top10 day</option>
                    <option value="day">specific day (YYYY-MM-DD)</option>
                    <option value="external_ids">external_ids list</option>
                    <option value="all">all history</option>
                  </select>
                </label>

                {((cfg as any)?.effective?._caption_scope || 'latest') === 'day' && (
                  <label className="block text-xs text-white/60">
                    Day
                    <input
                      className="mt-1 w-full bg-gray-900 border border-white/10 rounded px-2 py-1 text-sm"
                      placeholder="2026-02-06"
                      value={(cfg as any)?.effective?._caption_day || ''}
                      onChange={(e) =>
                        setCfg((prev) =>
                          prev
                            ? {
                                ...prev,
                                effective: {
                                  ...(prev as any).effective,
                                  _caption_day: e.target.value,
                                },
                              }
                            : prev
                        )
                      }
                    />
                  </label>
                )}

                {((cfg as any)?.effective?._caption_scope || 'latest') === 'external_ids' && (
                  <label className="block text-xs text-white/60">
                    external_ids (comma separated)
                    <textarea
                      className="mt-1 w-full bg-gray-900 border border-white/10 rounded px-2 py-1 text-sm"
                      rows={3}
                      placeholder="2602.04705,2602.04804"
                      value={(cfg as any)?.effective?._caption_external_ids || ''}
                      onChange={(e) =>
                        setCfg((prev) =>
                          prev
                            ? {
                                ...prev,
                                effective: {
                                  ...(prev as any).effective,
                                  _caption_external_ids: e.target.value,
                                },
                              }
                            : prev
                        )
                      }
                    />
                  </label>
                )}

                <div className="grid grid-cols-2 gap-2">
                  <label className="block text-xs text-white/60">
                    max images
                    <input
                      type="number"
                      className="mt-1 w-full bg-gray-900 border border-white/10 rounded px-2 py-1 text-sm"
                      value={Number((cfg as any)?.effective?._caption_max || 500)}
                      onChange={(e) =>
                        setCfg((prev) =>
                          prev
                            ? {
                                ...prev,
                                effective: {
                                  ...(prev as any).effective,
                                  _caption_max: Number(e.target.value),
                                },
                              }
                            : prev
                        )
                      }
                    />
                  </label>
                  <label className="block text-xs text-white/60">
                    per paper
                    <input
                      type="number"
                      className="mt-1 w-full bg-gray-900 border border-white/10 rounded px-2 py-1 text-sm"
                      value={Number((cfg as any)?.effective?._caption_per_paper || 40)}
                      onChange={(e) =>
                        setCfg((prev) =>
                          prev
                            ? {
                                ...prev,
                                effective: {
                                  ...(prev as any).effective,
                                  _caption_per_paper: Number(e.target.value),
                                },
                              }
                            : prev
                        )
                      }
                    />
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    className="px-3 py-2 text-sm rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                    onClick={() => {
                      const scope = (cfg as any)?.effective?._caption_scope || 'latest';
                      const payload: any = {
                        image_caption_max: Number((cfg as any)?.effective?._caption_max || 500),
                        image_caption_per_paper: Number((cfg as any)?.effective?._caption_per_paper || 40),
                      };
                      if (scope === 'latest') payload.day = 'latest';
                      else if (scope === 'day') payload.day = ((cfg as any)?.effective?._caption_day || '').trim();
                      else if (scope === 'external_ids') payload.external_ids = (cfg as any)?.effective?._caption_external_ids || '';
                      else payload.day = null;
                      // fill missing (no wipe)
                      enqueueJob('image_caption_scoped', payload);
                    }}
                    disabled={loading}
                    title="Generate captions for missing images only (scoped)"
                  >
                    Caption (fill)
                  </button>
                  <button
                    className="px-3 py-2 text-sm rounded bg-red-600/70 hover:bg-red-600 disabled:opacity-50"
                    onClick={() => {
                      const scope = (cfg as any)?.effective?._caption_scope || 'latest';
                      const payload: any = {
                        image_caption_max: Number((cfg as any)?.effective?._caption_max || 500),
                        image_caption_per_paper: Number((cfg as any)?.effective?._caption_per_paper || 40),
                      };
                      if (scope === 'latest') payload.day = 'latest';
                      else if (scope === 'day') payload.day = ((cfg as any)?.effective?._caption_day || '').trim();
                      else if (scope === 'external_ids') payload.external_ids = (cfg as any)?.effective?._caption_external_ids || '';
                      else payload.day = null;
                      enqueueJob('image_caption_regen_scoped', payload);
                    }}
                    disabled={loading}
                    title="Wipe and re-generate captions in the selected scope"
                  >
                    Caption (regen)
                  </button>
                </div>

                <div className="text-[11px] text-white/50">
                  Fill = only missing captions; Regen = wipe captions in scope then re-generate.
                </div>
              </div>
              <button
                className="w-full px-3 py-2 text-sm rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                onClick={() => enqueueJob('paper_images_glm_backfill')}
                disabled={loading}
              >
                Enqueue: paper_images_glm_backfill
              </button>

              <button
                className="w-full px-3 py-2 text-sm rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                onClick={() => enqueueJob('paper_events_backfill')}
                disabled={loading}
                title="Write skipped/success markers into paper_events for current DB state"
              >
                Enqueue: paper_events_backfill
              </button>

              <div className="space-y-2 border border-white/10 rounded p-2">
                <div className="text-xs text-white/70">Retry one paper stage</div>

                <label className="block text-xs text-white/60">
                  external_id
                  <input
                    className="mt-1 w-full bg-gray-900 border border-white/10 rounded px-2 py-1 text-sm"
                    placeholder="2601.21296"
                    value={(cfg as any)?.effective?._retry_external_id || ''}
                    onChange={(e) =>
                      setCfg((prev) =>
                        prev
                          ? {
                              ...prev,
                              effective: {
                                ...(prev as any).effective,
                                _retry_external_id: e.target.value,
                              },
                            }
                          : prev
                      )
                    }
                  />
                </label>

                <label className="block text-xs text-white/60">
                  stage
                  <select
                    className="mt-1 w-full bg-gray-900 border border-white/10 rounded px-2 py-1 text-sm"
                    value={(cfg as any)?.effective?._retry_stage || 'mineru'}
                    onChange={(e) =>
                      setCfg((prev) =>
                        prev
                          ? {
                              ...prev,
                              effective: {
                                ...(prev as any).effective,
                                _retry_stage: e.target.value,
                              },
                            }
                          : prev
                      )
                    }
                  >
                    <option value="pdf">pdf</option>
                    <option value="mineru">mineru</option>
                    <option value="explain">explain</option>
                    <option value="caption">caption</option>
                    <option value="paper_images">paper_images</option>
                  </select>
                </label>

                <button
                  className="w-full px-3 py-2 text-sm rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                  onClick={() => {
                    const external_id = ((cfg as any)?.effective?._retry_external_id || '').trim();
                    const stage = ((cfg as any)?.effective?._retry_stage || 'mineru').trim();
                    enqueueJob('paper_retry_stage', { external_id, stage });
                  }}
                  disabled={loading}
                >
                  Enqueue retry
                </button>

                <div className="text-[11px] text-white/50">
                  Tip: for current blockers try external_id=2601.22027 stage=pdf, or external_id=2601.21296 stage=mineru.
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1">
                <button
                  className="px-3 py-2 text-sm rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50"
                  onClick={kickWorkerNow}
                  disabled={loading}
                >
                  Kick worker now
                </button>
                <button
                  className="px-3 py-2 text-sm rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                  onClick={truncateWorkerLogs}
                  disabled={loading}
                  title="Clear job_worker launchd out/err logs to reduce old noise"
                >
                  Clear worker logs
                </button>
              </div>

              <div className="text-xs text-white/50 space-y-1">
                <div>Job worker polls the queue every ~60s (launchd: com.papertok.job_worker).</div>
                <div>
                  worker err size: {workerMeta?.err?.size ?? '-'} bytes; out size: {workerMeta?.out?.size ?? '-'} bytes
                </div>
                {workerLogsTooBig && (
                  <div className="text-[11px] text-yellow-200/80">
                    Note: worker launchd logs are getting large. Consider “Clear worker logs” (after you’ve fixed the root cause) or lower PAPERTOK_LOGROTATE_MAX_BYTES.
                  </div>
                )}
                <div className="text-white/40">
                  Tip: old stack traces may remain in job_worker.launchd.err.log; use “Clear worker logs” after fixes.
                </div>
              </div>
            </div>

            <div className="border-t border-white/10 pt-3">
              <div className="text-xs text-white/60 mb-2">Recent jobs</div>
              <div className="space-y-2">
                {(jobs?.jobs || []).slice(0, 12).map((j: any) => (
                  <div key={j.id} className="border border-white/10 rounded p-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs text-white/80">
                        #{j.id} {j.job_type}
                      </div>
                      <div className="text-xs text-white/60">{j.status}</div>
                    </div>
                    <div className="text-[11px] text-white/50 mt-1">
                      created: {j.created_at}
                      {j.started_at ? ` | started: ${j.started_at}` : ''}
                      {j.finished_at ? ` | finished: ${j.finished_at}` : ''}
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <button
                        className="px-2 py-1 text-xs rounded bg-white/10 hover:bg-white/20"
                        onClick={() => viewJobLog(Number(j.id))}
                        disabled={loading}
                      >
                        Tail log
                      </button>
                      {j.error && <div className="text-[11px] text-red-200/80 truncate">{j.error}</div>}
                    </div>
                  </div>
                ))}
                {(!jobs || (jobs?.jobs || []).length === 0) && (
                  <div className="text-xs text-white/60">(no jobs yet)</div>
                )}
              </div>
            </div>
          </div>

          <div className="border border-white/10 rounded p-3 space-y-2">
            <div className="text-sm font-semibold">Job Log (tail)</div>
            <pre className="text-xs text-white/70 whitespace-pre-wrap break-words max-h-[60vh] overflow-auto">
              {jobLog || '(select a job)'}
            </pre>
          </div>
        </div>

        <div className="border border-white/10 rounded p-3 space-y-2">
          <div className="text-sm font-semibold">Config Raw (debug)</div>
          <pre className="text-xs text-white/70 whitespace-pre-wrap break-words max-h-[40vh] overflow-auto">
            {cfg ? JSON.stringify(cfg, null, 2) : '(loading...)'}
          </pre>
        </div>
      </div>
    </div>
  );
}
