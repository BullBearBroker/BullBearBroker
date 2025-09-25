"use client";

import useSWR from "swr";
import { useMemo } from "react";
import { LineChart, Coins, Wallet } from "lucide-react";

import { MarketQuote, UserProfile, getMarketQuote } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

type MarketType = "crypto" | "stock" | "forex";

const icons: Record<MarketType, typeof Coins> = {
  crypto: Coins,
  stock: LineChart,
  forex: Wallet
};

interface MarketSidebarProps {
  token?: string;
  user: UserProfile;
  onLogout: () => void;
}

interface MarketWatchConfig {
  id: string;
  type: MarketType;
  requestSymbol: string;
  displaySymbol: string;
  label: string;
}

const MARKET_WATCHLIST: MarketWatchConfig[] = [
  {
    id: "btc",
    type: "crypto",
    requestSymbol: "BTC",
    displaySymbol: "BTCUSDT",
    label: "Bitcoin"
  },
  {
    id: "aapl",
    type: "stock",
    requestSymbol: "AAPL",
    displaySymbol: "AAPL",
    label: "Apple Inc."
  },
  {
    id: "eurusd",
    type: "forex",
    requestSymbol: "EURUSD",
    displaySymbol: "EUR/USD",
    label: "Euro vs Dólar"
  }
];

export function MarketSidebar({ token, user, onLogout }: MarketSidebarProps) {
  const marketGroups = useMemo(
    () =>
      [
        {
          key: "crypto" as MarketType,
          label: "Cripto",
          items: MARKET_WATCHLIST.filter((item) => item.type === "crypto")
        },
        {
          key: "stock" as MarketType,
          label: "Acciones",
          items: MARKET_WATCHLIST.filter((item) => item.type === "stock")
        },
        {
          key: "forex" as MarketType,
          label: "Forex",
          items: MARKET_WATCHLIST.filter((item) => item.type === "forex")
        }
      ],
    []
  );

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <Card className="border-none bg-transparent shadow-none">
        <CardContent className="p-0">
          <h2 className="text-xl font-semibold">BullBearBroker</h2>
          <p className="text-sm text-muted-foreground">{user.email}</p>
        </CardContent>
      </Card>
      <ScrollArea className="flex-1">
        <div className="space-y-4 pr-2">
          {marketGroups.map((group) => (
            <MarketSection key={group.key} label={group.label} items={group.items} token={token} />
          ))}
        </div>
      </ScrollArea>
      <Separator />
      <Button variant="outline" onClick={onLogout}>
        Cerrar sesión
      </Button>
    </div>
  );
}

interface MarketSectionProps {
  label: string;
  items: MarketWatchConfig[];
  token?: string;
}

function MarketSection({ label, items, token }: MarketSectionProps) {
  const type = items[0]?.type ?? "crypto";
  const Icon = icons[type];

  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-primary" />
            <h3 className="font-medium">{label}</h3>
          </div>
          <Badge variant="secondary">Tiempo real</Badge>
        </div>
        <div className="space-y-2">
          {items.map((item) => (
            <MarketRow key={item.id} config={item} token={token} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

interface MarketRowProps {
  config: MarketWatchConfig;
  token?: string;
}

function MarketRow({ config, token }: MarketRowProps) {
  const { data, error, isLoading } = useSWR<MarketQuote>(
    ["market", config.type, config.requestSymbol, token],
    () => getMarketQuote(config.type, config.requestSymbol, token),
    {
      refreshInterval: 1000 * 30,
      revalidateOnFocus: false
    }
  );

  const dataType = (data?.type as MarketType | undefined) ?? config.type;

  const priceText = data?.price
    ? new Intl.NumberFormat("es-ES", {
        minimumFractionDigits: dataType === "forex" ? 4 : 2,
        maximumFractionDigits: dataType === "forex" ? 5 : 2
      }).format(data.price)
    : "--";

  const change = typeof data?.raw_change === "number" ? data.raw_change : null;
  const changeText = change !== null ? `${change > 0 ? "+" : ""}${change.toFixed(2)}%` : "--";
  const changeClass = change === null ? "text-muted-foreground" : change >= 0 ? "text-emerald-500" : "text-red-500";

  return (
    <div className="flex flex-col gap-2 rounded-md bg-muted/40 p-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">{config.displaySymbol}</p>
          <p className="text-xs text-muted-foreground">{config.label}</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold">{priceText}</p>
          <p className={`text-xs ${changeClass}`}>{changeText}</p>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        {error ? <span>Error</span> : isLoading ? <span>Actualizando...</span> : <span>{data?.source ?? ""}</span>}
        <Sparkline change={change ?? 0} positive={change !== null ? change >= 0 : undefined} loading={isLoading} />
      </div>
    </div>
  );
}

interface SparklineProps {
  change: number;
  positive?: boolean;
  loading?: boolean;
}

function Sparkline({ change, positive, loading }: SparklineProps) {
  if (loading) {
    return <span className="italic">...</span>;
  }

  const clamped = Number.isFinite(change) ? Math.max(Math.min(change, 15), -15) : 0;
  const baseline = 16;
  const slope = clamped * 0.6;
  const mid = baseline - slope / 2;
  const end = baseline - slope;
  const color = positive === undefined ? "currentColor" : positive ? "#10b981" : "#ef4444";

  return (
    <svg viewBox="0 0 100 32" className="h-6 w-16">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={`0,${baseline} 50,${mid.toFixed(2)} 100,${end.toFixed(2)}`}
      />
    </svg>
  );
}
