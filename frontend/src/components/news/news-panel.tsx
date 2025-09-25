"use client";

import useSWR from "swr";
import { Newspaper } from "lucide-react";
import Link from "next/link";

import { listNews, NewsItem } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface NewsPanelProps {
  token?: string;
}

export function NewsPanel({ token }: NewsPanelProps) {
  const { data, error, isLoading } = useSWR<NewsItem[]>(
    ["news", token],
    () => listNews(token)
  );

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
        {isLoading && <p className="text-sm text-muted-foreground">Cargando noticias...</p>}
        {error && (
          <p className="text-sm text-destructive">
            No se pudieron cargar las noticias: {error.message}
          </p>
        )}
        {!isLoading && !error && !data?.length && (
          <p className="text-sm text-muted-foreground">
            No hay noticias disponibles en este momento.
          </p>
        )}
        {data?.slice(0, 6).map((item) => (
          <article key={item.id} className="space-y-1 rounded-lg border p-3">
            <h3 className="text-sm font-semibold">{item.title}</h3>
            {item.summary && <p className="text-xs text-muted-foreground">{item.summary}</p>}
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{item.source ?? "Fuente desconocida"}</span>
              {item.published_at && <span>{new Date(item.published_at).toLocaleString()}</span>}
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
