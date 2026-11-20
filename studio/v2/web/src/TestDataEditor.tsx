import { useState } from "react";
import type { DraftContent } from "./document";

type TestData = DraftContent["data"];
type Path = (string | number)[];

const fieldLabels: Record<string, string> = {
  project: "项目",
  name: "名称",
  testCases: "测试用例",
  steps: "测试步骤",
  expected: "预期结果",
  result: "实际结果",
};

function isObject(value: unknown): value is TestData {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function blank(value: unknown): unknown {
  if (Array.isArray(value)) return [];
  if (isObject(value))
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, blank(item)]),
    );
  if (typeof value === "boolean") return false;
  if (typeof value === "number") return 0;
  return "";
}

function readJson(text: string): TestData {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("JSON 格式无效。请检查括号、引号和逗号后重试。");
  }
  if (!isObject(parsed))
    throw new Error("测试数据必须是 JSON 对象，以 { 开头、以 } 结尾。");
  return parsed;
}

function DataField({
  title,
  value,
  sample,
  path,
  change,
}: {
  title: string;
  value: unknown;
  sample?: unknown;
  path: Path;
  change: (path: Path, value: unknown) => void;
}) {
  if (path.length > 7)
    return <p>{title}包含多层数据，可在高级 JSON 中编辑。</p>;
  if (Array.isArray(value)) {
    const exemplar = value.length
      ? value.at(-1)
      : Array.isArray(sample)
        ? sample.at(-1)
        : undefined;
    return (
      <fieldset className="data-group">
        <legend>
          {title}（{value.length} 条）
        </legend>
        {value.map((item, index) => (
          <fieldset className="data-record" key={index}>
            <legend>第 {index + 1} 条</legend>
            <DataField
              title="值"
              value={item}
              sample={exemplar}
              path={[...path, index]}
              change={change}
            />
            <button
              type="button"
              onClick={() =>
                change(
                  path,
                  value.filter((_, at) => at !== index),
                )
              }
              aria-label={"删除 " + title + "第 " + (index + 1) + " 条"}
            >
              删除此条
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          onClick={() => change(path, [...value, blank(exemplar)])}
          disabled={exemplar === undefined}
          aria-label={"添加 " + title + "记录"}
        >
          添加记录
        </button>
        {exemplar === undefined && <p>空列表的字段可在高级 JSON 中定义。</p>}
      </fieldset>
    );
  }
  if (isObject(value)) {
    return (
      <fieldset className="data-group">
        <legend>{title}</legend>
        {Object.entries(value).map(([key, entry]) => (
          <DataField
            key={key}
            title={fieldLabels[key] ?? key}
            value={entry}
            sample={isObject(sample) ? sample[key] : undefined}
            path={[...path, key]}
            change={change}
          />
        ))}
      </fieldset>
    );
  }
  if (typeof value === "boolean") {
    return (
      <label className="data-checkbox">
        <input
          type="checkbox"
          checked={value}
          onChange={(event) => change(path, event.currentTarget.checked)}
        />
        {title}
      </label>
    );
  }
  if (typeof value === "number") {
    return (
      <label>
        {title}
        <input
          type="number"
          step="any"
          required
          value={Number.isNaN(value) ? "" : value}
          onChange={(event) => change(path, event.currentTarget.valueAsNumber)}
        />
      </label>
    );
  }
  return (
    <label>
      {title}
      <textarea
        rows={2}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => change(path, event.currentTarget.value)}
      />
    </label>
  );
}

export function TestDataEditor({
  data,
  onApply,
}: {
  data: TestData;
  onApply: (data: TestData) => void;
}) {
  const [formData, setFormData] = useState(data);
  const [text, setText] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [error, setError] = useState("");

  function change(path: Path, value: unknown) {
    setFormData((current) => {
      const next = structuredClone(current);
      let owner: any = next;
      for (const step of path.slice(0, -1)) owner = owner[step];
      owner[path.at(-1)!] = value;
      return next;
    });
  }

  return (
    <form
      className="test-data-editor"
      onSubmit={(event) => {
        event.preventDefault();
        setError("");
        try {
          onApply(advanced ? readJson(text) : formData);
        } catch (problem) {
          setError(
            problem instanceof Error ? problem.message : "无法应用测试数据。",
          );
        }
      }}
    >
      <p>编辑预览和导出使用的样例值。应用后的数据随模板保存。</p>
      <div className="data-modes" aria-label="测试数据编辑方式">
        <button
          data-dialog-autofocus
          type="button"
          aria-pressed={!advanced}
          onClick={() => {
            if (!advanced) return;
            try {
              setFormData(readJson(text));
              setAdvanced(false);
              setError("");
            } catch (problem) {
              setError((problem as Error).message);
            }
          }}
        >
          数据表单
        </button>
        <button
          type="button"
          aria-pressed={advanced}
          onClick={(event) => {
            if (advanced) return;
            if (!event.currentTarget.form?.reportValidity()) return;
            setText(JSON.stringify(formData, null, 2));
            setAdvanced(true);
            setError("");
          }}
        >
          高级 JSON
        </button>
      </div>
      {advanced ? (
        <>
          <textarea
            className="json"
            aria-label="测试数据 JSON"
            aria-invalid={!!error}
            aria-describedby={error ? "test-data-error" : undefined}
            value={text}
            onChange={(event) => {
              setText(event.currentTarget.value);
              setError("");
            }}
          />
          {error && (
            <p id="test-data-error" className="form-error" role="alert">
              {error}
            </p>
          )}
        </>
      ) : (
        <div className="data-fields">
          {Object.entries(formData).map(([key, value]) => (
            <DataField
              key={key}
              title={fieldLabels[key] ?? key}
              value={value}
              sample={data[key]}
              path={[key]}
              change={change}
            />
          ))}
          {!Object.keys(formData).length && (
            <p>还没有测试字段。可用高级 JSON 添加。</p>
          )}
        </div>
      )}
      <button className="primary dialog-primary" type="submit">
        应用数据
      </button>
    </form>
  );
}
