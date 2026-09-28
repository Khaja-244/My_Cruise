export default function NoticeDialog({
  open,
  title,
  message,
  buttonLabel = 'Continue',
  onClose,
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center bg-black/50 p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="w-full max-w-md rounded-3xl bg-surface p-7 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="notice-dialog-title"
      >
        <div className="grid h-12 w-12 place-items-center rounded-full bg-accent-soft text-2xl text-accent">
          ✓
        </div>
        <h2 id="notice-dialog-title" className="mt-5 text-2xl font-extrabold text-primary">
          {title}
        </h2>
        <p className="mt-2 leading-6 text-secondary">{message}</p>
        <button type="button" className="btn btn-primary mt-6 w-full" onClick={onClose}>
          {buttonLabel}
        </button>
      </div>
    </div>
  );
}
