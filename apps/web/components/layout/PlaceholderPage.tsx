interface PlaceholderPageProps {
  title: string
  description?: string
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {description ? <p className="text-muted-foreground">{description}</p> : null}
      <div className="mt-6 rounded-lg border border-dashed border-border bg-card/70 p-12 text-center">
        <p className="text-sm text-muted-foreground">This page is coming soon.</p>
      </div>
    </div>
  )
}
