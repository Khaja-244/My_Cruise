export function Loading({ label = 'Loading' }) {
  return (
    <div className="space-y-4" role="status" aria-label={label}>
      <div className="h-5 w-32 rounded bg-surface-subtle animate-pulse" />
      <div className="h-12 w-full rounded-xl bg-surface-subtle animate-pulse" />
      <div className="h-12 w-4/5 rounded-xl bg-surface-subtle animate-pulse" />
      <span className="sr-only">{label}…</span>
    </div>
  );
}

export function ErrorBox({ retry, title = 'Something went wrong', description = "We couldn't load this section. Please try again." }) {
  return (
    <div className="card p-8 text-center" role="alert">
      <div className="mx-auto h-12 w-12 rounded-2xl bg-error-soft text-error grid place-items-center font-extrabold">!</div>
      <h2 className="font-extrabold text-lg text-primary mt-4">{title}</h2>
      <p className="muted text-sm mt-2 max-w-md mx-auto">{description}</p>
      {retry && <button className="btn btn-outline mt-5" onClick={retry}>Try again</button>}
    </div>
  );
}

export function EmptyState({ title = 'Nothing here yet', description = 'There is nothing to show right now.', action }) {
  return (
    <div className="card p-10 text-center">
      <div className="mx-auto h-12 w-12 rounded-2xl bg-accent-soft text-accent grid place-items-center font-extrabold">—</div>
      <h2 className="font-extrabold text-lg text-primary mt-4">{title}</h2>
      <p className="muted text-sm mt-2 max-w-md mx-auto">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
