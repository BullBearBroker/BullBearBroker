"use client";

import { memo, useMemo } from "react";
import useSWR from "swr";
import { Newspaper } from "lucide-react";
import Link from "next/link";

import { listNews, NewsItem } from "@/lib/api";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { EmptyState } from "@/components/common/EmptyState";
import { Skeleton } from "@/components/common/Skeleton";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface NewsPanelProps {
  token?: string;
}

function NewsPanelContent({ token }: NewsPanelProps) {
  const { data, error, isLoading } = useSWR<NewsItem[]>(
    ["news", token],
    () => listNews(token)
  );

  const sortedNews = useMemo(() => {
    if (!data?.length) return [] as NewsItem[];
    return data
      .slice()
      .sort((a, b) => {
        const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
        const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
        return dateB - dateA;
      });
  }, [data]);

  return (
    <Card className="surface-card flex flex-col">
      <CardHeader className="space-y-2 pb-4">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
            <Newspaper className="h-5 w-5 text-primary" /> Noticias
          </CardTitle>
          <Badge variant="outline" className="flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium">
            <Newspaper className="h-3.5 w-3.5" /> Últimas
          </Badge>
        </div>
        <CardDescription>Descubre las señales más relevantes del mercado en tiempo real.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && (
          <div className="space-y-2" data-testid="news-loading">
            {[0, 1, 2].map((index) => (
              <div key={index} className="space-y-2 rounded-xl border border-border/40 bg-[hsl(var(--surface))] p-3">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))}
          </div>
        )}
        {error && (
          <EmptyState
            title="No se pudieron cargar las noticias"
            description={error instanceof Error ? error.message : "Intenta nuevamente más tarde."}
            icon={<Newspaper className="h-5 w-5" />}
          />
        )}
        {!error && !isLoading && sortedNews.length === 0 && (
          <EmptyState
            title="No hay noticias disponibles"
            description="Vuelve más tarde para descubrir las últimas novedades del mercado."
            icon={<Newspaper className="h-5 w-5" />}
          />
        )}
        {sortedNews.slice(0, 6).map((item) => (
          <article
            key={item.id}
            className="space-y-2 rounded-2xl border border-border/40 bg-[hsl(var(--surface))] p-4 transition-all duration-300 hover:border-border hover:bg-[hsl(var(--surface-hover))]"
          >
            <h3 className="text-sm font-medium text-card-foreground">{item.title}</h3>
            {item.summary && <p className="text-xs text-muted-foreground leading-relaxed">{item.summary}</p>}
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{item.source ?? "Fuente desconocida"}</span>
              {item.published_at && (
                <span>{new Date(item.published_at).toLocaleString("es-ES", { hour12: false })}</span>
              )}
            </div>
            <Link
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-primary transition-colors hover:text-primary/80"
            >
              Leer noticia
            </Link>
          </article>
        ))}
      </CardContent>
    </Card>
  );
}

function NewsPanelFallback() {
  return (
    <Card className="surface-card flex flex-col">
      <CardHeader className="space-y-2">
        <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
          <Newspaper className="h-5 w-5 text-primary" /> Noticias
        </CardTitle>
        <CardDescription>
          No se pudo cargar esta sección. Intenta nuevamente en unos instantes.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <EmptyState
          title="Ups, algo salió mal"
          description="Actualiza la página o vuelve más tarde para ver las noticias."
          icon={<Newspaper className="h-6 w-6" />}
        />
      </CardContent>
    </Card>
  );
}

const NewsPanelComponent = memo(function NewsPanel(props: NewsPanelProps) {
  return (
    <ErrorBoundary fallback={<NewsPanelFallback />} resetKeys={[props.token]}>
      <NewsPanelContent {...props} />
    </ErrorBoundary>
  );
});

export { NewsPanelComponent as NewsPanel };
export default NewsPanelComponent;
