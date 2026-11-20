import { useId, useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";

export function StudioDialog({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const titleId = useId();
  const ref = useRef<HTMLDialogElement>(null);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const opener = document.activeElement;
    element.showModal();
    (
      element.querySelector<HTMLElement>("[data-dialog-autofocus]") ??
      element.querySelector<HTMLElement>(".dialog-close")
    )?.focus({ preventScroll: true });
    return () => {
      if (element.open) element.close();
      if (opener instanceof HTMLElement && opener.isConnected) {
        opener.focus({ preventScroll: true });
      }
    };
  }, []);

  return (
    <dialog
      className="modal studio-modal"
      ref={ref}
      aria-labelledby={titleId}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            "button, input, select, textarea, summary, a[href], [tabindex]",
          ),
        ).filter(
          (element) =>
            element.tabIndex >= 0 &&
            !element.matches(":disabled") &&
            element.getClientRects().length > 0,
        );
        const first = controls[0];
        const last = controls.at(-1);
        if (
          (event.shiftKey && document.activeElement === first) ||
          (!event.shiftKey && document.activeElement === last)
        ) {
          event.preventDefault();
          (event.shiftKey ? last : first)?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="section-head">
        <h2 id={titleId}>{title}</h2>
        <button type="button" className="dialog-close" onClick={onClose}>
          关闭
        </button>
      </div>
      {children}
    </dialog>
  );
}
