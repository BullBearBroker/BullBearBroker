"use client";

import useSWR from "swr";
import { useMemo } from "react";
import { LineChart, Coins, Wallet } from "lucide-react";

import {
  MarketEntry,
  UserProfile,
  getMarkets
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const icons = {
  crypto: Coins,
  stocks: LineChart,
  forex: Wallet
};

interface MarketSidebarProps {
  token?: string;
  user: UserProfile;
  onLogout: () => void;
}

export function MarketSidebar({ token, user, onLogout }: MarketSidebarProps) {
  const marketTypes: Array<{ key: "crypto" | "stocks" | "forex"; label: string }> = useMemo(
    () => [
      { key: "crypto", label: "Cripto" },
      { key: "stocks", label: "Acciones" },
      { key: "forex", label: "Forex" }
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
          {marketTypes.map((market) => (
            <MarketSection key={market.key} type={market.key} label={market.label} token={token} />
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
  type: "crypto" | "stocks" | "forex";
  label: string;
  token?: string;
}

function MarketSection({ type, label, token }: MarketSectionProps) {
  const { data, error, isLoading } = useSWR<MarketEntry[]>(
    ["markets", type, token],
    () => getMarkets(type, token),
    {
      refreshInterval: 1000 * 30
    }
  );

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
        {isLoading && <p className="text-sm text-muted-foreground">Cargando datos...</p>}
        {error && (
          <p className="text-sm text-destructive">
            Error al cargar datos: {error.message}
          </p>
        )}
        <div className="space-y-2">
          {data?.slice(0, 5).map((item) => (
            <div key={item.symbol} className="flex items-center justify-between rounded-md bg-muted/40 p-2">
              <div>
                <p className="text-sm font-medium">{item.symbol}</p>
                {item.change_24h !== undefined && (
                  <p
                    className={`text-xs ${item.change_24h >= 0 ? "text-emerald-500" : "text-red-500"}`}
                  >
                    {item.change_24h >= 0 ? "+" : ""}
                    {item.change_24h?.toFixed?.(2) ?? item.change_24h}%
                  </p>
                )}
              </div>
              <p className="text-sm font-semibold">${item.price?.toLocaleString?.() ?? item.price}</p>
            </div>
          ))}
          {!isLoading && !error && !data?.length && (
            <p className="text-sm text-muted-foreground">
              No hay datos disponibles por el momento.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
