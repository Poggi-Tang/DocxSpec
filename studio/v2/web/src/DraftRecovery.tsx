import { useRef } from "react";
import { flat } from "./document";
import type { RecoverableDraft } from "./editor";
import "./draft-recovery.css";

function excerpt(draft: RecoverableDraft): string {
  const { document, data } = draft.template;
  const text = [
    document.header,
    ...flat(document.nodes).map((node) => node.text),
    document.footer,
    Object.keys(data).length ? JSON.stringify(data) : "",
  ]
    .filter((value) => value?.trim())
    .join(" · ");
  return text.slice(0, 120) || "空白正文";
}

export function DraftRecovery({
  drafts,
  serverVersion,
  recover,
}: {
  drafts: RecoverableDraft[];
  serverVersion: number;
  recover: (draft: RecoverableDraft) => boolean;
}) {
  const disclosure = useRef<HTMLDetailsElement>(null);
  return (
    <details className="draft-recovery" ref={disclosure}>
      <summary>本机草稿 ({drafts.length})</summary>
      <div className="draft-recovery-menu">
        <p>打开一份草稿。当前未保存的内容也会保留在本机。</p>
        {drafts.map((draft, index) => (
          <div className="draft-option" key={draft.key}>
            <span className="draft-option-caption">
              基于 v{draft.template.version}
              {draft.modifiedAt
                ? " · " + new Date(draft.modifiedAt).toLocaleString()
                : ""}
            </span>
            {draft.template.version !== serverVersion && (
              <small>
                已知服务器版本为 v{serverVersion}。可用“复制模板”另存。
              </small>
            )}
            <div className="draft-option-summary">
              {draft.template.name} · {excerpt(draft)}
            </div>
            <button
              onClick={() => {
                if (recover(draft) && disclosure.current)
                  disclosure.current.open = false;
              }}
            >
              恢复草稿 {index + 1}
            </button>
          </div>
        ))}
      </div>
    </details>
  );
}
