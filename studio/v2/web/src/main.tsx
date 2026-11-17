import React, { useEffect, useRef, useState } from "react";
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
import * as pdfjs from "pdfjs-dist";
import worker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "./style.css";
pdfjs.GlobalWorkerOptions.workerSrc = worker;
const api = async (path: string, body?: any, method?: string) => {
  const r = await fetch("/api/v2" + path, {
    method: method || (body ? "POST" : "GET"),
    headers:
      body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body: body
      ? body instanceof FormData
        ? body
        : JSON.stringify(body)
      : undefined,
  });
  const v = await r.json();
  if (!r.ok)
    throw Error(
      typeof v.detail === "string" ? v.detail : JSON.stringify(v.detail),
    );
  return v;
};
const flat = (nodes: any[]): any[] =>
  nodes.flatMap((n) => [n, ...flat(n.children || [])]);
const clone = (node: any) => {
  const n = structuredClone(node),
    ids: any = {};
  flat([n]).forEach((x) => {
    ids[x.id] = crypto.randomUUID();
    x.id = ids[x.id];
  });
  flat([n]).forEach((x) => {
    x.target = ids[x.target] || "";
  });
  return n;
};
const paths = (data: any, prefix = ""): string[] =>
  Object.entries(data || {}).flatMap(([k, v]) => {
    const p = prefix ? prefix + "." + k : k;
    return Array.isArray(v)
      ? []
      : v && typeof v === "object"
        ? paths(v, p)
        : [p];
  });
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
function PDF({ job, onSelect, selected }: any) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let stopped = false;
    let loading: any;
    const tasks: any[] = [];
    const run = async () => {
      loading = pdfjs.getDocument(
        "/api/v2/artifacts/" + job.id + "/report.pdf",
      );
      const doc = await loading.promise;
      if (stopped) return;
      ref.current!.innerHTML = "";
      for (let i = 1; i <= doc.numPages; i++) {
        if (stopped) break;
        const page = await doc.getPage(i);
        const viewport = page.getViewport({ scale: 1 });
        const wrap = document.createElement("div");
        wrap.className = "pdf-page";
        wrap.style.aspectRatio = viewport.width + "/" + viewport.height;
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width * 1.5;
        canvas.height = viewport.height * 1.5;
        wrap.append(canvas);
        ref.current!.append(wrap);
        const task = page.render({
          canvas,
          viewport: page.getViewport({ scale: 1.5 }),
        });
        tasks.push(task);
        await task.promise;
        for (const m of job.result.mapping.filter((m: any) => m.page === i - 1))
          for (const r of m.rects) {
            const b = document.createElement("button");
            b.className = "pdf-hit" + (m.node_id === selected ? " chosen" : "");
            b.title = "编辑 " + m.text;
            b.setAttribute("aria-label", b.title);
            Object.assign(b.style, {
              left: (r[0] / viewport.width) * 100 + "%",
              top: (r[1] / viewport.height) * 100 + "%",
              width: ((r[2] - r[0]) / viewport.width) * 100 + "%",
              height: ((r[3] - r[1]) / viewport.height) * 100 + "%",
            });
            b.onclick = () => onSelect(m.node_id);
            wrap.append(b);
          }
      }
    };
    run().catch((e) => {
      if (!stopped && ref.current)
        ref.current.textContent = "PDF 加载失败：" + e.message;
    });
    return () => {
      stopped = true;
      tasks.forEach((t) => t.cancel());
      loading?.destroy();
    };
  }, [job.id, selected]);
  return <div ref={ref} className="pdf-pages" />;
}
function App() {
  const [boot, B] = useState<any>(),
    [setId, S] = useState(""),
    [tpl, T] = useState<any>(),
    [saved, SV] = useState(""),
    [selected, SEL] = useState(""),
    [custom, C] = useState<any[]>([]),
    [error, E] = useState(""),
    [message, M] = useState(""),
    [job, J] = useState<any>(),
    [snapshot, SN] = useState(""),
    [busy, BUSY] = useState(false),
    [mode, MODE] = useState("preview"),
    [modal, MOD] = useState(""),
    [json, JSONTEXT] = useState(""),
    [reviews, REV] = useState<any>(),
    [undo, U] = useState<any[]>([]);
  const latest = useRef(tpl);
  latest.current = tpl;
  const serial = tpl ? JSON.stringify([tpl.document, tpl.data, tpl.name]) : "";
  const dirty = !!tpl && serial !== saved;
  const stale = job && snapshot !== serial;
  const node = tpl
    ? flat(tpl.document.nodes).find((n) => n.id === selected)
    : null;
  const currentSet = boot?.sets.find((s: any) => s.id === setId);
  const [engine, ENGINE] = useState("word");
  const run = async (fn: () => Promise<any>) => {
    E("");
    try {
      return await fn();
    } catch (e: any) {
      E(e.message);
    }
  };
  const refresh = async () => {
    const b = await api("/bootstrap");
    B(b);
    return b;
  };
  useEffect(() => {
    run(async () => {
      const b = await refresh();
      if (b.sets[0]) {
        S(b.sets[0].id);
        ENGINE(b.sets[0].engine);
      }
    });
  }, []);
  useEffect(() => {
    if (setId) run(async () => C(await api("/components?set_id=" + setId)));
  }, [setId]);
  useEffect(() => {
    if (tpl && dirty)
      localStorage.setItem("ds-draft-" + tpl.id, JSON.stringify(tpl));
  }, [serial]);
  useEffect(() => {
    const f = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", f);
    return () => window.removeEventListener("beforeunload", f);
  }, [dirty]);
  const edit = (fn: (t: any) => void) => {
    U((h) => [...h.slice(-39), structuredClone(tpl)]);
    const t = structuredClone(tpl);
    fn(t);
    T(t);
  };
  const patch = (v: any) =>
    edit((t) =>
      Object.assign(
        flat(t.document.nodes).find((n) => n.id === selected),
        v,
      ),
    );
  const save = async () => {
    const t = latest.current;
    if (!t) return;
    const r = await api(
      "/templates/" + t.id,
      {
        name: t.name,
        set_id: t.set_id,
        version: t.version,
        document: t.document,
        data: t.data,
      },
      "PUT",
    );
    if (latest.current === t) {
      T(r);
      SV(JSON.stringify([r.document, r.data, r.name]));
    } else T((now: any) => ({ ...now, version: r.version }));
    localStorage.removeItem("ds-draft-" + t.id);
    await refresh();
    M("已保存 v" + r.version);
    return r;
  };
  const open = async (id: string) => {
    if (dirty) await save();
    const t = await api("/templates/" + id);
    const draft = localStorage.getItem("ds-draft-" + id);
    SV(JSON.stringify([t.document, t.data, t.name]));
    T(draft ? JSON.parse(draft) : t);
    S(t.set_id);
    ENGINE(boot.sets.find((s: any) => s.id === t.set_id).engine);
    SEL("");
    J(null);
    U([]);
    if (draft) M("已恢复本机未保存草稿，请核对后保存");
  };
  const createSet = () =>
    run(async () => {
      const name = prompt("新模板集名称");
      if (!name?.trim()) return;
      const s = await api("/sets", { name, engine: "word" });
      await refresh();
      S(s.id);
      ENGINE(s.engine);
    });
  const createTemplate = () =>
    run(async () => {
      if (!setId) throw Error("请先新建或选择模板集");
      const name = prompt("新模板名称", "功能测试报告");
      if (!name?.trim()) return;
      if (dirty) await save();
      const d = await api("/default");
      const t = await api("/templates", { name, set_id: setId, ...d });
      await refresh();
      T(t);
      SV(JSON.stringify([t.document, t.data, t.name]));
      SEL("");
      J(null);
      U([]);
    });
  const insert = (component: any, target = selected) => {
    const n = clone(component.node);
    n.component_id = component.id;
    n.component_version = component.version;
    edit((t) => {
      const parent = flat(t.document.nodes).find((x) => x.id === target);
      if (
        parent &&
        ["repeat", "condition", "section", "group"].includes(parent.kind)
      )
        parent.children.push(n);
      else {
        const list =
          [
            t.document.nodes,
            ...flat(t.document.nodes).map((x) => x.children),
          ].find((xs) => xs.some((x: any) => x.id === target)) ||
          t.document.nodes;
        const idx = list.findIndex((x: any) => x.id === target);
        list.splice(idx < 0 ? list.length : idx + 1, 0, n);
      }
    });
    SEL(n.id);
    M("已添加 " + component.name + "，编辑后更新预览");
  };
  const move = (delta: number) =>
    edit((t) => {
      const list = [
        t.document.nodes,
        ...flat(t.document.nodes).map((x) => x.children),
      ].find((xs) => xs.some((n: any) => n.id === selected));
      const i = list.findIndex((n: any) => n.id === selected);
      if (i + delta >= 0 && i + delta < list.length) {
        const [n] = list.splice(i, 1);
        list.splice(i + delta, 0, n);
      }
    });
  const remove = () => {
    edit((t) => {
      const list = [
        t.document.nodes,
        ...flat(t.document.nodes).map((x) => x.children),
      ].find((xs) => xs.some((n: any) => n.id === selected));
      list.splice(
        list.findIndex((n: any) => n.id === selected),
        1,
      );
    });
    SEL("");
  };
  const poll = async (id: string) => {
    for (;;) {
      const j = await api("/jobs/" + id);
      if (j.status === "ready") return j;
      if (["failed", "cancelled"].includes(j.status))
        throw Error(j.error || "任务已取消");
      M(
        (
          {
            queued: "排队中",
            compiling: "正在生成 DOCX",
            rendering: "正在 Office 中排版",
            analyzing: "AI 正在分析报告",
          } as any
        )[j.status] || j.status,
      );
      await new Promise((r) => setTimeout(r, 1000));
    }
  };
  const preview = () =>
    run(async () => {
      BUSY(true);
      try {
        await save();
        const t = latest.current;
        const snap = JSON.stringify([t.document, t.data, t.name]);
        const j = await api("/renders", {
          document: t.document,
          data: t.data,
          engine,
        });
        const result = await poll(j.id);
        J(result);
        SN(snap);
        MODE("preview");
        M("真实预览已生成 · " + result.result.pages + " 页");
      } finally {
        BUSY(false);
      }
    });
  const convert = async (file: File) => {
    BUSY(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const j = await api(
        "/conversions?set_id=" +
          setId +
          "&name=" +
          encodeURIComponent(file.name.replace(/\.docx$/i, "") + " · AI 模板"),
        form,
      );
      const result = await poll(j.id);
      await refresh();
      await open(result.result.template_id);
      REV(result.result);
      MOD("review");
      M("转换完成，请逐项审核");
    } finally {
      BUSY(false);
    }
  };
  const outline = (nodes: any[], depth = 0): any =>
    nodes.map((n) => (
      <React.Fragment key={n.id}>
        <button
          className={"tree-node " + (selected === n.id ? "active" : "")}
          style={{ paddingLeft: 12 + depth * 15 }}
          onClick={() => SEL(n.id)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            const c = [...boot.presets, ...custom].find(
              (c) => c.id === e.dataTransfer.getData("component"),
            );
            if (c) insert(c, n.id);
          }}
        >
          {icon(n.kind)}
          <span>{n.label || n.text || names[n.kind]}</span>
          <small>{n.kind === "heading" ? "H" + n.level : ""}</small>
        </button>
        {outline(n.children, depth + 1)}
      </React.Fragment>
    ));
  const styleField = (label: string, key: string, type = "number") => (
    <label>
      {label}
      <input
        type={type}
        placeholder="继承 DS 样式"
        value={node.style[key] ?? ""}
        onChange={(e) =>
          patch({
            style: {
              ...node.style,
              [key]:
                e.target.value === ""
                  ? null
                  : type === "number"
                    ? Number(e.target.value)
                    : e.target.value,
            },
          })
        }
      />
    </label>
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
          <span className="save-state">{dirty ? "● 未保存" : "✓ 已保存"}</span>
          <button disabled={!tpl} onClick={() => run(save)}>
            <FloppyDisk />
            保存
          </button>
          <button className="primary" disabled={!tpl || busy} onClick={preview}>
            <Play />
            {busy ? "处理中…" : "更新预览"}
          </button>
        </div>
      </header>
      <div className="workspace">
        <aside className="navigation">
          <div className="section-head">
            <span>模板管理</span>
            <button aria-label="新建模板集" onClick={createSet}>
              <Plus />
            </button>
          </div>
          <div className="sets">
            {boot.sets.map((s: any) => (
              <div key={s.id}>
                <button
                  className={"set " + (s.id === setId ? "selected" : "")}
                  onClick={() => {
                    S(s.id);
                    ENGINE(s.engine);
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
          <button className="new-template" onClick={createTemplate}>
            <Plus />
            新建模板
          </button>
          <button
            className="ai-button"
            disabled={!setId || busy}
            onClick={() => MOD("ai")}
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
            </div>
            <div>
              <button
                title="撤销"
                disabled={!undo.length}
                onClick={() => {
                  T(undo.at(-1));
                  U(undo.slice(0, -1));
                }}
              >
                <ArrowCounterClockwise />
              </button>
              <button
                disabled={!tpl}
                onClick={() => {
                  JSONTEXT(JSON.stringify(tpl.data, null, 2));
                  MOD("data");
                }}
              >
                测试数据
              </button>
              <button
                disabled={!tpl}
                onClick={() =>
                  run(async () => {
                    REV(await api("/templates/" + tpl.id + "/versions"));
                    MOD("versions");
                  })
                }
              >
                <Clock />
              </button>
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
              onChange={(e) => {
                const value = e.target.value;
                ENGINE(value);
                J(null);
                run(async () => {
                  await api(
                    "/sets/" + setId,
                    { name: currentSet.name, engine: value },
                    "PUT",
                  );
                  await refresh();
                });
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
              disabled={!job || stale}
              onClick={() =>
                window.open("/api/v2/artifacts/" + job.id + "/report.docx")
              }
            >
              <DownloadSimple />
              DOCX
            </button>
          </div>
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
          <div
            className="canvas"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              const c = [...boot.presets, ...custom].find(
                (c) => c.id === e.dataTransfer.getData("component"),
              );
              if (c && tpl) insert(c);
            }}
          >
            {mode === "preview" ? (
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
                  <PDF job={job} selected={selected} onSelect={SEL} />
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
                  <h1>{tpl ? "让编辑与产出对应起来" : "从一套模板开始"}</h1>
                  <p>
                    {tpl
                      ? "添加组件、修改属性，然后点击“更新预览”。"
                      : "新建模板集和模板，拖入组件即可开始。"}
                    <br />
                    这里展示排版引擎生成的真实 PDF。
                  </p>
                  <span>
                    {boot.engines.find((e: any) => e.id === engine)?.reason}
                  </span>
                  {tpl && (
                    <button
                      className="primary"
                      disabled={busy}
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
                <p>拖入组件：选中容器时放入容器，选中普通组件时插入其后。</p>
                {tpl && outline(tpl.document.nodes)}
                {tpl && !tpl.document.nodes.length && (
                  <p>从下方组件库拖入第一个组件</p>
                )}
              </div>
            )}
          </div>
          <div className="library">
            <div className="section-head">
              <strong>组件库</strong>
              <span>拖入文档或点击添加 · 默认采用 DS 样式</span>
            </div>
            <div className="component-list">
              {[...boot.presets, ...custom].map((c) => (
                <button
                  key={c.id}
                  className="component"
                  draggable={!!tpl}
                  disabled={!tpl}
                  onDragStart={(e) => e.dataTransfer.setData("component", c.id)}
                  onClick={() => insert(c)}
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
            {node && <button onClick={() => SEL("")}>完成</button>}
          </div>
          {tpl ? (
            node ? (
              <div className="properties">
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
                      insert({
                        id: node.component_id,
                        name: node.label || names[node.kind],
                        version: 1,
                        node,
                      })
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
                    onChange={(e) => patch({ label: e.target.value })}
                  />
                </label>
                {["heading", "paragraph", "caption"].includes(node.kind) && (
                  <label>
                    内容
                    <textarea
                      aria-label="内容"
                      rows={4}
                      value={node.text}
                      onChange={(e) => patch({ text: e.target.value })}
                    />
                    <small>
                      数据占位写法：{"{{project.name}}"}；重复区块内使用 item。
                    </small>
                    <select
                      aria-label="插入数据字段"
                      value=""
                      onChange={(e) => {
                        if (e.target.value)
                          patch({
                            text: node.text + "{{" + e.target.value + "}}",
                          });
                      }}
                    >
                      <option value="">＋ 插入数据字段</option>
                      {[
                        ...new Set([
                          ...paths(tpl.data),
                          ...Object.values(tpl.data)
                            .filter(Array.isArray)
                            .flatMap((v: any) => paths(v[0], "item")),
                        ]),
                      ].map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </label>
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
                        onClick={() =>
                          patch({
                            rows: [...node.rows, node.rows[0].map(() => "")],
                          })
                        }
                      >
                        ＋行
                      </button>
                      <button
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
                    <label>
                      各列宽度（厘米）
                      <div className="tools">
                        {node.rows[0].map((_: any, i: number) => (
                          <input
                            key={i}
                            aria-label={"第" + (i + 1) + "列宽度"}
                            type="number"
                            step="0.1"
                            value={
                              node.columns[i] ??
                              (
                                (tpl.document.page.width -
                                  2 * tpl.document.page.margin) /
                                node.rows[0].length
                              ).toFixed(1)
                            }
                            onChange={(e) => {
                              const columns = node.columns.length
                                ? [...node.columns]
                                : node.rows[0].map(
                                    () =>
                                      (tpl.document.page.width -
                                        2 * tpl.document.page.margin) /
                                      node.rows[0].length,
                                  );
                              columns[i] = +e.target.value;
                              patch({ columns });
                            }}
                          />
                        ))}
                      </div>
                    </label>
                    <label>
                      重复行数据路径
                      <input
                        value={node.rows_source}
                        placeholder="留空为固定表格"
                        onChange={(e) => patch({ rows_source: e.target.value })}
                      />
                    </label>
                    <label>
                      表头行数
                      <input
                        type="number"
                        min="0"
                        max="10"
                        value={node.header_rows}
                        onChange={(e) =>
                          patch({ header_rows: +e.target.value })
                        }
                      />
                    </label>
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
                        {flat(tpl.document.nodes)
                          .filter(
                            (n) =>
                              n.kind ===
                              (node.caption_type === "table"
                                ? "table"
                                : "image"),
                          )
                          .map((n) => (
                            <option key={n.id} value={n.id}>
                              {n.label || names[n.kind]} · {n.id.slice(0, 4)}
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
                        onChange={(e) =>
                          run(async () => {
                            const f = e.target.files?.[0];
                            if (!f) return;
                            const form = new FormData();
                            form.append("file", f);
                            const a = await api("/assets", form);
                            patch({ asset: a.id });
                          })
                        }
                      />
                    </label>
                    {node.asset && (
                      <img
                        className="asset-preview"
                        src={"/api/v2/assets/" + node.asset}
                      />
                    )}
                    <label>
                      宽度（厘米）
                      <input
                        type="number"
                        value={node.width}
                        onChange={(e) => patch({ width: +e.target.value })}
                      />
                    </label>
                  </>
                )}
                <h3>
                  样式覆盖 <small>留空继承 DS</small>
                </h3>
                <div className="two-col">
                  {styleField("字号（pt）", "size")}
                  {styleField("字体", "font", "text")}
                </div>
                <label>
                  对齐
                  <select
                    value={node.style.align || ""}
                    onChange={(e) =>
                      patch({
                        style: { ...node.style, align: e.target.value || null },
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
                  {styleField("行距倍数", "line")}
                  {styleField("颜色（HEX）", "color", "text")}
                </div>
                <label>
                  加粗
                  <select
                    value={
                      node.style.bold == null ? "" : String(node.style.bold)
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
                <button className="wide" onClick={() => patch({ style: {} })}>
                  恢复 DS 默认样式
                </button>
                <button
                  className="primary wide"
                  onClick={() =>
                    run(async () => {
                      const name = prompt(
                        "新组件名称",
                        node.label || names[node.kind],
                      );
                      if (name) {
                        await api("/components", {
                          set_id: tpl.set_id,
                          name,
                          node,
                        });
                        C(await api("/components?set_id=" + setId));
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
                <button
                  className="wide"
                  onClick={() =>
                    run(async () => {
                      const t = await api("/templates", {
                        name: tpl.name + " · 副本",
                        set_id: tpl.set_id,
                        document: tpl.document,
                        data: tpl.data,
                      });
                      await refresh();
                      await open(t.id);
                    })
                  }
                >
                  <Copy />
                  复制模板
                </button>
                <button
                  className="wide danger"
                  onClick={() =>
                    run(async () => {
                      if (confirm("归档此模板？历史版本会保留。")) {
                        await api("/templates/" + tpl.id, undefined, "DELETE");
                        T(null);
                        await refresh();
                      }
                    })
                  }
                >
                  归档模板
                </button>
              </div>
            )
          ) : (
            <p className="hint">新建或选择模板后开始编辑。</p>
          )}
        </aside>
      </div>
      {modal && (
        <div className="modal-backdrop">
          <section className="modal">
            <div className="section-head">
              <h2>
                {
                  {
                    data: "测试数据",
                    ai: "AI 转化模板",
                    review: "转换审核",
                    versions: "历史版本",
                  }[modal]
                }
              </h2>
              <button onClick={() => MOD("")}>关闭</button>
            </div>
            {modal === "data" && (
              <>
                <p>用于预览和导出的示例数据，与模板一同保存。</p>
                <textarea
                  className="json"
                  value={json}
                  onChange={(e) => JSONTEXT(e.target.value)}
                />
                <button
                  className="primary"
                  onClick={() =>
                    run(async () => {
                      const d = JSON.parse(json);
                      if (!d || Array.isArray(d) || typeof d !== "object")
                        throw Error("测试数据必须为对象");
                      edit((t) => (t.data = d));
                      MOD("");
                    })
                  }
                >
                  应用数据
                </button>
              </>
            )}
            {modal === "ai" && (
              <>
                <p>
                  选择已有 DOCX 测试报告。AI
                  分析正文和表格，生成固定内容、字段及重复区块；样式统一采用 DS
                  母版。
                </p>
                <div className="notice">
                  {boot.ai.configured
                    ? "将把提取的报告文字和表格发送到 " +
                      boot.ai.destination +
                      "，模型：" +
                      boot.ai.model
                    : "尚未配置模型服务。请在启动服务前设置 STUDIO_AI_BASE_URL、STUDIO_AI_MODEL 和 STUDIO_AI_API_KEY。"}
                </div>
                <p>
                  当前不会迁移源文档图片、浮动对象和源样式。转换后必须审核，未归类的文字会保留。
                </p>
                <input
                  disabled={!boot.ai.configured || busy}
                  type="file"
                  accept=".docx"
                  onChange={(e) =>
                    run(async () => {
                      if (dirty) await save();
                      const f = e.target.files?.[0];
                      if (f) await convert(f);
                    })
                  }
                />
              </>
            )}
            {modal === "review" && (
              <>
                <p>
                  模板已创建。点击候选项定位组件，关闭此窗口后可在属性栏修改。
                </p>
                {reviews?.review?.map((r: any, i: number) => (
                  <button
                    className="review-row"
                    key={i}
                    onClick={() => {
                      SEL(r.node_ids?.[0] || "");
                      MOD("");
                    }}
                  >
                    <strong>{r.decision || "待审核"}</strong>
                    <span>{r.reason}</span>
                  </button>
                ))}
                <details>
                  <summary>提取的源内容</summary>
                  <pre>{JSON.stringify(reviews?.source_blocks, null, 2)}</pre>
                </details>
              </>
            )}
            {modal === "versions" &&
              reviews?.map((r: any) => (
                <div className="version" key={r.version}>
                  <span>
                    v{r.version} · {r.name} ·{" "}
                    {new Date(r.updated).toLocaleString()}
                  </span>
                  <button
                    onClick={() =>
                      run(async () => {
                        const old = await api(
                          "/templates/" + tpl.id + "/versions/" + r.version,
                        );
                        edit((t) => {
                          t.document = old.document;
                          t.data = old.data;
                          t.name = old.name;
                        });
                        MOD("");
                        M("已恢复到编辑区，保存后形成新版本");
                      })
                    }
                  >
                    恢复到编辑区
                  </button>
                </div>
              ))}
          </section>
        </div>
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
