const $ = (id) => document.getElementById(id);
const escape = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let state;
let masterTemplate;
let fieldEngine = "mark";

let history = [],
  future = [];
function commit(fn, redraw = true) {
  history.push(JSON.stringify(state));
  if (history.length > 30) history.shift();
  future = [];
  fn();
  if (redraw) render();
  persist();
}
function notify(t) {
  $("toast").textContent = t;
  $("toast").style.display = "block";
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(
    () => ($("toast").style.display = "none"),
    2400,
  );
}
function fmt(i) {
  return {
    size: 14,
    line: "1",
    color: "#f2f4f8",
    style: "DS表格文字",
    bold: false,
    italic: false,
    center: false,
    ...state.format[i],
  };
}
function changeFormat(key, val) {
  commit(
    () =>
      (state.format[state.selected] = { ...state.format[state.selected], [key]: val }),
  );
}
function caseHTML(c, i, preview = false) {
  const f = fmt(i);
  return `<section class="block ${!preview && state.selected === i ? "selected" : ""}" data-case="${i}" style="font-size:${f.size}px;line-height:${f.line};font-weight:${f.bold || f.style === "DS一级标题" ? "bold" : "normal"};font-style:${f.italic ? "italic" : "normal"};text-align:${f.center ? "center" : "left"}">${!preview && state.selected === i ? '<span class="badge"><i class="ph ph-copy" style="font-size:16px"></i> 按测试用例重复</span>' : ""}<h2>${escape(c.id)}　${preview ? escape(c.name) : `<span contenteditable="true" class="editable" data-name="${i}" aria-label="测试项名称 ${i + 1}">${escape(c.name)}</span>`}</h2><table><tbody><tr><td style="background:${f.color}">测试步骤</td><td><ol>${c.steps.map((s, j) => `<li ${preview ? "" : `contenteditable="true" data-field="steps" data-index="${i}" data-step="${j}"`}>${escape(s)}</li>`).join("")}</ol></td></tr><tr><td style="background:${f.color}">预期结果</td><td>${preview ? escape(c.expected) : '<span class="token">{{ 预期结果 }}</span>'}</td></tr><tr><td style="background:${f.color}">实际结果</td><td>${fieldHTML(c.actual, "actual", i, preview)}</td></tr><tr><td style="background:${f.color}">测试结论</td><td>${fieldHTML(c.result, "result", i, preview)}</td></tr><tr><td style="background:${f.color}">截图</td><td>${c.image ? `<button class="upload" data-upload="${i}" aria-label="替换截图"><img src="${c.image}" alt="${escape(c.name)}截图"></button>` : preview ? '<span class="hint">未提供截图</span>' : `<button class="upload" data-upload="${i}"><i class="ph ph-image"></i><span>点击插入截图<br>（支持上传或替换）</span></button>`}</td></tr></tbody></table></section>`;
}
function cases(preview) {
  let arr = state.cases
    .map((c, i) => ({ c, i }))
    .filter(({ c }) => state.source !== "失败用例" || c.result === "失败");
  if (state.repeat === "仅首条记录") arr = arr.slice(0, 1);
  return arr.length
    ? arr.map(({ c, i }) => caseHTML(c, i, preview)).join("")
    : state.empty === "显示待补充"
      ? '<div class="empty-section">测试数据待补充</div>'
      : preview
        ? ""
        : '<div class="empty-section">当前数据源没有记录，生成时将隐藏区块。请修改样例数据。</div>';
}
function caseSection() {
  return state.section_meta ? state.section_meta.findIndex((entry) => entry.kind === "cases") : 2;
}
function sectionNumber(index) {
  if (!state.section_meta) return String(index + 1);
  const counts = [0, 0, 0, 0, 0, 0];
  for (let i = 0; i <= index; i++) {
    const level = state.section_meta[i].level;
    if (!level) continue;
    counts[level - 1]++;
    counts.fill(0, level);
  }
  const level = state.section_meta[index].level;
  return level ? counts.slice(0, level).join(".") : "";
}
function templateTable(rows) {
  return `<table><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${escape(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function content(preview = false) {
  const section = state.sections[state.section];
  const entry = state.section_meta?.[state.section];
  const number = sectionNumber(state.section);
  const title = `<h1>${escape(number)}${number ? "　" : ""}${escape(section)}</h1>`;
  if (entry && ["toc", "figures", "tables"].includes(entry.kind)) {
    const items = entry.kind === "toc"
      ? state.sections.map((text, index) => ({ text, index })).filter(({ index }) => state.section_meta[index].level)
      : state.cases.map((item) => ({ text: entry.kind === "figures" ? `${item.name}截图` : item.name }))
          .filter((_, index) => entry.kind !== "figures" || state.cases[index].image);
    return title + '<p class="hint">目录由 Word 域生成，页码以导出的文档为准。</p>' + items.map(({ text, index }) =>
      `<p style="margin-left:${index === undefined ? 0 : (state.section_meta[index].level - 1) * 16}px">${index === undefined ? "" : escape(sectionNumber(index)) + "　"}${escape(text)}</p>`).join("");
  }
  if (entry?.kind === "revision")
    return title + '<p class="hint">沿用内置母版的修改记录表。</p>' + templateTable(masterTemplate.revision_rows);
  if (state.section === caseSection())
    return title + `<p ${preview ? "" : 'contenteditable="true" class="editable" id="intro" aria-label="章节说明"'}>${escape(state.intro)}</p>${cases(preview)}`;
  const defaults = [
    "测试报告\n产品名称：示例系统\n报告版本：V1.0",
    "测试环境：桌面浏览器\n测试范围：登录与权限校验", "", "暂无待处理问题。",
    "本轮测试完成，结果详见测试明细。",
  ];
  const text = state.texts[state.section] ?? (entry ? "" : defaults[state.section]) ?? "";
  return title + (entry?.kind === "cover" ? `<p>${escape(masterTemplate.file_number)}</p>` : "") +
    `<p ${preview ? "" : 'contenteditable="true" class="editable" id="section-text" aria-label="章节内容"'} style="white-space:pre-wrap;margin-top:35px">${escape(text)}</p>` +
    (entry?.kind === "cover" ? templateTable(masterTemplate.signature_rows) : "");
}
function render() {
  $("nav-items").innerHTML = state.sections
    .map(
      (s, i) =>
        `<button class="nav ${i === state.section ? "selected" : ""}" data-nav="${i}" style="padding-left:${12 + Math.max(0, (state.section_meta?.[i].level || 1) - 1) * 12}px"><i class="ph ph-file"></i>${escape(s)}</button>`,
    )
    .join("");
  $("paper").innerHTML = content();
  const f = fmt(state.selected);
  ["source", "repeat", "empty"].forEach((id) => ($(id).value = state[id]));
  $("style-top").value = $("style-side").value = f.style;
  $("font-size").value = f.size;
  $("size-side").value = f.size;
  $("color").value = f.color;
  $("line-height").value = f.line;
  $("bold").classList.toggle("format-on", f.bold);
  $("italic").classList.toggle("format-on", f.italic);
  $("selection-hint").textContent = "正在编辑：测试项 " + (state.selected + 1);
  $("undo").disabled = !history.length;
  $("redo").disabled = !future.length;
}
document.addEventListener("click", (e) => {
  let nav = e.target.closest("[data-nav]");
  if (nav) {
    state.section = +nav.dataset.nav;
    render();
  }
  let block = e.target.closest("[data-case]");
  if (
    block &&
    +block.dataset.case !== state.selected &&
    !e.target.closest("[data-upload]")
  ) {
    state.selected = +block.dataset.case;
    render();
  }
  let upload = e.target.closest("[data-upload]");
  if (upload && !e.target.closest("#preview-dialog")) {
    window.uploadIndex = +upload.dataset.upload;
    $("image-file").click();
  }
  if (e.target.closest("[data-close]")) e.target.closest("dialog").close();
});
$("image-file").onchange = () => {
  const file = $("image-file").files[0];
  if (!file) return;
  if (
    !["image/png", "image/jpeg", "image/webp", "image/gif"].includes(
      file.type,
    ) ||
    file.size > 5 * 1024 * 1024
  ) {
    notify("请选择 5MB 以内的 PNG、JPEG、WebP 或 GIF 图片");
    return;
  }
  let i = window.uploadIndex;
  const r = new FileReader();
  r.onload = () => commit(() => (state.cases[i].image = r.result));
  r.readAsDataURL(file);
  $("image-file").value = "";
};
$("sample").onclick = () => {
  $("data-input").value = JSON.stringify(
    state.cases.map(({ image, ...c }) => c),
    null,
    2,
  );
  $("data-error").textContent = "";
  $("data-dialog").showModal();
};
$("apply-data").onclick = () => {
  try {
    let data = JSON.parse($("data-input").value);
    if (!Array.isArray(data) || data.length > 100)
      throw Error("请输入不超过 100 条记录的数组");
    for (const c of data)
      if (
        !c ||
        typeof c !== "object" ||
        !["id", "name", "expected", "actual", "result"].every(
          (k) => typeof c[k] === "string",
        ) ||
        !Array.isArray(c.steps) ||
        !c.steps.every((s) => typeof s === "string")
      )
        throw Error(
          "每条记录需包含 id、name、steps 数组、expected、actual、result 文本",
        );
    commit(() => {
      const old = state.cases;
      const oldFormat = state.format;
      state.format = {};
      state.cases = data.map((c, i) => {
        const prior = old.findIndex((x) => x.id === c.id);
        if (prior >= 0 && oldFormat[prior]) state.format[i] = oldFormat[prior];
        return {
          id: c.id,
          name: c.name,
          steps: c.steps,
          expected: c.expected,
          actual: c.actual,
          result: c.result,
          ...(prior >= 0 && old[prior].image
            ? { image: old[prior].image }
            : {}),
        };
      });
      state.selected = 0;
    });
    $("data-dialog").close();
    notify("样例数据已应用");
  } catch (e) {
    $("data-error").textContent = e.message;
  }
};
$("preview").onclick = () => {
  $("preview-body").innerHTML =
    '<div class="paper">' + content(true) + "</div>";
  $("preview-dialog").showModal();
};
["source", "repeat", "empty"].forEach(
  (id) => ($(id).onchange = () => commit(() => (state[id] = $(id).value))),
);
["style-top", "style-side"].forEach(
  (id) => ($(id).onchange = () => changeFormat("style", $(id).value)),
);
$("font-size").onchange = () => changeFormat("size", +$("font-size").value);
$("size-side").onchange = () =>
  changeFormat("size", Math.min(28, Math.max(12, +$("size-side").value || 15)));
$("color").onchange = () => changeFormat("color", $("color").value);
$("line-height").onchange = () => changeFormat("line", $("line-height").value);
$("bold").onclick = () => changeFormat("bold", !fmt(state.selected).bold);
$("italic").onclick = () => changeFormat("italic", !fmt(state.selected).italic);
$("align").onclick = () => changeFormat("center", !fmt(state.selected).center);
document.querySelectorAll("[data-tab]").forEach(
  (b) =>
    (b.onclick = () => {
      document
        .querySelectorAll("[data-tab]")
        .forEach((x) => x.classList.toggle("on", x === b));
      $("block-panel").classList.toggle("hide", b.dataset.tab !== "block");
      $("style-panel").classList.toggle("hide", b.dataset.tab !== "style");
    }),
);
$("add-case").onclick = () =>
  commit(() => {
    state.section = caseSection();
    state.cases.push({
      id: "TC-" + String(state.cases.length + 1).padStart(3, "0"),
      name: "新测试项",
      steps: ["填写测试步骤"],
      expected: "填写预期结果",
      actual: "待执行",
      result: "待执行",
    });
    state.selected = state.cases.length - 1;
    setTimeout(
      () =>
        document
          .querySelector(".block.selected")
          ?.scrollIntoView({ block: "center" }),
      0,
    );
  });
$("add-section").onclick = () => {
  $("section-name").value = "";
  $("section-dialog").showModal();
};
$("confirm-section").onclick = () => {
  let n = $("section-name").value.trim();
  if (!n) {
    $("section-name").focus();
    return;
  }
  commit(() => {
    state.sections.push(n);
    state.section_meta?.push({ kind: "heading", level: 1 });
    state.section = state.sections.length - 1;
  });
  $("section-dialog").close();
};
$("undo").onclick = () => {
  if (history.length) {
    future.push(JSON.stringify(state));
    state = JSON.parse(history.pop());
    render();
    persist();
  }
};
$("redo").onclick = () => {
  if (future.length) {
    history.push(JSON.stringify(state));
    state = JSON.parse(future.pop());
    render();
    persist();
  }
};
$("properties").onclick = () => {
  let open = document.querySelector(".props").classList.toggle("drawer");
  $("properties").setAttribute("aria-expanded", open);
};
let current = null,
  savedSnapshot = "",
  draftError = false;
const draftKey = "docxspec-studio-master-draft-v1";
const documentData = () => ({ schema: "docxspec-studio-v1", ...state });
function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((k) => [k, stable(value[k])]),
    );
  return value;
}
const snapshot = () => {
  const { section, selected, ...content } = documentData();
  return JSON.stringify(stable(content));
};
function fieldHTML(value, key, i, preview) {
  return preview
    ? escape(value)
    : `<span contenteditable="true" data-field="${key}" data-index="${i}" aria-label="${key === "actual" ? "实际结果" : "测试结论"}">${escape(value)}</span>`;
}
let editStarted = false;
$("paper").addEventListener("focusin", () => {
  editStarted = false;
});
$("paper").addEventListener("input", (e) => {
  const target = e.target.closest('[contenteditable="true"]');
  if (!target) return;
  // Record one undo step per editing session, but persist every input immediately.
  if (!editStarted) {
    history.push(JSON.stringify(state));
    if (history.length > 30) history.shift();
    future = [];
    editStarted = true;
  }
  if (target.dataset.name !== undefined)
    state.cases[+target.dataset.name].name = target.textContent;
  else if (target.id === "intro") state.intro = target.textContent;
  else if (target.id === "section-text")
    state.texts[state.section] = target.innerText;
  else if (target.dataset.field) {
    const i = +target.dataset.index,
      key = target.dataset.field;
    if (key === "steps")
      state.cases[i].steps[+target.dataset.step] = target.innerText;
    else state.cases[i][key] = target.innerText;
  }
  $("undo").disabled = !history.length;
  $("redo").disabled = !future.length;
  persist();
});
function status() {
  const dirty = snapshot() !== savedSnapshot;
  $("save-status").textContent = draftError
    ? "本地草稿未保存，请导出配置"
    : dirty
      ? "有未保存的修改"
      : "已保存到模板库";
  document.querySelector(".template-name").textContent =
    current?.name || "测试报告模板";
}
function persist() {
  try {
    localStorage.setItem(
      draftKey,
      JSON.stringify({ document: documentData(), current, savedSnapshot }),
    );
    draftError = false;
  } catch (e) {
    draftError = true;
  }
  status();
}
window.addEventListener("beforeunload", (e) => {
  if (draftError && snapshot() !== savedSnapshot) {
    e.preventDefault();
    e.returnValue = "";
  }
});
async function api(path, body) {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    let error;
    try {
      error = (await response.json()).error;
    } catch {
      error = "服务请求失败";
    }
    throw Error(error);
  }
  return response;
}
function download(blob, name) {
  const a = document.createElement("a"),
    url = URL.createObjectURL(blob);
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("export").onclick = () => {
  download(
    new Blob([JSON.stringify(documentData(), null, 2)], {
      type: "application/json",
    }),
    "docxspec-template.json",
  );
  notify("已导出模板配置，可通过“导入配置”重新打开");
};
$("save-template").onclick = () => {
  $("template-name").value = current?.name || "测试报告模板";
  $("save-error").textContent = "";
  $("save-dialog").showModal();
};
async function save(copy) {
  const payload = {
    name: $("template-name").value.trim(),
    document: documentData(),
    ...(current && !copy ? { id: current.id, version: current.version } : {}),
  };
  $("confirm-save").disabled = $("save-copy").disabled = true;
  try {
    const record = await (await api("/api/templates", payload)).json();
    current = { id: record.id, version: record.version, name: record.name };
    savedSnapshot = snapshot();
    persist();
    $("save-dialog").close();
    notify("模板已保存到磁盘");
  } catch (e) {
    $("save-error").textContent = e.message;
  } finally {
    $("confirm-save").disabled = $("save-copy").disabled = false;
  }
}
$("confirm-save").onclick = () => save(false);
$("save-copy").onclick = () => save(true);
function mayReplace() {
  return (
    snapshot() === savedSnapshot ||
    confirm("当前修改尚未保存到模板库。是否放弃这些修改并打开所选模板？")
  );
}
async function openRecord(id) {
  if (!mayReplace()) return;
  try {
    const record = await (
      await api("/api/templates/" + encodeURIComponent(id))
    ).json();
    state = record.document;
    current = { id: record.id, version: record.version, name: record.name };
    history = [];
    future = [];
    savedSnapshot = snapshot();
    render();
    persist();
    $("library-dialog").close();
    notify("模板已打开");
  } catch (e) {
    notify(e.message);
  }
}
$("open-template").onclick = async () => {
  $("library-dialog").showModal();
  $("template-list").textContent = "正在读取…";
  try {
    const records = await (await api("/api/templates")).json();
    $("template-list").innerHTML = records.length
      ? records
          .map(
            (r) =>
              `<div style="display:flex;justify-content:space-between;padding:14px 0;border-bottom:1px solid #ddd"><span>${escape(r.name)}<br><small>版本 ${r.version} · ${escape(new Date(r.updated).toLocaleString())}</small></span><button class="outline" data-open="${r.id}">打开</button></div>`,
          )
          .join("")
      : "暂无模板，请先保存。";
  } catch (e) {
    $("template-list").textContent = e.message;
  }
};
$("template-list").onclick = (e) => {
  const b = e.target.closest("[data-open]");
  if (b) openRecord(b.dataset.open);
};
$("import-template").onclick = () => $("config-file").click();
$("config-file").onchange = async () => {
  const file = $("config-file").files[0];
  $("config-file").value = "";
  if (!file) return;
  try {
    if (file.size > 25 * 1024 * 1024) throw Error("配置不能超过 25 MB");
    const validated = await (
      await api("/api/validate", JSON.parse(await file.text()))
    ).json();
    if (!mayReplace()) return;
    state = validated;
    current = null;
    savedSnapshot = "";
    history = [];
    future = [];
    render();
    persist();
    notify("配置已导入，请保存到模板库");
  } catch (e) {
    notify("导入失败：" + e.message);
  }
};
$("generate").onclick = async () => {
  const button = $("generate");
  button.disabled = true;
  button.textContent = "正在生成…";
  try {
    const response = await api("/api/render", documentData());
    download(await response.blob(), "docxspec-report.docx");
    notify(fieldEngine === "mark" ? "DOCX 已生成，已请求在 Office 打开时更新域" : "DOCX 已生成，已检查保存后的域结果");
  } catch (e) {
    notify("生成失败：" + e.message);
  } finally {
    button.disabled = false;
    button.textContent = "导出 DOCX";
  }
};
async function boot() {
  try {
    masterTemplate = await (await api("/api/master")).json();
    state = masterTemplate.document;
    const health = await (await api("/api/health")).json();
    fieldEngine = health.field_engine ?? (health.refresh_fields ? "word" : "mark");
    render();
    const draft = JSON.parse(localStorage.getItem(draftKey) || "null");
    if (draft) {
      state = await (await api("/api/validate", draft.document)).json();
      current = draft.current;
      savedSnapshot = draft.savedSnapshot || "";
      render();
      notify("已恢复本机草稿");
    }
    status();
  } catch (e) {
    $("save-status").textContent = "服务不可用或草稿恢复失败";
    notify(e.message);
  }
}
boot();
