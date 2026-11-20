import { useState } from "react";

interface EngineChoice {
  id: string;
  name: string;
  available: boolean;
}

export function TemplateSetup({
  kind,
  setName,
  engines = [],
  onCreate,
}: {
  kind: "create-set" | "create-template";
  setName?: string;
  engines?: EngineChoice[];
  onCreate: (name: string, engine: string) => Promise<void>;
}) {
  const creatingSet = kind === "create-set";
  const [name, setNameInput] = useState(creatingSet ? "" : "功能测试报告");
  const [engine, setEngine] = useState(
    engines.find((candidate) => candidate.available)?.id ?? "word",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  return (
    <form
      className="template-setup"
      onSubmit={async (event) => {
        event.preventDefault();
        const cleanedName = name.trim();
        if (!cleanedName) {
          setError("请填写" + (creatingSet ? "模板集" : "模板") + "名称。");
          return;
        }
        setError("");
        setBusy(true);
        try {
          await onCreate(cleanedName, engine);
        } catch (problem) {
          setError(
            problem instanceof Error ? problem.message : "创建失败，请重试。",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      {!creatingSet && (
        <p>
          保存到模板集 <strong>{setName}</strong>
        </p>
      )}
      <label>
        {creatingSet ? "模板集名称" : "新模板名称"}
        <input
          data-dialog-autofocus
          type="text"
          maxLength={100}
          value={name}
          onChange={(event) => setNameInput(event.currentTarget.value)}
          placeholder={creatingSet ? "例如：软件测试" : undefined}
        />
      </label>
      {creatingSet && (
        <label>
          默认排版引擎
          <select
            value={engine}
            onChange={(event) => setEngine(event.currentTarget.value)}
          >
            {engines.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
                {option.available ? " · 可用" : " · 当前环境不可用"}
              </option>
            ))}
          </select>
          <small>
            此设置用于该模板集。选用当前环境不可用的引擎时，可先编辑模板，生成前再选择可用引擎。
          </small>
        </label>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="primary dialog-primary" disabled={busy} type="submit">
        {busy ? "创建中…" : creatingSet ? "创建模板集" : "创建模板"}
      </button>
    </form>
  );
}
