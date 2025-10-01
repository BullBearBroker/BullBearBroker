"use client";

import useSWR from "swr";
import { Newspaper } from "lucide-react";
import Link from "next/link";

import { listNews, NewsItem } from "@/lib/api";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { EmptyState } from "@/components/common/EmptyState";
import { Skeleton } from "@/components/common/Skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface NewsPanelProps {
  token?: string;
}

function NewsPanelContent({ token }: NewsPanelProps) {
  const { data, error, isLoading } = useSWR<NewsItem[]>(
    ["news", token],
    () => listNews(token)
  );

  const sortedNews = data
    ?.slice()
    .sort((a, b) => {
      const dateA = a.published_at ? new Date(a.published_at).getTime() : 0;
      const dateB = b.published_at ? new Date(b.published_at).getTime() : 0;
      return dateB - dateA;
    });

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-lg font-medium">Noticias</CardTitle>
        <Badge variant="secondary" className="flex items-center gap-1">
          <Newspaper className="h-3.5 w-3.5" />
          Últimas
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && (
          <div className="space-y-2" data-testid="news-loading">
            {[0, 1, 2].map((index) => (
              <div key={index} className="space-y-2 rounded-lg border p-3">
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
        {!error && !isLoading && (!sortedNews || sortedNews.length === 0) && (
          <EmptyState
            title="No hay noticias disponibles"
            description="Vuelve más tarde para descubrir las últimas novedades del mercado."
            icon={<Newspaper className="h-5 w-5" />}
          />
        )}
        {sortedNews?.slice(0, 6).map((item) => (
          <article key={item.id} className="space-y-1 rounded-lg border p-3">
            <h3 className="text-sm font-semibold">{item.title}</h3>
            {item.summary && <p className="text-xs text-muted-foreground">{item.summary}</p>}
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
              className="text-xs font-medium text-primary hover:underline"
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
    <Card className="flex flex-col">
      <CardHeader className="space-y-1">
        <CardTitle className="text-lg font-medium">Noticias</CardTitle>
        <p className="text-sm text-muted-foreground">
          No se pudo cargar esta sección. Intenta nuevamente en unos instantes.
        </p>
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

export function NewsPanel(props: NewsPanelProps) {
  return (
    <ErrorBoundary fallback={<NewsPanelFallback />} resetKeys={[props.token]}>
      <NewsPanelContent {...props} />
    </ErrorBoundary>
  );
}
