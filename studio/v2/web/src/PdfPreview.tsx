import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ButtonHTMLAttributes,
} from "react";
import * as pdfjs from "pdfjs-dist";
import worker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { Job } from "./api";
import { usePdfControls } from "./PdfControls";

pdfjs.GlobalWorkerOptions.workerSrc = worker;

interface PdfMapping {
  page: number;
  node_id: string;
  text: string;
  rects: [number, number, number, number][];
}

export interface RenderResult {
  engine: string;
  engine_version: string;
  pages: number;
  page_sizes: [number, number][];
  field_status: string;
  mapping: PdfMapping[];
}

export function PdfPreview({
  job,
  controlsTarget,
  onSelect,
  selected,
  dropTarget,
}: {
  job: Job<RenderResult>;
  controlsTarget: HTMLDivElement | null;
  onSelect: (id: string, keyboard: boolean) => void;
  selected: string;
  dropTarget?: (
    id: string,
    zone: string,
  ) => ButtonHTMLAttributes<HTMLButtonElement> | undefined;
}) {
  const canvases = useRef(new Map<number, HTMLCanvasElement>());
  const [error, setError] = useState("");
  const pages = job.result.page_sizes;
  const { pageStack, scale, minimumWidth, toolbar } = usePdfControls(
    pages,
    canvases,
    controlsTarget,
    !error,
  );
  const mappings = useMemo(() => {
    const grouped = new Map<number, PdfMapping[]>();
    for (const mapping of job.result.mapping) {
      const group = grouped.get(mapping.page);
      if (group) group.push(mapping);
      else grouped.set(mapping.page, [mapping]);
    }
    return grouped;
  }, [job.result.mapping]);

  useEffect(() => {
    let stopped = false;
    let drawing: pdfjs.RenderTask | undefined;
    const loading = pdfjs.getDocument(
      "/api/v2/artifacts/" + job.id + "/report.pdf",
    );
    async function draw() {
      const doc = await loading.promise;
      for (let number = 1; !stopped && number <= doc.numPages; number++) {
        const page = await doc.getPage(number);
        if (stopped) return;
        const canvas = canvases.current.get(number - 1);
        if (!canvas) return;
        const viewport = page.getViewport({ scale: 1.5 });
        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        drawing = page.render({ canvas, viewport });
        await drawing.promise;
        if (!stopped) canvas.dataset.ready = "true";
      }
    }
    draw().catch((reason) => {
      if (!stopped) setError("PDF 加载失败：" + reason.message);
    });
    return () => {
      stopped = true;
      drawing?.cancel();
      void loading.destroy().catch(() => {});
    };
  }, [job.id]);

  if (error) return <p role="alert">{error}</p>;
  return (
    <>
      {toolbar}
      <div
        className={"pdf-pages pdf-scalable" + (dropTarget ? " can-drop" : "")}
        ref={pageStack}
        style={{ minWidth: minimumWidth }}
      >
        {pages.map(([width, height], index) => (
          <div
            key={index}
            className="pdf-page"
            data-pdf-page={index + 1}
            style={{ width: width * scale, aspectRatio: width / height }}
          >
            <canvas
              ref={(el) => {
                if (el) canvases.current.set(index, el);
                else canvases.current.delete(index);
              }}
            />
            {mappings.get(index)?.flatMap((mapping, part) =>
              mapping.rects.map(([x0, y0, x1, y1], rect) => {
                const { className = "", ...events } =
                  dropTarget?.(
                    mapping.node_id,
                    "pdf:" + index + ":" + part + ":" + rect,
                  ) ?? {};
                return (
                  <button
                    key={part + ":" + rect}
                    className={
                      "pdf-hit" +
                      (mapping.node_id === selected ? " chosen" : "") +
                      " " +
                      className
                    }
                    title={"编辑 " + mapping.text}
                    aria-label={"编辑 " + mapping.text}
                    aria-pressed={mapping.node_id === selected}
                    onClick={(event) =>
                      onSelect(mapping.node_id, event.detail === 0)
                    }
                    style={{
                      left: (x0 / width) * 100 + "%",
                      top: (y0 / height) * 100 + "%",
                      width: ((x1 - x0) / width) * 100 + "%",
                      height: ((y1 - y0) / height) * 100 + "%",
                    }}
                    {...events}
                  />
                );
              }),
            )}
          </div>
        ))}
      </div>
    </>
  );
}
