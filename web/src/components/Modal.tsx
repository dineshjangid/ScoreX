import { useEffect, useRef } from "react";

// Thin wrapper over the native <dialog> element: modal focus handling and
// Esc-to-close come from the browser. Clicking the backdrop also closes it.
export default function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="modal"
      aria-label={title}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="modal-body">
        <div className="modal-header">
          <h2>{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>
        {open && children}
      </div>
    </dialog>
  );
}
