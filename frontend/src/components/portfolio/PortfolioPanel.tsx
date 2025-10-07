"use client";

import { type ChangeEvent, useCallback, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { BriefcaseBusiness, PlusCircle, Trash2 } from "lucide-react";

import {
  PortfolioItem,
  PortfolioSummary,
  createPortfolioItem,
  deletePortfolioItem,
  exportPortfolioCsv,
  importPortfolioCsv,
  listPortfolio,
} from "@/lib/api";
import { getFeatureFlag } from "@/lib/featureFlags";
import { cn } from "@/lib/utils";
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
  const csvEnabled = useMemo(() => getFeatureFlag("portfolio-csv"), []);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [csvFeedback, setCsvFeedback] = useState<
    | {
        variant: "success" | "error" | "warning";
        message: string;
        details?: string[];
      }
    | null
  >(null);
  const [exporting, setExporting] = useState(false);
  const [importingCsv, setImportingCsv] = useState(false);

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

  const handleExportCsv = useCallback(async () => {
    if (!token) return;
    setCsvFeedback(null);
    setExporting(true);
    try {
      const csv = await exportPortfolioCsv(token);
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "portfolio.csv";
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
      setCsvFeedback({
        variant: "success",
        message: "Exportación completada. Revisa tu archivo \"portfolio.csv\".",
      });
    } catch (err) {
      setCsvFeedback({
        variant: "error",
        message:
          err instanceof Error
            ? err.message
            : "No se pudo exportar el portafolio.",
      });
    } finally {
      setExporting(false);
    }
  }, [token]);

  const handleImportTrigger = useCallback(() => {
    if (!token) return;
    fileInputRef.current?.click();
  }, [token]);

  const handleImportFile = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      if (!token) return;
      const file = event.target.files?.[0];
      if (!file) return;

      setCsvFeedback(null);
      setImportingCsv(true);
      try {
        const result = await importPortfolioCsv(token, file);
        const errorMessages = (result.errors ?? []).map(
          (error) => `Fila ${error.row}: ${error.message}`
        );
        const baseMessage = `Se importaron ${result.created} activos.`;
        setCsvFeedback({
          variant: errorMessages.length ? "warning" : "success",
          message:
            errorMessages.length > 0
              ? `${baseMessage} ${errorMessages.length} filas no se procesaron.`
              : baseMessage,
          details: errorMessages,
        });
        await mutate();
      } catch (err) {
        setCsvFeedback({
          variant: "error",
          message:
            err instanceof Error
              ? err.message
              : "No se pudo importar el CSV.",
        });
      } finally {
        setImportingCsv(false);
        event.target.value = "";
      }
    },
    [mutate, token]
  );

  const handleDownloadTemplate = useCallback(() => {
    const template = "symbol,amount\nAAPL,10\nBTCUSDT,0.5\n";
    const blob = new Blob([template], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "portfolio_template.csv";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, []);

  return (
    <Card className="surface-card flex flex-col">
      <CardHeader className="flex flex-col gap-3 pb-4">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
            <BriefcaseBusiness className="h-5 w-5 text-primary" /> Mi portafolio
          </CardTitle>
          <Badge variant="outline" className="rounded-full px-3 py-1 text-xs font-medium">
            Total: {formattedTotal}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Administra tus posiciones y consulta su valoración estimada.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {csvEnabled && (
          <div className="space-y-3 rounded-2xl border border-dashed border-border/50 bg-[hsl(var(--surface))] p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-card-foreground">Importar / exportar cartera</p>
                <p className="text-xs text-muted-foreground">
                  Trabaja con archivos CSV usando las columnas <code>symbol</code> y <code>amount</code>.
                </p>
              </div>
              <div className="flex flex-col gap-2 md:flex-row">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={handleExportCsv}
                  disabled={!token || exporting}
                >
                  {exporting ? "Exportando..." : "Exportar CSV"}
                </Button>
                <Button
                  type="button"
                  onClick={handleImportTrigger}
                  disabled={!token || importingCsv}
                >
                  {importingCsv ? "Importando..." : "Importar CSV"}
                </Button>
                <Button type="button" variant="ghost" onClick={handleDownloadTemplate}>
                  Plantilla
                </Button>
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={handleImportFile}
            />
            {csvFeedback && (
              <div
                role="status"
                className={cn(
                  "rounded-xl border p-3 text-sm",
                  csvFeedback.variant === "error" && "border-destructive/40 text-destructive",
                  csvFeedback.variant === "warning" && "border-warning/40 text-warning",
                  csvFeedback.variant === "success" && "border-success/40 text-success"
                )}
              >
                <p>{csvFeedback.message}</p>
                {csvFeedback.details && csvFeedback.details.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-4">
                    {csvFeedback.details.map((detail) => (
                      <li key={detail}>{detail}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}

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
                className="flex flex-col gap-3 rounded-2xl border border-border/40 bg-[hsl(var(--surface))] p-4 transition-all duration-300 hover:border-border hover:bg-[hsl(var(--surface-hover))] md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-card-foreground">{item.symbol}</p>
                  <p className="text-xs text-muted-foreground">
                    Cantidad: {item.amount.toLocaleString("en-US")}
                  </p>
                  <p className="text-xs text-muted-foreground">Precio: {priceLabel}</p>
                </div>
                <div className="flex items-center gap-3">
                  <p className="text-sm font-semibold text-card-foreground">{valueLabel}</p>
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
