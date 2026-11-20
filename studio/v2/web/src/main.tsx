import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Plus,
  FloppyDisk,
  Play,
  DownloadSimple,
  FileText,
  Stack,
  MagicWand,
  TextH,
  Table,
  Image as ImageIcon,
  Trash,
  ArrowUp,
  ArrowDown,
  Copy,
  Clock,
  ArrowCounterClockwise,
} from "@phosphor-icons/react";
import { api, JobFailedError, pollJob, type Job } from "./api";
import {
  availableFields,
  captionTargets,
  cloneNode,
  flat,
  locateNodes,
} from "./document";
import type {
  DraftContent,
  ReportNode,
  Template,
  TemplateSummary,
} from "./document";
import { contentOf, useEditor, type RecoverableDraft } from "./editor";
import { DraftRecovery } from "./DraftRecovery";
import {
  ColorParameter,
  ComponentContent,
  NumberParameter,
} from "./ComponentFields";
import { PdfPreview, type RenderResult } from "./PdfPreview";
import { StudioDialog } from "./StudioDialog";
import {
  ConversionNotice,
  ConversionUpload,
  ReviewWorkspace,
  type ConversionReview,
  type ConversionTask,
} from "./StudioConversion";
import { TemplateSetup } from "./TemplateSetup";
import { TestDataEditor } from "./TestDataEditor";
import "./style.css";
import "./component-editing.css";

const names: any = {
  heading: "标题",
  paragraph: "正文",
  table: "表格",
  caption: "题注",
  image: "图片",
  repeat: "重复区块",
  condition: "条件区块",
  pagebreak: "分页",
  section: "分节",
  toc: "目录",
  group: "组合",
};
const icon = (kind: string) =>
  kind === "table" ? (
    <Table />
  ) : kind === "image" ? (
    <ImageIcon />
  ) : kind === "heading" ? (
    <TextH />
  ) : (
    <FileText />
  );
interface TemplateSet {
  id: string;
  name: string;
  engine: string;
}
interface Component {
  id?: string;
  name: string;
  version?: number;
  node: ReportNode;
  builtin?: boolean;
}
interface Bootstrap {
  sets: TemplateSet[];
  templates: TemplateSummary[];
  presets: Component[];
  engines: { id: string; name: string; available: boolean; reason: string }[];
  ai: { configured: boolean; destination: string; model: string };
}
interface Preview {
  templateId: string;
  downloadName: string;
  version: number;
  engine: string;
  contentKey: string;
  job: Job<RenderResult>;
}
interface RenderRequest {
  jobId?: string;
}
type Dialog =
  | { kind: "data"; sessionKey: symbol }
  | { kind: "create-set" }
  | { kind: "create-template"; setId: string }
  | { kind: "versions"; sessionKey: symbol; versions: TemplateSummary[] }
  | { kind: "ai"; setId: string }
  | { kind: "review"; templateId: string };

interface ImageUpload {
  sessionKey: symbol;
  completion: Promise<boolean>;
}

type InsertionPoint =
  { kind: "append" } | { kind: "before" | "after" | "inside"; nodeId: string };

const componentMime = "application/x-docxspec-component";
const containerKinds = new Set(["repeat", "condition", "section", "group"]);
const numericStyles = {
  size: { min: 5, max: 72, unit: " pt" },
  before: { min: 0, max: 144, unit: " pt" },
  after: { min: 0, max: 144, unit: " pt" },
  line: { min: 1, max: 3, unit: " 倍" },
};

function edgeAt(y: number, bounds: DOMRect, container: boolean) {
  const relative = (y - bounds.top) / Math.max(1, bounds.height);
  if (container && relative >= 0.25 && relative < 0.75) return "inside";
  return relative < 0.5 ? "before" : "after";
}

function nodeName(node: ReportNode) {
  return node.label.trim() || node.text.trim() || names[node.kind];
}

function App() {
  const [dragSession, setDragSession] = useState<symbol>();
  const [dropIndicator, setDropIndicator] = useState<{
    zone: string;
    point: InsertionPoint;
  }>();
  const [styleReset, setStyleReset] = useState(0);
  const inspectorProperties = useRef<HTMLDivElement>(null);
  const inspectorEntry = useRef<{
    trigger: HTMLElement;
    panel: "browse" | "document" | "properties";
    sessionKey: symbol;
  }>(undefined);
  const [boot, B] = useState<Bootstrap>(),
    [setId, S] = useState(""),
    [selected, SEL] = useState(""),
    [components, C] = useState<Record<string, Component[]>>({}),
    [error, E] = useState(""),
    [message, M] = useState(""),
    [rendered, setRendered] = useState<Preview>(),
    [rendering, setRendering] = useState(false),
    [saving, setSaving] = useState<symbol>(),
    [pendingEngines, setPendingEngines] = useState<Record<string, string>>({}),
    [mode, MODE] = useState("preview"),
    [dialog, setDialogState] = useState<Dialog | null>(null),
    [panel, setPanel] = useState<"browse" | "document" | "properties">(
      "document",
    ),
    [reviews, setReviews] = useState<Record<string, ConversionReview | null>>(
      {},
    ),
    [conversionTask, setConversionTask] = useState<ConversionTask>();
  const converting = useRef(false);
  const navigation = useRef(0);
  const dialogIntent = useRef(0);
  const archiveOperation = useRef<Promise<void> | null>(null);
  const renderRequest = useRef<RenderRequest | null>(null);
  const [pdfControls, setPdfControls] = useState<HTMLDivElement | null>(null);
  const imageRequests = useRef(new Map<string, ImageUpload>());

  function showDialog(next: Dialog | null) {
    ++dialogIntent.current;
    setDialogState(next);
  }

  function selectComponent(id: string) {
    SEL(id);
    setPanel("properties");
  }

  function updateTemplate(template: TemplateSummary) {
    const { id, set_id, name, version, updated, archived } = template;
    B((previous) => {
      if (!previous) return previous;
      const existing = previous.templates.find((entry) => entry.id === id);
      if (!archived && existing && existing.version > version) return previous;
      const remaining = previous.templates.filter((entry) => entry.id !== id);
      return {
        ...previous,
        templates: archived
          ? remaining
          : [{ id, set_id, name, version, updated }, ...remaining],
      };
    });
  }

  const editor = useEditor(updateTemplate, E);
  const session = editor.session;
  const tpl = session?.template;
  const dirty = session && session.contentKey !== session.savedKey;
  const ownerSetId = tpl?.set_id ?? setId;
  const currentSet = boot?.sets.find((set) => set.id === ownerSetId);
  const pendingEngine = pendingEngines[ownerSetId];
  const engine = pendingEngine ?? currentSet?.engine ?? "word";
  const engineOption = boot?.engines.find((option) => option.id === engine);
  const availableEngine = boot?.engines.find((option) => option.available);
  const browsingSet = boot?.sets.find((set) => set.id === setId);
  const custom = components[ownerSetId] ?? [];
  const activePreview =
    rendered && rendered.templateId === tpl?.id && rendered.engine === engine
      ? rendered
      : undefined;
  const job = activePreview?.job;
  const stale =
    activePreview && activePreview.contentKey !== session.contentKey;
  const locations = useMemo(
    () => locateNodes(tpl?.document.nodes ?? []),
    [tpl?.document.nodes],
  );
  const location = locations.find(({ node }) => node.id === selected);
  const node = location?.node;
  const fields = useMemo(
    () => (location && tpl ? availableFields(tpl.data, location) : []),
    [location, tpl?.data],
  );
  const targets =
    node?.kind === "caption" ? captionTargets(location, locations) : [];
  const usableWidth =
    tpl && tpl.document.page.width - 2 * tpl.document.page.margin;
  const previewColumnWidths =
    node?.kind === "table"
      ? node.columns.length
        ? node.columns
        : node.rows[0].map(() => usableWidth / node.rows[0].length)
      : [];
  const currentReview = tpl ? reviews[tpl.id] : undefined;
  const conversionTarget =
    dialog?.kind === "ai"
      ? boot?.sets.find((set) => set.id === dialog.setId)
      : undefined;

  const run = async (fn: () => Promise<unknown>) => {
    E("");
    try {
      await fn();
    } catch (reason) {
      E(reason.message);
    }
  };

  useEffect(() => {
    void run(async () => {
      const data = await api<Bootstrap>("/bootstrap");
      B(data);
      S(data.sets[0]?.id ?? "");
    });
  }, []);

  useEffect(() => {
    if (!ownerSetId) return;
    let active = true;
    api<Component[]>("/components?set_id=" + ownerSetId)
      .then((loaded) => {
        if (active)
          C((previous) => {
            const all = new Map(
              loaded.map((component) => [component.id, component]),
            );
            for (const component of previous[ownerSetId] ?? [])
              all.set(component.id, component);
            return { ...previous, [ownerSetId]: [...all.values()] };
          });
      })
      .catch((reason) => {
        if (active) E(reason.message);
      });
    return () => {
      active = false;
    };
  }, [ownerSetId]);

  useEffect(() => {
    const id = tpl?.id;
    if (!id || reviews[id] !== undefined) return;
    let active = true;
    api<ConversionReview | null>("/templates/" + id + "/review")
      .then((review) => {
        if (active) setReviews((previous) => ({ ...previous, [id]: review }));
      })
      .catch((reason) => {
        if (active) E(reason.message);
      });
    return () => {
      active = false;
    };
  }, [tpl?.id]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      const active = editor.current.current;
      if (
        active &&
        (active.contentKey !== active.savedKey ||
          pendingImages(active.key).length)
      ) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, []);

  function cancelRender(jobId: string) {
    // A superseded job must not report cancellation errors in the new editor.
    void api("/jobs/" + jobId, undefined, "DELETE").catch(() => {});
  }

  // Each document open and engine change invalidates outstanding previews.
  function clearPreview() {
    const jobId = renderRequest.current?.jobId;
    renderRequest.current = null;
    setRendering(false);
    setRendered(undefined);
    if (jobId) cancelRender(jobId);
  }

  function showTemplate(template: Template) {
    const recovered = editor.load(template);
    S(template.set_id);
    SEL("");
    setPanel("document");
    showDialog(null);
    clearPreview();
    M(recovered ? "已恢复本机未保存草稿，请核对后保存" : "");
  }

  function pendingImages(sessionKey: symbol | undefined) {
    return [...imageRequests.current.values()].filter(
      (upload) => upload.sessionKey === sessionKey,
    );
  }

  async function settleOutgoing(
    from: symbol | undefined,
    isCurrent: () => boolean,
    action: "save" | "uploads" | "pending-save",
  ) {
    const uploadMessage = "正在等待图片上传完成";
    while (isCurrent()) {
      const uploads = pendingImages(from);
      if (uploads.length) {
        M(uploadMessage);
        const results = await Promise.all(
          uploads.map((upload) => upload.completion),
        );
        M((message) => (message === uploadMessage ? "" : message));
        if (!results.every(Boolean)) return false;
        continue;
      }
      if (action === "save" && !(await editor.flush(from, isCurrent)))
        return false;
      if (action === "pending-save" && from)
        await editor.waitForPendingSave(from);
      // A new upload may have started while a save was in progress.
      if (!pendingImages(from).length) return isCurrent();
    }
    return false;
  }

  async function navigate(
    load: () => Promise<Template>,
    saveOutgoing = true,
    wanted = () => true,
  ) {
    const request = ++navigation.current;
    await archiveOperation.current;
    if (navigation.current !== request || !wanted()) return false;
    const from = editor.current.current?.key;
    const isCurrent = () =>
      navigation.current === request &&
      editor.current.current?.key === from &&
      wanted();
    if (
      !(await settleOutgoing(
        from,
        isCurrent,
        saveOutgoing ? "save" : "uploads",
      ))
    )
      return false;
    const target = await load();
    // The source can be edited while the target is being loaded.
    if (
      !(await settleOutgoing(
        from,
        isCurrent,
        saveOutgoing ? "save" : "pending-save",
      )) ||
      !isCurrent()
    ) {
      return false;
    }
    showTemplate(target);
    return true;
  }

  async function open(id: string) {
    const active = editor.current.current?.template;
    if (active?.id === id) {
      ++navigation.current;
      S(active.set_id);
      setPanel("document");
      return true;
    }
    return navigate(() => api<Template>("/templates/" + id));
  }

  async function save() {
    const key = editor.current.current?.key;
    if (!key) return;
    setSaving(key);
    try {
      const result = await editor.save(key);
      const active = editor.current.current;
      if (result && active?.key === key) {
        const stillDirty = active.contentKey !== active.savedKey;
        M(
          "已保存 v" +
            result.version +
            (stillDirty ? "，还有更新的改动未保存" : ""),
        );
      }
    } finally {
      setSaving((current) => (current === key ? undefined : current));
    }
  }

  const createSet = () => showDialog({ kind: "create-set" });
  const createTemplate = () =>
    setId ? showDialog({ kind: "create-template", setId }) : createSet();

  async function submitSetup(
    kind: "create-set" | "create-template",
    name: string,
    engine: string,
  ) {
    const intent = dialogIntent.current;
    E("");
    const wanted = () => dialogIntent.current === intent;
    if (kind === "create-set") {
      const set = await api<TemplateSet>("/sets", { name, engine });
      B((previous) => ({ ...previous, sets: [...previous.sets, set] }));
      if (wanted()) {
        ++navigation.current;
        S(set.id);
        if (!editor.current.current) setPanel("document");
        showDialog(null);
      }
    } else if (dialog?.kind === "create-template") {
      const targetSetId = dialog.setId;
      await navigate(
        async () => {
          const defaults = await api<DraftContent>("/default");
          const template = await api<Template>("/templates", {
            ...defaults,
            name,
            set_id: targetSetId,
          });
          updateTemplate(template);
          return template;
        },
        true,
        wanted,
      );
    }
  }

  const copyTemplate = () =>
    run(async () => {
      if (!editor.current.current) return;
      await navigate(async () => {
        const active = editor.current.current;
        if (!active) throw new Error("原模板已关闭");
        const source = active.template;
        const template = await api<Template>("/templates", {
          ...contentOf(source),
          name: source.name + " · 副本",
          set_id: source.set_id,
        });
        updateTemplate(template);
        return template;
      }, false);
    });

  function recoverDraft(draft: RecoverableDraft) {
    const active = editor.current.current;
    if (
      !active ||
      archiveOperation.current ||
      pendingImages(active.key).length
    ) {
      E("请等当前操作完成后再打开本机草稿。");
      return false;
    }
    E("");
    if (!editor.restoreDraft(draft)) return false;
    SEL("");
    setPanel("document");
    showDialog(null);
    clearPreview();
    M("已恢复本机草稿，请核对后保存");
    return true;
  }

  const archiveTemplate = () =>
    run(async () => {
      const active = editor.current.current;
      if (
        !active ||
        archiveOperation.current ||
        !confirm("归档此模板？历史版本会保留。")
      )
        return;
      ++navigation.current;
      const isCurrent = () => editor.current.current?.key === active.key;
      const operation = (async () => {
        if (!(await settleOutgoing(active.key, isCurrent, "save"))) return;
        await api("/templates/" + active.template.id, undefined, "DELETE");
        try {
          if (
            !(await settleOutgoing(active.key, isCurrent, "save")) ||
            !isCurrent()
          )
            return;
          editor.close();
          SEL("");
          setPanel("document");
          showDialog(null);
          M("");
          clearPreview();
        } finally {
          updateTemplate({ ...active.template, archived: 1 });
        }
      })();
      archiveOperation.current = operation;
      try {
        await operation;
      } finally {
        archiveOperation.current = null;
      }
    });

  const edit = editor.edit;
  const patch = (updates: Partial<ReportNode>) =>
    edit((draft) => {
      const target = flat(draft.document.nodes).find(
        (entry) => entry.id === selected,
      );
      if (target) Object.assign(target, updates);
    }, session?.key);

  function siblings(nodes: ReportNode[], id: string) {
    return [nodes, ...flat(nodes).map((entry) => entry.children)].find((list) =>
      list.some((entry) => entry.id === id),
    );
  }

  function selectForEdit(id: string, keyboard: boolean) {
    const trigger = document.activeElement;
    if (
      keyboard &&
      session &&
      trigger instanceof HTMLElement &&
      !inspectorProperties.current?.contains(trigger)
    ) {
      inspectorEntry.current = { trigger, panel, sessionKey: session.key };
    } else if (!keyboard) inspectorEntry.current = undefined;
    selectComponent(id);
    if (keyboard) {
      requestAnimationFrame(() => {
        const panel = inspectorProperties.current;
        const control =
          panel?.querySelector("textarea") ??
          panel?.querySelector<HTMLElement>("input, select");
        (control ?? panel)?.focus();
      });
    }
  }

  function finishEditing() {
    const previous = inspectorEntry.current;
    inspectorEntry.current = undefined;
    SEL("");
    if (!previous || previous.sessionKey !== session?.key) {
      setPanel("document");
      return;
    }
    setPanel(previous.panel);
    requestAnimationFrame(() => {
      if (previous.trigger.isConnected) previous.trigger.focus();
    });
  }

  const clickInsertion: InsertionPoint = node
    ? {
        kind: containerKinds.has(node.kind) ? "inside" : "after",
        nodeId: node.id,
      }
    : { kind: "append" };

  function insertionDescription(point: InsertionPoint) {
    if (point.kind === "append") return "添加到文档末尾";
    const anchor = locations.find(({ node }) => node.id === point.nodeId)?.node;
    const label = anchor ? nodeName(anchor).slice(0, 22) : "选中组件";
    return point.kind === "inside"
      ? "添加到「" + label + "」内"
      : "插入「" + label + "」" + (point.kind === "before" ? "之前" : "之后");
  }

  const insert = (
    component: Component,
    point = clickInsertion,
    duplicate = false,
    keyboard = false,
  ) => {
    const added = cloneNode(component.node, duplicate);
    added.component_id = component.id;
    added.component_version = component.version;
    if (component.builtin && added.kind === "heading") added.label = "";
    let inserted = false;
    edit((draft) => {
      const { nodes } = draft.document;
      if (point.kind === "append") {
        nodes.push(added);
      } else if (point.kind === "inside") {
        const parent = flat(nodes).find((entry) => entry.id === point.nodeId);
        if (!parent || !containerKinds.has(parent.kind)) return;
        parent.children.push(added);
      } else {
        const list = siblings(nodes, point.nodeId);
        if (!list) return;
        const index = list.findIndex((entry) => entry.id === point.nodeId);
        list.splice(index + (point.kind === "after" ? 1 : 0), 0, added);
      }
      inserted = true;
    }, session?.key);
    if (!inserted) return;
    selectForEdit(added.id, keyboard);
    M("已添加 " + component.name + "，位置：" + insertionDescription(point));
  };

  function startComponentDrag(event: React.DragEvent, component: Component) {
    if (!component.id || !session) return;
    event.dataTransfer.setData(componentMime, component.id);
    event.dataTransfer.effectAllowed = "copy";
    setDragSession(session.key);
    setDropIndicator(undefined);
  }

  function endComponentDrag() {
    setDragSession(undefined);
    setDropIndicator(undefined);
  }

  const draggingComponent = !!session && dragSession === session.key;

  function dropAttributes(
    zone: string,
    pointAt: (event: React.DragEvent<HTMLElement>) => InsertionPoint,
  ) {
    function accepts(event: React.DragEvent) {
      return (
        draggingComponent &&
        Array.from(event.dataTransfer.types).includes(componentMime)
      );
    }
    return {
      onDragOver(event: React.DragEvent<HTMLElement>) {
        if (!accepts(event)) return;
        event.preventDefault();
        event.stopPropagation();
        event.dataTransfer.dropEffect = "copy";
        const point = pointAt(event);
        setDropIndicator((current) =>
          current?.zone === zone && current.point.kind === point.kind
            ? current
            : { zone, point },
        );
      },
      onDragLeave(event: React.DragEvent<HTMLElement>) {
        if (
          event.relatedTarget instanceof Node &&
          event.currentTarget.contains(event.relatedTarget)
        )
          return;
        setDropIndicator((current) =>
          current?.zone === zone ? undefined : current,
        );
      },
      onDrop(event: React.DragEvent<HTMLElement>) {
        if (!accepts(event)) return;
        event.preventDefault();
        event.stopPropagation();
        const id = event.dataTransfer.getData(componentMime);
        const component = [...boot.presets, ...custom].find(
          (item) => item.id === id,
        );
        if (component) insert(component, pointAt(event));
        endComponentDrag();
      },
    };
  }

  function dropClass(zone: string) {
    const side =
      draggingComponent &&
      dropIndicator?.zone === zone &&
      dropIndicator.point.kind;
    return side
      ? " component-drop-" + side + (side === "append" ? "-active" : "")
      : "";
  }

  const move = (delta: number) =>
    edit((draft) => {
      const list = siblings(draft.document.nodes, selected);
      if (!list) return;
      const i = list.findIndex((entry) => entry.id === selected);
      if (i + delta >= 0 && i + delta < list.length) {
        const [moved] = list.splice(i, 1);
        list.splice(i + delta, 0, moved);
      }
    }, session?.key);

  const remove = () => {
    edit((draft) => {
      const list = siblings(draft.document.nodes, selected);
      if (!list) return;
      const [removed] = list.splice(
        list.findIndex((entry) => entry.id === selected),
        1,
      );
      const removedIds = new Set(flat([removed]).map((entry) => entry.id));
      for (const entry of flat(draft.document.nodes)) {
        if (removedIds.has(entry.target)) entry.target = "";
      }
    }, session?.key);
    SEL("");
  };

  function uploadImage(
    file: File,
    nodeId: string,
    templateId: string,
    key: symbol,
  ) {
    const slot = templateId + ":" + nodeId;
    const form = new FormData();
    form.append("file", file);
    E("");
    const current = () =>
      imageRequests.current.get(slot) === request &&
      editor.current.current?.key === key;
    const request: ImageUpload = {
      sessionKey: key,
      completion: api<{ id: string }>("/assets", form)
        .then((asset) => {
          if (current()) {
            edit((draft) => {
              const target = flat(draft.document.nodes).find(
                (entry) => entry.id === nodeId,
              );
              if (target?.kind === "image") target.asset = asset.id;
            }, key);
          }
          return true;
        })
        .catch((reason) => {
          if (!current()) return true;
          E(reason.message);
          return false;
        })
        .finally(() => {
          if (imageRequests.current.get(slot) === request)
            imageRequests.current.delete(slot);
        }),
    };
    imageRequests.current.set(slot, request);
  }

  async function changeEngine(next: string) {
    if (!currentSet || pendingEngine || next === engine) return;
    const owner = currentSet.id;
    clearPreview();
    M("");
    setPendingEngines((previous) => ({ ...previous, [owner]: next }));
    try {
      const updated = await api<TemplateSet>(
        "/sets/" + owner,
        { name: currentSet.name, engine: next },
        "PUT",
      );
      B((previous) => ({
        ...previous,
        sets: previous.sets.map((set) => (set.id === owner ? updated : set)),
      }));
    } finally {
      setPendingEngines((previous) => {
        const remaining = { ...previous };
        delete remaining[owner];
        return remaining;
      });
    }
  }

  async function preview() {
    const active = editor.current.current;
    if (
      !active ||
      renderRequest.current ||
      pendingEngine ||
      !engineOption?.available
    )
      return;
    E("");
    const request: RenderRequest = {};
    renderRequest.current = request;
    const ownsRequest = () =>
      renderRequest.current === request &&
      editor.current.current?.key === active.key;
    // Save responses can normalize content, but only edits change the undo history.
    const keepsInput = () =>
      ownsRequest() && editor.current.current?.undo === active.undo;
    setRendering(true);
    setPanel("document");
    M("正在准备预览");
    try {
      if (!(await editor.flush(active.key, keepsInput)) || !keepsInput()) {
        if (ownsRequest()) M("模板在准备预览期间已修改，请重新更新预览");
        return;
      }
      const prepared = editor.current.current;
      const template = prepared.template;
      const signature = prepared.contentKey;
      const queued = await api<{ id: string }>("/renders", {
        document: template.document,
        data: template.data,
        engine,
      });
      if (!ownsRequest()) {
        cancelRender(queued.id);
        return;
      }
      request.jobId = queued.id;
      const finished = await pollJob<RenderResult>(queued.id, M, ownsRequest);
      if (!finished || !ownsRequest()) return;
      if (finished.result.engine !== engine)
        throw new Error("排版结果与所选引擎不一致");
      if (editor.current.current?.contentKey !== signature) {
        M("模板在排版期间已修改，请重新更新预览");
        return;
      }
      setRendered({
        templateId: template.id,
        downloadName: template.name,
        version: template.version,
        engine,
        contentKey: signature,
        job: finished,
      });
      MODE("preview");
      M("真实预览已生成 · " + finished.result.pages + " 页");
    } catch (reason) {
      if (ownsRequest()) {
        E(reason.message);
        M("");
      }
    } finally {
      if (renderRequest.current === request) {
        renderRequest.current = null;
        setRendering(false);
      }
    }
  }

  async function convert(
    file: File,
    target: Pick<TemplateSet, "id" | "name">,
    resumeJobId?: string,
  ) {
    if (converting.current) return;
    converting.current = true;
    let jobId = resumeJobId;
    const report = { fileName: file.name, target };
    const progress = (message: string) =>
      setConversionTask({ phase: "running", ...report, progress: message });
    progress(jobId ? "正在查询转换结果" : "正在上传报告");
    try {
      if (!jobId) {
        const form = new FormData();
        form.append("file", file);
        const suffix = " · AI 模板";
        const basename = Array.from(file.name.replace(/\.docx$/i, ""))
          .slice(0, 100 - suffix.length)
          .join("");
        const query = new URLSearchParams({
          set_id: target.id,
          name: (basename || "报告") + suffix,
        });
        jobId = (await api<{ id: string }>("/conversions?" + query, form)).id;
      }
      const finished = await pollJob<{ template_id: string }>(jobId, progress);
      const id = finished.result.template_id;
      const [template, review] = await Promise.all([
        api<Template>("/templates/" + id),
        api<ConversionReview | null>("/templates/" + id + "/review"),
      ]);
      if (!review) throw new Error("转换完成，但暂时无法读取审核内容。");
      setReviews((previous) => ({
        ...previous,
        [id]: review,
      }));
      updateTemplate(template);
      setConversionTask({ phase: "complete", ...report, template });
    } catch (reason) {
      setConversionTask({
        phase: "failed",
        file,
        target,
        error: reason instanceof Error ? reason.message : "转换失败，请重试。",
        resumeJobId: reason instanceof JobFailedError ? undefined : jobId,
      });
    } finally {
      converting.current = false;
    }
  }

  async function markReview(
    templateId: string,
    index: number,
    reviewed: boolean,
  ) {
    const updated = await api<Pick<ConversionReview, "reviewed_indices">>(
      "/templates/" + templateId + "/review/" + index,
      { reviewed },
      "PUT",
    );
    setReviews((previous) => {
      const current = previous[templateId];
      return current
        ? { ...previous, [templateId]: { ...current, ...updated } }
        : previous;
    });
  }

  const openReview = (id: string) =>
    run(async () => {
      if (editor.current.current?.template.id !== id && !(await open(id)))
        return;
      if (editor.current.current?.template.id === id)
        showDialog({ kind: "review", templateId: id });
    });

  const listVersions = () =>
    run(async () => {
      const active = editor.current.current;
      if (!active) return;
      const intent = ++dialogIntent.current;
      const versions = await api<TemplateSummary[]>(
        "/templates/" + active.template.id + "/versions",
      );
      if (
        dialogIntent.current === intent &&
        editor.current.current?.key === active.key
      ) {
        showDialog({ kind: "versions", sessionKey: active.key, versions });
      }
    });

  async function restoreVersion(
    version: number,
    restoring: Extract<Dialog, { kind: "versions" }>,
  ) {
    const active = editor.current.current;
    if (active?.key !== restoring.sessionKey) return;
    const intent = ++dialogIntent.current;
    const old = await api<DraftContent>(
      "/templates/" + active.template.id + "/versions/" + version,
    );
    if (
      dialogIntent.current !== intent ||
      editor.current.current?.key !== active.key
    )
      return;
    if (editor.current.current.contentKey !== active.contentKey) {
      M("模板在读取历史版本期间已修改，请重新选择要恢复的版本");
      return;
    }
    edit((draft) => Object.assign(draft, contentOf(old)), active.key);
    showDialog(null);
    M("已恢复到编辑区，保存后形成新版本");
  }

  const canRender =
    !!tpl && !rendering && !pendingEngine && !!engineOption?.available;
  const outline = (
    nodes: ReportNode[],
    depth = 0,
    panel = "outline",
  ): React.ReactNode =>
    nodes.map((n) => {
      const zone = panel + ":" + n.id;
      return (
        <React.Fragment key={n.id}>
          <button
            type="button"
            className={
              "tree-node component-drop-anchor" +
              (selected === n.id ? " active" : "") +
              dropClass(zone)
            }
            style={{ paddingLeft: 12 + depth * 15 }}
            aria-pressed={selected === n.id}
            aria-controls={
              selected === n.id ? "component-properties" : undefined
            }
            onClick={(event) => selectForEdit(n.id, event.detail === 0)}
            {...dropAttributes(zone, (event) => ({
              kind: edgeAt(
                event.clientY,
                event.currentTarget.getBoundingClientRect(),
                containerKinds.has(n.kind),
              ),
              nodeId: n.id,
            }))}
          >
            {icon(n.kind)}
            <span>{nodeName(n)}</span>
            <small>{n.kind === "heading" ? "H" + n.level : ""}</small>
          </button>
          {outline(n.children, depth + 1, panel)}
        </React.Fragment>
      );
    });
  const styleField = (label: string, key: keyof typeof numericStyles) => (
    <NumberParameter
      key={node.id + ":" + key + ":" + styleReset}
      label={label}
      value={node.style[key]}
      placeholder="继承 DS 样式"
      allowEmpty
      {...numericStyles[key]}
      update={(value) => patch({ style: { ...node.style, [key]: value } })}
    />
  );
  if (!boot)
    return <div className="loading">正在打开 DocxSpec Studio…{error}</div>;
  return (
    <>
      <header>
        <div className="brand">
          <b>DS</b>
          <strong>
            DocxSpec <span>Studio</span>
          </strong>
          <em>模板工作台</em>
        </div>
        <div className="header-actions">
          <span className="save-state">
            {tpl ? (dirty ? "● 未保存" : "✓ 已保存") : ""}
          </span>
          {session && editor.drafts.length > 0 && (
            <DraftRecovery
              drafts={editor.drafts}
              serverVersion={session.savedVersion}
              recover={recoverDraft}
            />
          )}
          <button
            disabled={!tpl || saving === session?.key}
            onClick={() => run(save)}
          >
            <FloppyDisk />
            保存
          </button>
          <button
            className="primary"
            disabled={!canRender}
            title={!engineOption?.available ? engineOption?.reason : undefined}
            onClick={preview}
          >
            <Play />
            {rendering ? "处理中…" : "更新预览"}
          </button>
        </div>
      </header>
      <nav className="workspace-switch" aria-label="工作区面板">
        <button
          type="button"
          aria-pressed={panel === "browse"}
          onClick={() => setPanel("browse")}
        >
          模板与结构
        </button>
        <button
          type="button"
          aria-pressed={panel === "document"}
          onClick={() => setPanel("document")}
        >
          画布与组件
        </button>
        <button
          type="button"
          aria-pressed={panel === "properties"}
          disabled={!tpl}
          onClick={() => setPanel("properties")}
        >
          属性
        </button>
      </nav>
      <div
        className="workspace"
        data-panel={panel}
        data-template={tpl ? "yes" : "no"}
      >
        <aside className="navigation">
          <div className="section-head">
            <span>模板管理</span>
            {boot.sets.length > 0 && (
              <button
                aria-label="添加模板集"
                title="新建模板集"
                onClick={createSet}
              >
                <Plus />
              </button>
            )}
          </div>
          <div className="sets">
            {boot.sets.map((s: any) => (
              <div key={s.id}>
                <button
                  className={"set " + (s.id === setId ? "selected" : "")}
                  onClick={() => {
                    ++navigation.current;
                    S(s.id);
                  }}
                >
                  <Stack />
                  {s.name}
                </button>
                {s.id === setId &&
                  boot.templates
                    .filter((t: any) => t.set_id === s.id)
                    .map((t: any) => (
                      <button
                        key={t.id}
                        className={
                          "template " + (tpl?.id === t.id ? "active" : "")
                        }
                        onClick={() => run(() => open(t.id))}
                      >
                        <FileText />
                        {t.name}
                      </button>
                    ))}
              </div>
            ))}
            {!boot.sets.length && (
              <p className="hint">先创建模板集，集中管理报告模板和组件。</p>
            )}
          </div>
          {setId ? (
            <button className="new-template" onClick={createTemplate}>
              <Plus />
              新建模板
            </button>
          ) : (
            <button
              className="new-template first-set-in-nav"
              onClick={createSet}
            >
              <Plus />
              新建模板集
            </button>
          )}
          <button
            className="ai-button"
            disabled={!setId}
            onClick={() => showDialog({ kind: "ai", setId })}
          >
            <MagicWand />
            AI 转化模板
          </button>
          <div className="section-head outline-head">
            <span>文档结构</span>
            <small>{tpl ? flat(tpl.document.nodes).length : 0} 个组件</small>
          </div>
          <div className="outline">{tpl && outline(tpl.document.nodes)}</div>
          <div className="nav-footer">DS 母版样式 · 组件化模板</div>
        </aside>
        <main>
          <div className="document-bar">
            <div>
              <FileText />
              <strong>{tpl?.name || "创建你的报告模板"}</strong>
              {tpl && <span className="badge">v{tpl.version}</span>}
              {tpl && tpl.version !== session.savedVersion && (
                <span className="badge" title="可用“复制模板”另存此草稿">
                  服务器 v{session.savedVersion}
                </span>
              )}
              {tpl && currentSet && tpl.set_id !== setId && (
                <span className="badge">{currentSet.name}</span>
              )}
            </div>
            <div>
              <button
                title="撤销"
                disabled={!session?.undo.length}
                onClick={editor.undo}
              >
                <ArrowCounterClockwise />
              </button>
              <button
                disabled={!tpl}
                onClick={() =>
                  showDialog({ kind: "data", sessionKey: session.key })
                }
              >
                测试数据
              </button>
              <button title="历史版本" disabled={!tpl} onClick={listVersions}>
                <Clock />
              </button>
              {currentReview && (
                <button onClick={() => openReview(tpl.id)}>转换审核</button>
              )}
            </div>
          </div>
          <div className="preview-toolbar">
            <div className="segmented">
              <button
                className={mode === "preview" ? "on" : ""}
                onClick={() => MODE("preview")}
              >
                真实预览
              </button>
              <button
                className={mode === "structure" ? "on" : ""}
                onClick={() => MODE("structure")}
              >
                组件结构
              </button>
            </div>
            <select
              aria-label="排版引擎"
              value={engine}
              disabled={!currentSet || !!pendingEngine}
              onChange={(e) => {
                const value = e.currentTarget.value;
                void run(() => changeEngine(value));
              }}
            >
              {boot.engines.map((e: any) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                  {!e.available ? " · 不可用" : ""}
                </option>
              ))}
            </select>
            <button
              disabled={!job || stale || !!pendingEngine}
              onClick={() => {
                if (
                  activePreview?.contentKey ===
                    editor.current.current?.contentKey &&
                  activePreview?.templateId ===
                    editor.current.current?.template.id &&
                  job &&
                  !pendingEngine
                ) {
                  const query = new URLSearchParams({
                    download_name: activePreview.downloadName,
                    download_version: String(activePreview.version),
                  });
                  const link = document.createElement("a");
                  link.href =
                    "/api/v2/artifacts/" + job.id + "/report.docx?" + query;
                  link.download = "";
                  link.click();
                }
              }}
            >
              <DownloadSimple />
              DOCX
            </button>
          </div>
          {job && mode === "preview" && <div ref={setPdfControls} />}
          {error && (
            <div className="error" role="alert">
              {error}
              <button onClick={() => E("")}>×</button>
            </div>
          )}
          {message && (
            <div className="status" role="status">
              {message}
            </div>
          )}
          {conversionTask && dialog?.kind !== "ai" && (
            <ConversionNotice
              task={conversionTask}
              onOpenReview={openReview}
              onOpenConversion={(id) => showDialog({ kind: "ai", setId: id })}
              onDismiss={() => setConversionTask(undefined)}
            />
          )}
          <div className="canvas">
            {!tpl || mode === "preview" ? (
              job ? (
                <>
                  <div className={"render-label " + (stale ? "stale" : "")}>
                    {stale
                      ? "模板已修改，以下为旧预览 · 请更新"
                      : job.result.engine_version +
                        " · " +
                        job.result.pages +
                        " 页"}
                    <a
                      href={"/api/v2/artifacts/" + job.id + "/manifest.json"}
                      target="_blank"
                    >
                      产物记录
                    </a>
                  </div>
                  <PdfPreview
                    key={job.id}
                    job={job}
                    controlsTarget={pdfControls}
                    selected={selected}
                    onSelect={(id, keyboard) => {
                      if (locations.some(({ node }) => node.id === id))
                        selectForEdit(id, keyboard);
                    }}
                    dropTarget={
                      draggingComponent && !stale
                        ? (id, zone) => {
                            if (!locations.some(({ node }) => node.id === id))
                              return;
                            return {
                              className:
                                "component-drop-anchor" + dropClass(zone),
                              ...dropAttributes(zone, (event) => ({
                                kind: edgeAt(
                                  event.clientY,
                                  event.currentTarget.getBoundingClientRect(),
                                  false,
                                ),
                                nodeId: id,
                              })),
                            };
                          }
                        : undefined
                    }
                  />
                  <p className="preview-note">
                    {job.result.field_status}
                    <br />
                    唯一文本可点击选中；表格、图片和重复文本请通过左侧结构树选择。
                  </p>
                </>
              ) : (
                <div className="empty-preview">
                  <div className="empty-icon">
                    <FileText size={40} />
                  </div>
                  <h1>
                    {tpl
                      ? "生成报告预览"
                      : browsingSet
                        ? "在模板集中创建模板"
                        : "创建第一个模板集"}
                  </h1>
                  <p>
                    {tpl
                      ? "添加组件、修改属性，然后点击“更新预览”。"
                      : browsingSet
                        ? "在「" +
                          browsingSet.name +
                          "」中创建模板，使用 DS 示例文档开始。"
                        : "模板集用来管理报告模板、可复用组件和排版引擎。"}
                  </p>
                  {tpl && !engineOption?.available && (
                    <p className="engine-blocked">
                      {engineOption?.name ?? "所选引擎"}在当前环境不可用。
                      {availableEngine
                        ? "可切换此模板集的排版引擎。"
                        : "安装排版引擎后即可生成报告。"}
                    </p>
                  )}
                  {!tpl ? (
                    <button
                      className="primary"
                      onClick={browsingSet ? createTemplate : createSet}
                    >
                      <Plus />
                      {browsingSet ? "创建报告模板" : "新建模板集"}
                    </button>
                  ) : !engineOption?.available && availableEngine ? (
                    <button
                      className="primary"
                      disabled={!!pendingEngine}
                      onClick={() =>
                        run(() => changeEngine(availableEngine.id))
                      }
                    >
                      使用 {availableEngine.name} 排版
                    </button>
                  ) : (
                    <button
                      className="primary"
                      disabled={!canRender}
                      onClick={preview}
                    >
                      <Play />
                      生成真实预览
                    </button>
                  )}
                </div>
              )
            ) : (
              <div className="structure-view">
                <h2>组件结构</h2>
                <p>拖到组件上缘或下缘可在前后插入，拖到容器中间可放入容器。</p>
                {tpl && outline(tpl.document.nodes, 0, "structure")}
                {tpl && !tpl.document.nodes.length && (
                  <p>从下方组件库拖入第一个组件</p>
                )}
              </div>
            )}
          </div>
          <div className="library">
            <div className="section-head">
              <strong>组件库</strong>
              <span>默认采用 DS 样式</span>
            </div>
            {tpl && (
              <>
                <small className="component-drop-hint">
                  {draggingComponent
                    ? dropIndicator
                      ? insertionDescription(dropIndicator.point)
                      : mode === "preview" &&
                          job?.result.mapping.length &&
                          !stale
                        ? "拖到结构列表、当前预览标记或文档末尾"
                        : "拖到结构列表或文档末尾"
                    : "点击组件：" + insertionDescription(clickInsertion)}
                </small>
                <div
                  className={"component-drop-append" + dropClass("append")}
                  {...dropAttributes("append", () => ({ kind: "append" }))}
                >
                  拖到此处，添加到文档末尾
                </div>
              </>
            )}
            <div className="component-list">
              {[...boot.presets, ...custom].map((c) => (
                <button
                  key={c.id}
                  className="component"
                  draggable={!!tpl}
                  disabled={!tpl}
                  onDragStart={(event) => startComponentDrag(event, c)}
                  onDragEnd={endComponentDrag}
                  onClick={(event) =>
                    insert(c, clickInsertion, false, event.detail === 0)
                  }
                >
                  {icon(c.node.kind)}
                  <strong>{c.name}</strong>
                  <small>
                    {c.builtin ? "DS 内置" : "我的组件 · v" + c.version}
                  </small>
                </button>
              ))}
            </div>
          </div>
        </main>
        <aside className="inspector">
          <div className="section-head">
            <strong>{node ? "组件属性" : "模板属性"}</strong>
            {node && <button onClick={finishEditing}>完成</button>}
          </div>
          {tpl ? (
            node ? (
              <div
                className="properties"
                id="component-properties"
                ref={inspectorProperties}
                key={node.id}
                tabIndex={-1}
              >
                <div className="component-title">
                  {icon(node.kind)}
                  <h2>{names[node.kind]}</h2>
                  <span className="badge">DS</span>
                </div>
                <div className="tools">
                  <button title="上移" onClick={() => move(-1)}>
                    <ArrowUp />
                  </button>
                  <button title="下移" onClick={() => move(1)}>
                    <ArrowDown />
                  </button>
                  <button
                    title="复制"
                    onClick={() =>
                      insert(
                        {
                          id: node.component_id,
                          name: nodeName(node),
                          version: node.component_version,
                          node,
                        },
                        { kind: "after", nodeId: node.id },
                        true,
                      )
                    }
                  >
                    <Copy />
                  </button>
                  <button title="删除组件" onClick={remove}>
                    <Trash />
                  </button>
                </div>
                <label>
                  组件名称
                  <input
                    value={node.label}
                    maxLength={100}
                    placeholder={
                      node.kind === "heading" ? "留空时使用标题内容" : undefined
                    }
                    onChange={(e) => patch({ label: e.target.value })}
                  />
                </label>
                {["heading", "paragraph", "caption"].includes(node.kind) && (
                  <ComponentContent
                    value={node.text}
                    fields={fields}
                    onChange={(value) => patch({ text: value })}
                  />
                )}
                {node.kind === "heading" && (
                  <label>
                    标题级别
                    <select
                      value={node.level}
                      onChange={(e) => patch({ level: Number(e.target.value) })}
                    >
                      {[1, 2, 3, 4, 5, 6].map((n) => (
                        <option key={n} value={n}>
                          H{n} · {n} 级标题
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {node.kind === "table" && (
                  <>
                    <label>单元格内容</label>
                    <div className="grid-editor">
                      {node.rows.map((r: string[], i: number) => (
                        <div key={i}>
                          {r.map((c, j) => (
                            <textarea
                              key={j}
                              aria-label={
                                "第" + (i + 1) + "行第" + (j + 1) + "列"
                              }
                              value={c}
                              maxLength={30000}
                              onChange={(e) => {
                                const rows = structuredClone(node.rows);
                                rows[i][j] = e.target.value;
                                patch({ rows });
                              }}
                            />
                          ))}
                        </div>
                      ))}
                    </div>
                    <div className="tools">
                      <button
                        disabled={node.rows.length >= 200}
                        onClick={() =>
                          patch({
                            rows: [...node.rows, node.rows[0].map(() => "")],
                          })
                        }
                      >
                        ＋行
                      </button>
                      <button
                        disabled={node.rows[0].length >= 20}
                        onClick={() =>
                          patch({
                            rows: node.rows.map((r: any) => [...r, ""]),
                            columns: [],
                          })
                        }
                      >
                        ＋列
                      </button>
                      <button
                        disabled={node.rows.length < 2}
                        onClick={() => patch({ rows: node.rows.slice(0, -1) })}
                      >
                        －行
                      </button>
                      <button
                        disabled={node.rows[0].length < 2}
                        onClick={() =>
                          patch({
                            rows: node.rows.map((r: any) => r.slice(0, -1)),
                            columns: [],
                          })
                        }
                      >
                        －列
                      </button>
                    </div>
                    <fieldset className="component-column-widths">
                      <legend>各列宽度（厘米）</legend>
                      <div className="component-column-inputs">
                        {previewColumnWidths.map((width, index) => (
                          <NumberParameter
                            key={index}
                            label={"第" + (index + 1) + "列宽度"}
                            min={0}
                            max={25}
                            unit=" 厘米"
                            value={
                              node.columns.length
                                ? width
                                : Number(width.toFixed(2))
                            }
                            validate={(value) => {
                              if (value <= 0) return "列宽必须大于 0 厘米。";
                              const total = previewColumnWidths.reduce(
                                (sum, item, i) =>
                                  sum + (i === index ? value : item),
                                0,
                              );
                              if (total > usableWidth + 0.01) {
                                return (
                                  "各列宽度合计不能超过 " +
                                  Number(usableWidth.toFixed(2)) +
                                  " 厘米。"
                                );
                              }
                            }}
                            update={(value) =>
                              patch({
                                columns: previewColumnWidths.map((item, i) =>
                                  i === index ? value : item,
                                ),
                              })
                            }
                          />
                        ))}
                      </div>
                    </fieldset>
                    <label>
                      重复行数据路径
                      <input
                        value={node.rows_source}
                        placeholder="留空为固定表格"
                        onChange={(e) => patch({ rows_source: e.target.value })}
                      />
                    </label>
                    <NumberParameter
                      label="表头行数"
                      min={0}
                      max={10}
                      integer
                      value={node.header_rows}
                      update={(value) => patch({ header_rows: value })}
                    />
                  </>
                )}
                {node.kind === "caption" && (
                  <>
                    <label>
                      关联对象
                      <select
                        value={node.target}
                        onChange={(e) => patch({ target: e.target.value })}
                      >
                        <option value="">
                          请选择
                          {node.caption_type === "table" ? "表格" : "图片"}
                        </option>
                        {node.target &&
                          !targets.some(
                            (target) => target.id === node.target,
                          ) && (
                            <option value={node.target} disabled>
                              原关联不可用 · 请重新选择
                            </option>
                          )}
                        {targets.map((target) => (
                          <option key={target.id} value={target.id}>
                            {target.label || names[target.kind]} ·{" "}
                            {target.id.slice(0, 4)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      编号方式
                      <select
                        value={node.numbering}
                        onChange={(e) => patch({ numbering: e.target.value })}
                      >
                        <option value="chapter">按章节（1-1）</option>
                        <option value="document">全文连续（1）</option>
                      </select>
                    </label>
                  </>
                )}
                {["image", "repeat", "condition"].includes(node.kind) && (
                  <label>
                    数据绑定路径
                    <input
                      value={node.source}
                      onChange={(e) => patch({ source: e.target.value })}
                      placeholder={
                        node.kind === "image"
                          ? "可选：图片资源 ID 字段"
                          : "testCases"
                      }
                    />
                  </label>
                )}
                {node.kind === "condition" && (
                  <label>
                    等于
                    <input
                      value={node.equals}
                      onChange={(e) => patch({ equals: e.target.value })}
                    />
                  </label>
                )}
                {node.kind === "repeat" && (
                  <label>
                    空数据行为
                    <select
                      value={node.empty}
                      onChange={(e) => patch({ empty: e.target.value })}
                    >
                      <option value="hide">隐藏区块</option>
                      <option value="placeholder">显示“数据待补充”</option>
                    </select>
                  </label>
                )}
                {node.kind === "image" && (
                  <>
                    <label>
                      上传图片
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => {
                          const file = e.currentTarget.files?.[0];
                          e.currentTarget.value = "";
                          if (file)
                            void uploadImage(
                              file,
                              node.id,
                              tpl.id,
                              session.key,
                            );
                        }}
                      />
                    </label>
                    {node.asset && (
                      <img
                        className="asset-preview"
                        src={"/api/v2/assets/" + node.asset}
                      />
                    )}
                    <NumberParameter
                      label="宽度（厘米）"
                      min={1}
                      max={25}
                      unit=" 厘米"
                      value={node.width}
                      update={(value) => patch({ width: value })}
                    />
                  </>
                )}
                {([
                  "heading",
                  "paragraph",
                  "caption",
                  "table",
                  "image",
                ].includes(node.kind) ||
                  (node.kind === "repeat" && node.empty === "placeholder")) && (
                  <>
                    <h3>
                      {node.kind === "repeat"
                        ? "空数据占位文字样式"
                        : "样式覆盖"}
                      <small>留空继承 DS</small>
                    </h3>
                    {node.kind !== "image" && (
                      <div className="two-col">
                        {styleField("字号（pt）", "size")}
                        <label>
                          字体
                          <input
                            value={node.style.font ?? ""}
                            maxLength={80}
                            placeholder="继承 DS 样式"
                            onChange={(event) =>
                              patch({
                                style: {
                                  ...node.style,
                                  font: event.currentTarget.value || null,
                                },
                              })
                            }
                          />
                        </label>
                      </div>
                    )}
                    <label>
                      对齐
                      <select
                        value={node.style.align || ""}
                        onChange={(e) =>
                          patch({
                            style: {
                              ...node.style,
                              align: e.target.value || null,
                            },
                          })
                        }
                      >
                        <option value="">继承 DS 样式</option>
                        <option value="left">左对齐</option>
                        <option value="center">居中</option>
                        <option value="right">右对齐</option>
                        <option value="justify">两端对齐</option>
                      </select>
                    </label>
                    <div className="two-col">
                      {styleField("段前（pt）", "before")}
                      {styleField("段后（pt）", "after")}
                      {node.kind !== "image" && styleField("行距倍数", "line")}
                      {node.kind !== "image" && (
                        <ColorParameter
                          key={node.id + ":color:" + styleReset}
                          value={node.style.color}
                          update={(value) =>
                            patch({ style: { ...node.style, color: value } })
                          }
                        />
                      )}
                    </div>
                    {node.kind !== "image" && (
                      <label>
                        加粗
                        <select
                          value={
                            node.style.bold == null
                              ? ""
                              : String(node.style.bold)
                          }
                          onChange={(e) =>
                            patch({
                              style: {
                                ...node.style,
                                bold:
                                  e.target.value === ""
                                    ? null
                                    : e.target.value === "true",
                              },
                            })
                          }
                        >
                          <option value="">继承 DS</option>
                          <option value="true">加粗</option>
                          <option value="false">常规</option>
                        </select>
                      </label>
                    )}
                    <button
                      className="wide"
                      onClick={() => {
                        patch({ style: {} });
                        setStyleReset((current) => current + 1);
                      }}
                    >
                      恢复 DS 默认样式
                    </button>
                  </>
                )}
                <button
                  className="primary wide"
                  onClick={() =>
                    run(async () => {
                      const name = prompt("新组件名称", nodeName(node));
                      if (name) {
                        const owner = tpl.set_id;
                        const saved = await api<Component>("/components", {
                          set_id: owner,
                          name,
                          node,
                        });
                        C((previous) => ({
                          ...previous,
                          [owner]: [
                            ...(previous[owner] ?? []).filter(
                              (c) => c.id !== saved.id,
                            ),
                            saved,
                          ],
                        }));
                        M("已保存为新组件");
                      }
                    })
                  }
                >
                  <Plus />
                  保存为新组件
                </button>
              </div>
            ) : (
              <div className="properties">
                <label>
                  模板名称
                  <input
                    value={tpl.name}
                    onChange={(e) => edit((t) => (t.name = e.target.value))}
                  />
                </label>
                <label>
                  页眉
                  <textarea
                    value={tpl.document.header}
                    onChange={(e) =>
                      edit((t) => (t.document.header = e.target.value))
                    }
                  />
                </label>
                <label>
                  页脚
                  <textarea
                    value={tpl.document.footer}
                    onChange={(e) =>
                      edit((t) => (t.document.footer = e.target.value))
                    }
                  />
                  <small>{"{PAGE} 页码 · {NUMPAGES} 总页数"}</small>
                </label>
                <h3>页面设置（厘米）</h3>
                {[
                  ["width", "宽度"],
                  ["height", "高度"],
                  ["margin", "页边距"],
                ].map(([k, l]) => (
                  <label key={k}>
                    {l}
                    <input
                      type="number"
                      step="0.1"
                      value={tpl.document.page[k]}
                      onChange={(e) =>
                        edit((t) => (t.document.page[k] = +e.target.value))
                      }
                    />
                  </label>
                ))}
                <p className="hint">
                  选择左侧组件即可编辑内容和样式。插入组件时，默认使用内置 DS
                  母版。
                </p>
                <button className="wide" onClick={copyTemplate}>
                  <Copy />
                  复制模板
                </button>
                <button className="wide danger" onClick={archiveTemplate}>
                  归档模板
                </button>
              </div>
            )
          ) : (
            <p className="hint">新建或选择模板后开始编辑。</p>
          )}
        </aside>
      </div>
      {dialog && (
        <StudioDialog
          key={dialog.kind}
          title={
            {
              data: "测试数据",
              ai: "AI 转化模板",
              review: "转换审核",
              versions: "历史版本",
              "create-set": "新建模板集",
              "create-template": "新建报告模板",
            }[dialog.kind]
          }
          onClose={() => showDialog(null)}
        >
          {(dialog.kind === "create-set" ||
            dialog.kind === "create-template") && (
            <TemplateSetup
              kind={dialog.kind}
              setName={
                dialog.kind === "create-template"
                  ? boot.sets.find((set) => set.id === dialog.setId)?.name
                  : undefined
              }
              engines={boot.engines}
              onCreate={(name, engine) =>
                submitSetup(dialog.kind, name, engine)
              }
            />
          )}
          {dialog.kind === "data" && session?.key === dialog.sessionKey && (
            <TestDataEditor
              data={tpl.data}
              onApply={(data) => {
                edit((draft) => {
                  draft.data = data;
                }, dialog.sessionKey);
                showDialog(null);
              }}
            />
          )}
          {dialog.kind === "ai" && conversionTarget && (
            <ConversionUpload
              key={conversionTarget.id}
              target={conversionTarget}
              model={boot.ai}
              task={conversionTask}
              onStart={(file, target, jobId) =>
                void convert(file, target, jobId)
              }
              onOpenReview={openReview}
            />
          )}
          {dialog.kind === "review" &&
            dialog.templateId === tpl?.id &&
            currentReview && (
              <ReviewWorkspace
                key={tpl.id}
                review={currentReview}
                nodes={locations.map(({ node }) => node)}
                onLocate={(id) => {
                  showDialog(null);
                  selectComponent(id);
                }}
                onMark={(index, reviewed) =>
                  markReview(tpl.id, index, reviewed)
                }
              />
            )}
          {dialog.kind === "versions" &&
            dialog.versions.map((version) => (
              <div className="version" key={version.version}>
                <span>
                  v{version.version} · {version.name} ·{" "}
                  {new Date(version.updated).toLocaleString()}
                </span>
                <button
                  onClick={() =>
                    run(() => restoreVersion(version.version, dialog))
                  }
                >
                  恢复到编辑区
                </button>
              </div>
            ))}
        </StudioDialog>
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
