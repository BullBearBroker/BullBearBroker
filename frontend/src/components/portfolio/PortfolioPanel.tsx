"use client";

import { useCallback, useMemo, useState } from "react";
import useSWR from "swr";
import { PlusCircle, Trash2 } from "lucide-react";

import {
  PortfolioItem,
  PortfolioSummary,
  createPortfolioItem,
  deletePortfolioItem,
  listPortfolio,
} from "@/lib/api";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { EmptyState } from "@/components/common/EmptyState";
import { Skeleton } from "@/components/common/Skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

interface PortfolioPanelProps {
  token?: string;
}

function PortfolioPanelContent({ token }: PortfolioPanelProps) {
  const { data, error, mutate, isLoading } = useSWR<PortfolioSummary>(
    token ? ["portfolio", token] : null,
    () => listPortfolio(token!)
  );

  const [symbol, setSymbol] = useState("");
  const [amount, setAmount] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const totalValue = data?.total_value ?? 0;
  const formattedTotal = useMemo(() => currencyFormatter.format(totalValue), [totalValue]);

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!token) return;

      const trimmedSymbol = symbol.trim();
      if (!trimmedSymbol) {
        setFormError("Debes indicar el símbolo del activo.");
        return;
      }

      if (amount.trim().length === 0) {
        setFormError("Debes indicar la cantidad del activo.");
        return;
      }

      const numericAmount = Number(amount);
      if (Number.isNaN(numericAmount) || numericAmount <= 0) {
        setFormError("La cantidad debe ser mayor que cero.");
        return;
      }

      setSubmitting(true);
      setFormError(null);
      try {
        await createPortfolioItem(token, {
          symbol: trimmedSymbol.toUpperCase(),
          amount: numericAmount,
        });
        setSymbol("");
        setAmount("");
        await mutate();
      } catch (err) {
        console.error(err);
        setFormError(
          err instanceof Error
            ? err.message
            : "No se pudo agregar el activo al portafolio."
        );
      } finally {
        setSubmitting(false);
      }
    },
    [amount, mutate, symbol, token]
  );

  const handleDelete = useCallback(
    async (item: PortfolioItem) => {
      if (!token) return;
      try {
        await deletePortfolioItem(token, String(item.id));
        await mutate();
      } catch (err) {
        console.error(err);
        setFormError(
          err instanceof Error
            ? err.message
            : "No se pudo eliminar el activo del portafolio."
        );
      }
    },
    [mutate, token]
  );

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <div>
          <CardTitle className="text-lg font-medium">Portafolio</CardTitle>
          <p className="text-sm text-muted-foreground">
            Administra tus posiciones y consulta su valoración estimada.
          </p>
        </div>
        <Badge variant="secondary">Total: {formattedTotal}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Input
              placeholder="Activo (ej. BTCUSDT, AAPL, EURUSD)"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              disabled={!token || submitting}
            />
            <Input
              placeholder="Cantidad"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              disabled={!token || submitting}
              inputMode="decimal"
            />
          </div>
          {formError && <p className="text-sm text-destructive">{formError}</p>}
          <Button type="submit" disabled={!token || submitting} className="w-full">
            <PlusCircle className="mr-2 h-4 w-4" />
            {submitting ? "Agregando..." : "Agregar activo"}
          </Button>
        </form>

        <div className="space-y-3">
          {isLoading && (
            <div className="space-y-2" data-testid="portfolio-loading">
              {[0, 1, 2].map((index) => (
                <Skeleton key={index} className="h-16 w-full" />
              ))}
            </div>
          )}
          {error && (
            <p className="text-sm text-destructive" role="alert">
              Error al cargar el portafolio: {error instanceof Error ? error.message : "Desconocido"}
            </p>
          )}
          {!isLoading && !error && (!data || data.items.length === 0) && (
            <EmptyState
              title="Tu portafolio está vacío"
              description="Agrega un activo para visualizar su valoración estimada."
              icon={<PlusCircle className="h-5 w-5" />}
            />
          )}

          {data?.items.map((item) => {
            const priceLabel =
              typeof item.price === "number"
                ? currencyFormatter.format(item.price)
                : "Sin datos";
            const valueLabel =
              typeof item.value === "number"
                ? currencyFormatter.format(item.value)
                : "-";

            return (
              <div
                key={item.id}
                className="flex flex-col gap-2 rounded-lg border p-3 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <p className="font-medium">{item.symbol}</p>
                  <p className="text-xs text-muted-foreground">
                    Cantidad: {item.amount.toLocaleString("en-US")}
                  </p>
                  <p className="text-xs text-muted-foreground">Precio: {priceLabel}</p>
                </div>
                <div className="flex items-center gap-3">
                  <p className="text-sm font-semibold">{valueLabel}</p>
                  <Button
                    type="button"
                    variant="destructive"
                    size="icon"
                    disabled={!token}
                    aria-label={`Eliminar ${item.symbol}`}
                    onClick={() => handleDelete(item)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function PortfolioPanelFallback() {
  return (
    <Card className="flex flex-col">
      <CardHeader className="space-y-1">
        <CardTitle className="text-lg font-medium">Portafolio</CardTitle>
        <p className="text-sm text-muted-foreground">
          No se pudo cargar esta sección. Intenta recargar la página.
        </p>
      </CardHeader>
      <CardContent>
        <EmptyState
          title="Ocurrió un problema al mostrar el portafolio"
          description="Actualiza la página o intenta nuevamente más tarde."
        />
      </CardContent>
    </Card>
  );
}

export function PortfolioPanel(props: PortfolioPanelProps) {
  return (
    <ErrorBoundary fallback={<PortfolioPanelFallback />} resetKeys={[props.token]}>
      <PortfolioPanelContent {...props} />
    </ErrorBoundary>
  );
}
