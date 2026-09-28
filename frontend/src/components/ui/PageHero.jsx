export default function PageHero({ eyebrow, title, subtitle, actions }) {
  return (
    <section className="bg-hero-mesh text-inverse">
      <div className="container-app py-10 lg:py-14">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
          <div className="max-w-3xl">
            {eyebrow && <p className="eyebrow text-inverse-muted">{eyebrow}</p>}
            <h1 className="page-heading text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight mt-2">{title}</h1>
            {subtitle && <p className="text-inverse-muted leading-7 mt-3 max-w-2xl">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap gap-3">{actions}</div>}
        </div>
      </div>
    </section>
  );
}
