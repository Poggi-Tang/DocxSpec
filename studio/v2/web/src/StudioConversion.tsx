import { useRef, useState } from "react";
import type { ReportNode, TemplateSummary } from "./document";
import "./studio-conversion.css";

type SourceBlock =
  | { source_id: string; kind: "table"; rows: string[][] }
  | { source_id: string; kind: "paragraph" | "unsupported"; text: string };

export interface ConversionReview {
  template_id: string;
  review: {
    source_ids: string[];
    node_ids: string[];
    decision: string;
    reason: string;
    needs_confirmation?: boolean;
  }[];
  source_blocks: SourceBlock[];
  reviewed_indices: number[];
}

type TargetSet = { id: string; name: string };
type Model = { configured: boolean; destination: string; model: string };

export type ConversionTask =
  | { phase: "running"; fileName: string; target: TargetSet; progress: string }
  | {
      phase: "failed";
      file: File;
      target: TargetSet;
      error: string;
      resumeJobId?: string;
    }
  | {
      phase: "complete";
      fileName: string;
      target: TargetSet;
      template: TemplateSummary;
    };

export function ConversionUpload({
  target,
  model,
  task,
  onStart,
  onOpenReview,
}: {
  target: TargetSet;
  model: Model;
  task: ConversionTask | undefined;
  onStart: (file: File, target: TargetSet, resumeJobId?: string) => void;
  onOpenReview: (id: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<File>();
  const running = task?.phase === "running" ? task : undefined;
  const failed =
    task?.phase === "failed" && task.target.id === target.id && !picked
      ? task
      : undefined;
  const complete =
    task?.phase === "complete" && task.target.id === target.id && !picked
      ? task
      : undefined;
  const file = picked ?? failed?.file;
  const invalid =
    file &&
    (!/\.docx$/i.test(file.name)
      ? "请选择 .docx 格式的报告。"
      : file.size > 10 * 1024 * 1024
        ? "报告超过 10 MB，请缩小文件后重新选择。"
        : file.size === 0
          ? "这个文件没有内容，请重新选择。"
          : "");

  return (
    <div className="conversion-upload">
      <p>将已有报告转换成可编辑的模板。图片和浮动对象需手动补充。</p>
      <dl className="conversion-meta">
        <dt>保存到</dt>
        <dd>{target.name}</dd>
        <dt>模型服务</dt>
        <dd>{model.configured ? model.model : "未配置"}</dd>
        {model.configured && (
          <>
            <dt>发送到</dt>
            <dd>{model.destination}</dd>
          </>
        )}
      </dl>
      {!model.configured ? (
        <details className="conversion-setup">
          <summary>查看配置方法</summary>
          <p>
            在启动 Studio 的终端设置 <code>STUDIO_AI_BASE_URL</code> 和{" "}
            <code>STUDIO_AI_MODEL</code>。模型服务要求身份验证时，再设置{" "}
            <code>STUDIO_AI_API_KEY</code>。重新启动 Studio 并刷新此页面。
          </p>
        </details>
      ) : (
        <>
          <p>开始转换后，只发送从报告提取的文字和表格。</p>
          <input
            ref={input}
            type="file"
            aria-label="选择 DOCX 报告"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            hidden
            disabled={!!running}
            onChange={(event) => {
              const selected = event.currentTarget.files?.[0];
              event.currentTarget.value = "";
              if (selected) setPicked(selected);
            }}
          />
          {running ? (
            <div className="conversion-feedback" role="status">
              <strong>{running.progress}</strong>
              <span>
                {running.fileName} · 保存到 {running.target.name}
              </span>
              <span>关闭此窗口后，转换会继续在后台运行。</span>
            </div>
          ) : (
            <>
              <div className="conversion-file">
                <button
                  type="button"
                  data-dialog-autofocus=""
                  onClick={() => input.current?.click()}
                >
                  {file ? "更换报告" : "选择 DOCX 报告"}
                </button>
                <span>{file?.name ?? "尚未选择文件 · 最大 10 MB"}</span>
              </div>
              {(invalid || failed?.error) && (
                <div
                  className="conversion-feedback conversion-error"
                  role="alert"
                >
                  <strong>{failed ? "转换遇到问题" : "请选择其他文件"}</strong>
                  <span>{invalid || failed?.error}</span>
                </div>
              )}
              {complete && (
                <div className="conversion-feedback" role="status">
                  <strong>转换完成</strong>
                  <span>
                    {complete.fileName} 已保存到 {complete.target.name}
                  </span>
                </div>
              )}
              <div className="conversion-actions">
                {complete && (
                  <button
                    type="button"
                    className="primary"
                    onClick={() => onOpenReview(complete.template.id)}
                  >
                    打开审核
                  </button>
                )}
                <button
                  type="button"
                  className={complete ? undefined : "primary"}
                  disabled={!file || !!invalid}
                  onClick={() => {
                    if (!file || invalid) return;
                    setPicked(undefined);
                    onStart(file, target, failed?.resumeJobId);
                  }}
                >
                  {failed?.resumeJobId
                    ? "继续查询转换结果"
                    : failed
                      ? "重试转换"
                      : "开始转换"}
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

export function ConversionNotice({
  task,
  onOpenReview,
  onOpenConversion,
  onDismiss,
}: {
  task: ConversionTask;
  onOpenReview: (id: string) => void;
  onOpenConversion: (id: string) => void;
  onDismiss: () => void;
}) {
  const fileName = task.phase === "failed" ? task.file.name : task.fileName;
  return (
    <div
      className={`conversion-task-notice ${task.phase === "failed" ? "conversion-error" : ""}`}
    >
      <div aria-live="polite">
        <strong>
          {task.phase === "running"
            ? task.progress
            : task.phase === "complete"
              ? "AI 转换完成"
              : "AI 转换遇到问题"}
        </strong>
        <span>
          {fileName} · {task.target.name}
        </span>
        {task.phase === "failed" && <span>{task.error}</span>}
      </div>
      <div className="conversion-actions">
        {task.phase === "complete" ? (
          <>
            <button
              type="button"
              onClick={() => onOpenReview(task.template.id)}
            >
              打开审核 · {task.template.name}
            </button>
            <button type="button" onClick={onDismiss}>
              关闭提示
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => onOpenConversion(task.target.id)}
          >
            {task.phase === "failed" ? "查看失败详情" : "查看任务"}
          </button>
        )}
      </div>
    </div>
  );
}

function TableExcerpt({ rows, label }: { rows: string[][]; label: string }) {
  return (
    <div className="review-table">
      <table aria-label={label}>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, column) => (
                <td key={column}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SourceExcerpt({ block }: { block: SourceBlock }) {
  return block.kind === "table" ? (
    <TableExcerpt rows={block.rows} label="提取的源表格" />
  ) : (
    <p className="review-excerpt">{block.text}</p>
  );
}

const componentType: Record<string, string> = {
  heading: "标题",
  paragraph: "正文",
  table: "表格",
  caption: "题注",
  image: "图片",
  repeat: "重复区块",
  condition: "条件区块",
  group: "组合",
  pagebreak: "分页",
  section: "分节",
  toc: "目录",
};

function ComponentExcerpt({ node }: { node: ReportNode }) {
  return (
    <div className="review-component">
      <strong>
        {componentType[node.kind] ?? node.kind}
        {node.label ? ` · ${node.label}` : ""}
      </strong>
      {node.kind === "table" && (
        <TableExcerpt rows={node.rows} label="生成表格内容" />
      )}
      {node.text && <p className="review-excerpt">{node.text}</p>}
      {node.source && (
        <p>
          数据字段 <code>{node.source}</code>
          {node.kind === "condition" ? ` 等于 ${node.equals}` : ""}
        </p>
      )}
      {!!node.children.length &&
        node.children.map((child) => (
          <ComponentExcerpt key={child.id} node={child} />
        ))}
    </div>
  );
}

function firstReviewItem(review: ConversionReview) {
  const unreviewed = review.review.findIndex(
    (entry, index) =>
      entry.needs_confirmation && !review.reviewed_indices.includes(index),
  );
  if (unreviewed !== -1) return unreviewed;
  return Math.max(
    0,
    review.review.findIndex(
      (_, index) => !review.reviewed_indices.includes(index),
    ),
  );
}

export function ReviewWorkspace({
  review,
  nodes,
  onLocate,
  onMark,
}: {
  review: ConversionReview;
  nodes: ReportNode[];
  onLocate: (id: string) => void;
  onMark: (index: number, reviewed: boolean) => Promise<void>;
}) {
  const [index, setIndex] = useState(() => firstReviewItem(review));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const entry = review.review[index];
  if (!entry) return <p>这个模板没有审核项。</p>;
  const source = new Map(
    review.source_blocks.map((block) => [block.source_id, block]),
  );
  const generated = new Map(nodes.map((node) => [node.id, node]));
  const isReviewed = review.reviewed_indices.includes(index);
  const count = review.review.length;
  const sourceItems = entry.source_ids.flatMap((id) =>
    source.has(id) ? [source.get(id)] : [],
  );
  const generatedItems = entry.node_ids.flatMap((id) =>
    generated.has(id) ? [generated.get(id)] : [],
  );

  async function mark() {
    setSaving(true);
    setError("");
    try {
      await onMark(index, !isReviewed);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存审核状态失败。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="review-workspace">
      <div className="review-top">
        <label>
          审核项
          <select
            value={index}
            disabled={saving}
            onChange={(event) => {
              setIndex(Number(event.currentTarget.value));
              setError("");
            }}
          >
            {review.review.map((item, itemIndex) => (
              <option key={itemIndex} value={itemIndex}>
                {itemIndex + 1}. {item.decision || "审核"}
                {review.reviewed_indices.includes(itemIndex)
                  ? "（已审核）"
                  : ""}
              </option>
            ))}
          </select>
        </label>
        <p role="status">
          已审核 {review.reviewed_indices.length} / {count} 项
        </p>
      </div>
      <div className="review-summary">
        <strong>{entry.decision || "待审核"}</strong>
        {entry.needs_confirmation && !isReviewed && (
          <span className="review-pending">待确认</span>
        )}
        <p>{entry.reason}</p>
      </div>
      <div className="review-comparison">
        <section aria-labelledby="review-source-title">
          <h3 id="review-source-title">报告原文</h3>
          {!sourceItems.length && <p>没有对应的原文片段。</p>}
          {sourceItems.map((block, blockIndex) => (
            <SourceExcerpt key={blockIndex} block={block} />
          ))}
        </section>
        <section aria-labelledby="review-template-title">
          <h3 id="review-template-title">模板当前内容</h3>
          {!generatedItems.length && <p>未生成对应组件，或该组件已被删除。</p>}
          {generatedItems.map((node) => (
            <div key={node.id} className="review-generated">
              <ComponentExcerpt node={node} />
              <button type="button" onClick={() => onLocate(node.id)}>
                在编辑器中定位
              </button>
            </div>
          ))}
        </section>
      </div>
      {error && (
        <div className="conversion-feedback conversion-error" role="alert">
          {error}
        </div>
      )}
      <div className="review-footer">
        <div className="conversion-actions">
          <button
            type="button"
            disabled={index === 0 || saving}
            onClick={() => {
              setIndex(index - 1);
              setError("");
            }}
          >
            上一项
          </button>
          <button
            type="button"
            disabled={index + 1 === count || saving}
            onClick={() => {
              setIndex(index + 1);
              setError("");
            }}
          >
            下一项
          </button>
        </div>
        <button
          type="button"
          className={isReviewed ? undefined : "primary"}
          disabled={saving}
          onClick={() => void mark()}
        >
          {saving ? "正在保存…" : isReviewed ? "取消已审核" : "标为已审核"}
        </button>
      </div>
    </div>
  );
}
