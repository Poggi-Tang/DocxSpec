import { useEffect, useId, useRef, useState } from "react";

export function ComponentContent({
  value,
  fields,
  onChange,
}: {
  value: string;
  fields: string[];
  onChange: (value: string) => void;
}) {
  const fieldId = useId();
  const area = useRef<HTMLTextAreaElement>(null);
  const visited = useRef(false);
  const [insertError, setInsertError] = useState("");
  function insertField(path: string) {
    if (!path) return;
    const textarea = area.current;
    const start = visited.current ? textarea.selectionStart : value.length;
    const end = visited.current ? textarea.selectionEnd : value.length;
    const marker = "{{" + path + "}}";
    const next = value.slice(0, start) + marker + value.slice(end);
    if (next.length > 30000) {
      setInsertError("插入字段后内容将超过 30,000 字符，请先删减部分内容。");
      return;
    }
    setInsertError("");
    onChange(next);
    requestAnimationFrame(() => {
      if (!textarea.isConnected) return;
      textarea.focus();
      textarea.setSelectionRange(start + marker.length, start + marker.length);
    });
  }
  return (
    <div className="component-content">
      <label htmlFor={fieldId}>内容</label>
      <textarea
        id={fieldId}
        ref={area}
        rows={4}
        maxLength={30000}
        aria-describedby={
          fieldId + "-help" + (insertError ? " " + fieldId + "-error" : "")
        }
        value={value}
        onFocus={() => (visited.current = true)}
        onChange={(event) => {
          setInsertError("");
          onChange(event.currentTarget.value);
        }}
      />
      <small id={fieldId + "-help"}>
        字段会插入光标处，或替换选中的文字。重复区块内使用 item。
      </small>
      <select
        aria-label="插入数据字段"
        value=""
        onChange={(event) => insertField(event.currentTarget.value)}
      >
        <option value="">＋ 插入数据字段</option>
        {fields.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
      {insertError && (
        <small
          id={fieldId + "-error"}
          className="component-parameter-error"
          aria-live="polite"
        >
          {insertError}
        </small>
      )}
    </div>
  );
}

interface NumberParameterProps {
  label: string;
  value?: number | null;
  update: (value: number | null) => void;
  min: number;
  max: number;
  integer?: boolean;
  allowEmpty?: boolean;
  validate?: (value: number) => string | undefined;
  unit?: string;
  placeholder?: string;
}

export function NumberParameter({
  label,
  value,
  update,
  min,
  max,
  integer,
  allowEmpty,
  validate,
  unit = "",
  placeholder,
}: NumberParameterProps) {
  const id = useId();
  const [invalid, setInvalid] = useState<{ raw: string; message: string }>();
  useEffect(() => setInvalid(undefined), [value]);
  return (
    <div className="component-parameter">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        step={integer ? "1" : "any"}
        value={invalid?.raw ?? value ?? ""}
        placeholder={placeholder}
        aria-invalid={invalid ? true : undefined}
        aria-describedby={invalid ? id + "-error" : undefined}
        onChange={(event) => {
          const input = event.currentTarget;
          const raw = input.value;
          if (allowEmpty && !raw && !input.validity.badInput) {
            setInvalid(undefined);
            update(null);
            return;
          }
          const number = input.valueAsNumber;
          const rangeError =
            !Number.isFinite(number) ||
            number < min ||
            number > max ||
            (integer && !Number.isInteger(number));
          const message = rangeError
            ? "请输入 " +
              min +
              "–" +
              max +
              unit +
              (integer ? " 的整数。" : " 之间的数字。")
            : validate?.(number);
          if (message) {
            setInvalid({ raw, message });
            return;
          }
          setInvalid(undefined);
          update(number);
        }}
      />
      {invalid && (
        <small
          className="component-parameter-error"
          id={id + "-error"}
          aria-live="polite"
        >
          {invalid.message} 此值未应用。
        </small>
      )}
    </div>
  );
}

export function ColorParameter({
  value,
  update,
}: {
  value?: string | null;
  update: (value: string | null) => void;
}) {
  const id = useId();
  const [invalid, setInvalid] = useState<string>();
  useEffect(() => setInvalid(undefined), [value]);
  return (
    <div className="component-parameter">
      <label htmlFor={id}>颜色（HEX）</label>
      <input
        id={id}
        value={invalid ?? value ?? ""}
        placeholder="继承 DS 样式"
        aria-invalid={invalid !== undefined ? true : undefined}
        aria-describedby={invalid !== undefined ? id + "-error" : undefined}
        onChange={(event) => {
          const raw = event.currentTarget.value;
          const color = raw.replace(/^#/, "");
          if (raw && !/^[0-9a-f]{6}$/i.test(color)) {
            setInvalid(raw);
            return;
          }
          setInvalid(undefined);
          update(color || null);
        }}
      />
      {invalid !== undefined && (
        <small
          className="component-parameter-error"
          id={id + "-error"}
          aria-live="polite"
        >
          请输入 6 位 HEX 颜色，例如 235391。此值未应用。
        </small>
      )}
    </div>
  );
}
