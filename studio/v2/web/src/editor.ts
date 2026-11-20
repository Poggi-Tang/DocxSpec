import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { DraftContent, Template } from "./document";

export const contentOf = ({
  name,
  document,
  data,
}: DraftContent): DraftContent => ({
  name,
  document,
  data,
});

export const contentKey = (content: DraftContent) =>
  JSON.stringify(contentOf(content));

interface DraftRecord {
  key: string;
  bytes: string;
  template: Template;
  signature: string;
  modifiedAt: number;
}

export interface RecoverableDraft extends DraftRecord {
  sources: DraftRecord[];
}

interface EditingSession {
  key: symbol;
  draftKey: string;
  template: Template;
  contentKey: string;
  savedKey: string;
  savedVersion: number;
  localDraft: DraftRecord | null;
  undo: DraftContent[];
}

interface PendingSave {
  submittedKey: string;
  request: Promise<Template>;
}

const legacyKey = (id: string) => "ds-draft-" + id;
const draftPrefix = (id: string) => "ds-draft-v2:" + id + ":";
const newDraftKey = (id: string) => draftPrefix(id) + crypto.randomUUID();
const isDraftKey = (id: string, key: string) =>
  key === legacyKey(id) || key.startsWith(draftPrefix(id));

function readDrafts(id: string): DraftRecord[] {
  const records: DraftRecord[] = [];
  for (let index = 0; index < localStorage.length; index++) {
    const key = localStorage.key(index);
    if (!key || !isDraftKey(id, key)) continue;
    const bytes = localStorage.getItem(key);
    if (!bytes) continue;
    try {
      const parsed = JSON.parse(bytes);
      const template: Template =
        key === legacyKey(id) ? parsed : parsed.template;
      if (
        template?.id !== id ||
        typeof template.name !== "string" ||
        !Number.isInteger(template.version) ||
        template.version < 1 ||
        !template.data ||
        Array.isArray(template.data) ||
        typeof template.data !== "object" ||
        !Array.isArray(template.document?.nodes)
      )
        continue;
      const modifiedAt =
        key !== legacyKey(id) && Number.isFinite(parsed.modifiedAt)
          ? parsed.modifiedAt
          : Date.parse(template.updated) || 0;
      records.push({
        key,
        bytes,
        template,
        signature: contentKey(template),
        modifiedAt,
      });
    } catch {
      // A damaged record must not hide the other recoverable drafts.
    }
  }
  return records.sort((a, b) => b.modifiedAt - a.modifiedAt);
}

function groupDrafts(
  records: DraftRecord[],
  savedKey: string,
  active?: EditingSession,
): RecoverableDraft[] {
  const groups = new Map<string, RecoverableDraft>();
  for (const record of records) {
    if (record.key === active?.draftKey) continue;
    const { signature } = record;
    if (signature === savedKey) continue;
    if (
      signature === active?.contentKey &&
      record.template.version === active.template.version
    )
      continue;
    const identity = record.template.version + ":" + signature;
    const same = groups.get(identity);
    if (same) same.sources.push(record);
    else groups.set(identity, { ...record, sources: [record] });
  }
  return [...groups.values()];
}

function removeUnchangedDraft(record: DraftRecord) {
  if (localStorage.getItem(record.key) === record.bytes) {
    localStorage.removeItem(record.key);
  }
}

function withRecoveredDraft(
  active: EditingSession,
  draft: RecoverableDraft,
): EditingSession {
  return {
    ...active,
    // Outstanding edits for the replaced session must not apply to this branch.
    key: Symbol(active.template.id),
    draftKey: newDraftKey(active.template.id),
    template: {
      ...active.template,
      ...contentOf(draft.template),
      version: draft.template.version,
    },
    contentKey: contentKey(draft.template),
    localDraft: null,
    undo: [],
  };
}

export function useEditor(
  onSaved: (template: Template) => void,
  onDraftError: (message: string) => void,
) {
  const [session, setSession] = useState<EditingSession | null>(null);
  const [storedDrafts, setStoredDrafts] = useState<DraftRecord[]>([]);
  const current = useRef<EditingSession | null>(null);
  const pending = useRef(new Map<symbol, PendingSave>());
  const drafts = useMemo(
    () =>
      session
        ? groupDrafts(
            storedDrafts.filter(
              (draft) => draft.template.id === session.template.id,
            ),
            session.savedKey,
            session,
          )
        : [],
    [session, storedDrafts],
  );

  function refreshDrafts(active: EditingSession) {
    try {
      setStoredDrafts(readDrafts(active.template.id));
    } catch {
      onDraftError("无法读取这份模板的本机草稿。");
    }
  }

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      const active = current.current;
      if (
        active &&
        event.storageArea === localStorage &&
        (!event.key || isDraftKey(active.template.id, event.key))
      ) {
        refreshDrafts(active);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  function publish(next: EditingSession | null) {
    current.current = next;
    setSession(next);
  }

  function persist(next: EditingSession, includePending = true) {
    try {
      const submitted = includePending && pending.current.get(next.key);
      const dirty = next.contentKey !== next.savedKey;
      const pendingWillChangeContent =
        submitted && next.contentKey !== submitted.submittedKey;
      if (dirty || pendingWillChangeContent) {
        const draft: DraftRecord = {
          key: next.draftKey,
          template: next.template,
          signature: next.contentKey,
          modifiedAt: Date.now(),
          bytes: "",
        };
        draft.bytes = JSON.stringify({
          template: draft.template,
          modifiedAt: draft.modifiedAt,
        });
        localStorage.setItem(draft.key, draft.bytes);
        return { ...next, localDraft: draft };
      }
      if (next.localDraft) removeUnchangedDraft(next.localDraft);
      return { ...next, localDraft: null };
    } catch {
      onDraftError("本机草稿写入失败，请保存模板后再关闭页面。");
      return next;
    }
  }

  function load(template: Template) {
    const savedKey = contentKey(template);
    const clean: EditingSession = {
      key: Symbol(template.id),
      draftKey: newDraftKey(template.id),
      template,
      contentKey: savedKey,
      savedKey,
      savedVersion: template.version,
      localDraft: null,
      undo: [],
    };
    let records: DraftRecord[] = [];
    try {
      records = readDrafts(template.id);
    } catch {
      onDraftError("无法读取这份模板的本机草稿，已打开服务器版本。");
    }
    setStoredDrafts(records);
    const choices = groupDrafts(records, savedKey);
    if (
      choices.length === 1 &&
      choices[0].template.version === template.version
    ) {
      publish(persist(withRecoveredDraft(clean, choices[0])));
      return true;
    }
    // Keep the server version visible when a draft is stale or there are several branches.
    publish(clean);
    return false;
  }

  function restoreDraft(choice: RecoverableDraft) {
    const active = current.current;
    if (!active) return false;
    if (pending.current.has(active.key)) {
      onDraftError("请等待当前保存完成后再打开本机草稿。");
      return false;
    }
    try {
      const records = readDrafts(active.template.id);
      const candidates = groupDrafts(records, active.savedKey, active);
      const fresh = candidates.find((candidate) =>
        candidate.sources.some(
          (source) =>
            source.key === choice.key && source.bytes === choice.bytes,
        ),
      );
      if (!fresh) {
        setStoredDrafts(records);
        onDraftError("该草稿已变化，请重新选择。");
        return false;
      }
      const preserved = persist(active);
      if (
        active.contentKey !== active.savedKey &&
        (!preserved.localDraft ||
          contentKey(preserved.localDraft.template) !== active.contentKey ||
          preserved.localDraft.template.version !== active.template.version)
      )
        return false;
      const next = persist(withRecoveredDraft(preserved, fresh));
      if (!next.localDraft) return false;
      publish(next);
      refreshDrafts(next);
      return true;
    } catch {
      onDraftError("无法恢复这份本机草稿。");
      return false;
    }
  }

  function edit(
    change: (draft: DraftContent) => void,
    key = current.current?.key,
  ) {
    const active = current.current;
    if (!active || active.key !== key) return;
    const previous = contentOf(active.template);
    const draft = structuredClone(previous);
    change(draft);
    const signature = contentKey(draft);
    if (signature === active.contentKey) return;
    publish(
      persist({
        ...active,
        template: { ...active.template, ...draft },
        contentKey: signature,
        undo: [...active.undo.slice(-39), previous],
      }),
    );
  }

  function undo() {
    const active = current.current;
    const previous = active?.undo.at(-1);
    if (!previous) return;
    publish(
      persist({
        ...active,
        template: { ...active.template, ...previous },
        contentKey: contentKey(previous),
        undo: active.undo.slice(0, -1),
      }),
    );
  }

  function clearSavedDrafts(active: EditingSession, signature: string) {
    try {
      // An imported snapshot can still belong to another tab. Retire only content now saved.
      for (const record of readDrafts(active.template.id)) {
        if (record.signature === signature) removeUnchangedDraft(record);
      }
    } catch {
      onDraftError("已保存到服务器，暂时无法清理本机草稿。");
    }
  }

  async function save(key = current.current?.key) {
    const active = current.current;
    if (!active || active.key !== key) return;
    const inFlight = pending.current.get(key);
    if (inFlight) return inFlight.request;
    if (active.contentKey === active.savedKey) return active.template;

    const submitted = active.template;
    const request = api<Template>(
      "/templates/" + submitted.id,
      {
        ...contentOf(submitted),
        version: submitted.version,
        set_id: submitted.set_id,
      },
      "PUT",
    )
      .then((confirmed) => {
        const latest = current.current;
        if (latest?.key === key) {
          const unchanged = latest.contentKey === active.contentKey;
          const savedKey = contentKey(confirmed);
          clearSavedDrafts(latest, savedKey);
          const next = persist(
            {
              ...latest,
              template: unchanged
                ? confirmed
                : { ...confirmed, ...contentOf(latest.template) },
              contentKey: unchanged ? savedKey : latest.contentKey,
              savedKey,
              savedVersion: confirmed.version,
            },
            false,
          );
          publish(next);
          refreshDrafts(next);
        }
        onSaved(confirmed);
        return confirmed;
      })
      .finally(() => pending.current.delete(key));
    pending.current.set(key, { submittedKey: active.contentKey, request });
    return request;
  }

  async function waitForPendingSave(key: symbol) {
    // A copy must still work if the original is already in conflict.
    await pending.current.get(key)?.request.catch(() => {});
  }

  async function flush(key: symbol | undefined, isCurrent = () => true) {
    while (isCurrent() && current.current?.key === key) {
      const active = current.current;
      if (
        !active ||
        (active.contentKey === active.savedKey && !pending.current.has(key))
      ) {
        return true;
      }
      await save(key);
    }
    return false;
  }

  return {
    session,
    current,
    drafts,
    load,
    restoreDraft,
    edit,
    undo,
    save,
    waitForPendingSave,
    flush,
    close: () => {
      publish(null);
      setStoredDrafts([]);
    },
  };
}
