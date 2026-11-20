import { CaretLeft, CaretRight, Minus, Plus } from "@phosphor-icons/react";
import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import "./pdf-preview.css";

const ZOOM_STEPS = [50, 75, 100, 125, 150, 200];
const CSS_PIXELS_PER_POINT = 96 / 72;
type Zoom = "page" | "width" | number;

function scrollPadding(view: HTMLElement) {
  const css = getComputedStyle(view);
  return {
    top: Number.parseFloat(css.paddingTop) || 0,
    bottom: Number.parseFloat(css.paddingBottom) || 0,
    left: Number.parseFloat(css.paddingLeft) || 0,
    right: Number.parseFloat(css.paddingRight) || 0,
  };
}

export function usePdfControls(
  pages: [number, number][],
  canvases: RefObject<Map<number, HTMLCanvasElement>>,
  controlsTarget: HTMLDivElement | null,
  enabled: boolean,
) {
  const pageStack = useRef<HTMLDivElement>(null);
  const scrollView = useRef<HTMLElement | null>(null);
  const zoomAnchor = useRef<number | null>(null);
  const [zoom, setZoom] = useState<Zoom>("page");
  const [pageNumber, setPageNumber] = useState(1);
  const [pageEntry, setPageEntry] = useState<string | null>(null);
  const [fitSize, setFitSize] = useState({ width: 640, height: 480 });
  const { width: widestPage, height: tallestPage } = useMemo(
    () =>
      pages.reduce(
        (area, [width, height]) => ({
          width: Math.max(area.width, width),
          height: Math.max(area.height, height),
        }),
        { width: 1, height: 1 },
      ),
    [pages],
  );
  const widthScale = fitSize.width / widestPage;
  const scale =
    zoom === "page"
      ? Math.min(widthScale, fitSize.height / tallestPage)
      : zoom === "width"
        ? widthScale
        : (zoom / 100) * CSS_PIXELS_PER_POINT;
  const percent = Math.round((scale / CSS_PIXELS_PER_POINT) * 100);
  const smaller = ZOOM_STEPS.filter((step) => step < percent).at(-1);
  const larger = ZOOM_STEPS.find((step) => step > percent);

  useLayoutEffect(() => {
    const stack = pageStack.current;
    const view = stack?.closest<HTMLElement>(".canvas");
    if (!enabled || !view || !stack) return;
    scrollView.current = view;

    let frame = 0;
    let padding = scrollPadding(view);
    function readVisiblePage() {
      frame = 0;
      const rect = view.getBoundingClientRect();
      const top = rect.top + view.clientTop + padding.top;
      const bottom =
        rect.top + view.clientTop + view.clientHeight - padding.bottom;
      let visible = 0;
      let current = 0;
      for (const [index, canvas] of canvases.current) {
        const page = canvas.parentElement?.getBoundingClientRect();
        if (!page) continue;
        if (page.top >= bottom) break;
        const overlap = Math.min(page.bottom, bottom) - Math.max(page.top, top);
        if (overlap > visible) {
          visible = overlap;
          current = index + 1;
        }
      }
      if (current) setPageNumber(current);
    }

    function schedulePageUpdate() {
      if (!frame) frame = window.requestAnimationFrame(readVisiblePage);
    }

    function measureFitSize() {
      padding = scrollPadding(view);
      const start =
        stack.getBoundingClientRect().top -
        view.getBoundingClientRect().top -
        view.clientTop +
        view.scrollTop -
        padding.top;
      const width = Math.max(
        1,
        view.clientWidth - padding.left - padding.right,
      );
      const height = Math.max(
        1,
        view.clientHeight - padding.top - padding.bottom - Math.max(0, start),
      );
      setFitSize((previous) =>
        previous.width === width && previous.height === height
          ? previous
          : { width, height },
      );
      schedulePageUpdate();
    }

    const resize = new ResizeObserver(measureFitSize);
    resize.observe(view);
    if (stack.previousElementSibling)
      resize.observe(stack.previousElementSibling);
    view.addEventListener("scroll", schedulePageUpdate, { passive: true });
    measureFitSize();
    return () => {
      resize.disconnect();
      view.removeEventListener("scroll", schedulePageUpdate);
      if (frame) window.cancelAnimationFrame(frame);
      scrollView.current = null;
    };
  }, [canvases, enabled]);

  function jumpTo(number: number) {
    const destination = Math.max(1, Math.min(pages.length, Math.round(number)));
    const view = scrollView.current;
    const page = canvases.current.get(destination - 1)?.parentElement;
    if (!view || !page) return;
    view.scrollTop +=
      page.getBoundingClientRect().top -
      view.getBoundingClientRect().top -
      view.clientTop -
      scrollPadding(view).top;
    setPageNumber(destination);
    setPageEntry(null);
  }

  function changeZoom(next: Zoom) {
    if (next === zoom) return;
    zoomAnchor.current = pageNumber;
    setZoom(next);
  }

  useLayoutEffect(() => {
    if (zoomAnchor.current === null) return;
    const number = zoomAnchor.current;
    zoomAnchor.current = null;
    jumpTo(number);
    const view = scrollView.current;
    if (view) view.scrollLeft = (view.scrollWidth - view.clientWidth) / 2;
  }, [scale, zoom]);

  const toolbar =
    enabled && controlsTarget
      ? createPortal(
          <div className="pdf-tools" role="group" aria-label="PDF 查看工具">
            <div className="pdf-tool-group" role="group" aria-label="预览缩放">
              <button
                type="button"
                title="缩小"
                aria-label="缩小"
                disabled={smaller === undefined}
                onClick={() => smaller !== undefined && changeZoom(smaller)}
              >
                <Minus aria-hidden="true" />
              </button>
              <label>
                缩放
                <select
                  aria-label="缩放"
                  value={zoom}
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    changeZoom(
                      value === "page" || value === "width"
                        ? value
                        : Number(value),
                    );
                  }}
                >
                  <option value="page">适合整页</option>
                  <option value="width">适合宽度</option>
                  {ZOOM_STEPS.map((step) => (
                    <option key={step} value={step}>
                      {step}%
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                title="放大"
                aria-label="放大"
                disabled={larger === undefined}
                onClick={() => larger !== undefined && changeZoom(larger)}
              >
                <Plus aria-hidden="true" />
              </button>
            </div>
            <form
              className="pdf-tool-group"
              aria-label="预览页码"
              noValidate
              onSubmit={(event) => {
                event.preventDefault();
                const requested = Number(pageEntry ?? pageNumber);
                if (Number.isFinite(requested) && pageEntry !== "")
                  jumpTo(requested);
                else setPageEntry(null);
              }}
            >
              <button
                type="button"
                title="上一页"
                aria-label="上一页"
                disabled={pageNumber <= 1}
                onClick={() => jumpTo(pageNumber - 1)}
              >
                <CaretLeft aria-hidden="true" />
              </button>
              <label>
                页码
                <input
                  aria-label="跳转页码"
                  type="number"
                  min="1"
                  max={pages.length}
                  step="1"
                  value={pageEntry ?? pageNumber}
                  onChange={(event) => setPageEntry(event.currentTarget.value)}
                  onBlur={(event) => {
                    if (!event.currentTarget.form?.contains(event.relatedTarget))
                      setPageEntry(null);
                  }}
                />
              </label>
              <span className="pdf-page-count">/ {pages.length}</span>
              <button type="submit">跳转</button>
              <button
                type="button"
                title="下一页"
                aria-label="下一页"
                disabled={pageNumber >= pages.length}
                onClick={() => jumpTo(pageNumber + 1)}
              >
                <CaretRight aria-hidden="true" />
              </button>
              <span className="pdf-sr-only" aria-live="polite">
                第 {pageNumber} 页，共 {pages.length} 页
              </span>
            </form>
          </div>,
          controlsTarget,
        )
      : null;

  return { pageStack, scale, minimumWidth: widestPage * scale, toolbar };
}
