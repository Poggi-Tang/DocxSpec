export interface ReportNode {
  id: string;
  kind: string;
  label: string;
  text: string;
  level: number;
  style: {
    size?: number;
    font?: string;
    align?: string;
    before?: number;
    after?: number;
    line?: number;
    color?: string;
    bold?: boolean;
    italic?: boolean;
  };
  rows: string[][];
  rows_source: string;
  source: string;
  equals: string;
  empty: string;
  target: string;
  caption_type: string;
  numbering: string;
  asset: string;
  width: number;
  columns: number[];
  header_rows: number;
  children: ReportNode[];
  component_id?: string;
  component_version?: number;
}

export interface DraftContent {
  name: string;
  document: {
    schema_version: string;
    nodes: ReportNode[];
    header: string;
    footer: string;
    page: { width: number; height: number; margin: number };
  };
  data: Record<string, unknown>;
}

export interface TemplateSummary {
  id: string;
  set_id: string;
  name: string;
  version: number;
  updated: string;
  archived?: number;
}

export interface Template extends TemplateSummary, DraftContent {}

export interface NodeLocation {
  node: ReportNode;
  ancestors: ReportNode[];
}

export function flat(nodes: ReportNode[]): ReportNode[] {
  return nodes.flatMap((node) => [node, ...flat(node.children)]);
}

export function locateNodes(
  nodes: ReportNode[],
  ancestors: ReportNode[] = [],
): NodeLocation[] {
  return nodes.flatMap((node) => [
    { node, ancestors },
    ...locateNodes(node.children, [...ancestors, node]),
  ]);
}

export function cloneNode(
  node: ReportNode,
  keepExternalTargets = false,
): ReportNode {
  const copy = structuredClone(node);
  const nodes = flat([copy]);
  const ids = new Map<string, string>();
  for (const n of nodes) {
    const id = crypto.randomUUID();
    ids.set(n.id, id);
    n.id = id;
  }
  for (const n of nodes) {
    if (n.target)
      n.target = ids.get(n.target) ?? (keepExternalTargets ? n.target : "");
  }
  return copy;
}

const repeatIds = (location: NodeLocation) =>
  location.ancestors
    .filter((node) => node.kind === "repeat")
    .map((node) => node.id);

export function captionTargets(
  caption: NodeLocation,
  locations: NodeLocation[],
): ReportNode[] {
  const scope = repeatIds(caption);
  const conditions = new Set(
    caption.ancestors
      .filter((node) => node.kind === "condition")
      .map((node) => node.id),
  );
  const kind = caption.node.caption_type === "table" ? "table" : "image";
  return locations
    .filter((location) => {
      if (location.node.kind !== kind) return false;
      const targetScope = repeatIds(location);
      return (
        targetScope.length === scope.length &&
        targetScope.every((id, i) => id === scope[i]) &&
        location.ancestors.every(
          (node) => node.kind !== "condition" || conditions.has(node.id),
        )
      );
    })
    .map(({ node }) => node);
}

function fieldValue(data: unknown, path: string): unknown {
  let value = data;
  for (const key of path.split(".")) {
    if (
      value === null ||
      typeof value !== "object" ||
      Array.isArray(value) ||
      !Object.hasOwn(value, key)
    )
      return undefined;
    value = (value as Record<string, unknown>)[key];
  }
  return value;
}

function isScalar(value: unknown): boolean {
  return (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  );
}

function scalarPaths(data: unknown, prefix = ""): string[] {
  if (data === null || typeof data !== "object" || Array.isArray(data))
    return [];
  return Object.entries(data).flatMap(([key, value]) => {
    if (!/^[\p{L}\p{N}_]+$/u.test(key)) return [];
    const path = prefix ? prefix + "." + key : key;
    return isScalar(value) ? [path] : scalarPaths(value, path);
  });
}

function conditionText(value: unknown): string | undefined {
  if (value === null) return "None";
  if (typeof value !== "number")
    return isScalar(value) ? String(value) : undefined;
  if (!Number.isFinite(value)) return "None";

  // The compiler receives JSON integers as int and decimals as float.
  // Match Python's scientific notation for the latter, including e-06.
  const jsonNumber = JSON.stringify(value);
  if (!/[.e]/.test(jsonNumber)) return jsonNumber;
  const magnitude = Math.abs(value);
  if (magnitude >= 1e-4 && magnitude < 1e16) return jsonNumber;
  const [coefficient, exponent] = value.toExponential().split("e");
  return coefficient + "e" + exponent[0] + exponent.slice(1).padStart(2, "0");
}

export function availableFields(
  data: DraftContent["data"],
  location: NodeLocation,
): string[] {
  const insideRepeat = location.ancestors.some(
    (node) => node.kind === "repeat",
  );
  const globalData = { ...data };
  if (insideRepeat) delete globalData.item;
  const globalFields = () => scalarPaths(globalData);
  let contexts = [data];
  for (const ancestor of location.ancestors) {
    if (ancestor.kind === "repeat") {
      const next: DraftContent["data"][] = [];
      for (const context of contexts) {
        const items = fieldValue(context, ancestor.source);
        if (!Array.isArray(items) || items.length > 200) return globalFields();
        // Don't materialize a sample larger than the compiler's expansion limit.
        if (next.length + items.length > 2000) return globalFields();
        for (const item of items) next.push({ ...globalData, item });
      }
      contexts = next;
    } else if (ancestor.kind === "condition") {
      contexts = contexts.filter(
        (context) =>
          conditionText(fieldValue(context, ancestor.source)) ===
          ancestor.equals,
      );
    }
  }
  if (!contexts.length) return globalFields();
  return scalarPaths(contexts[0]).filter((path) =>
    contexts.every((context) => isScalar(fieldValue(context, path))),
  );
}
