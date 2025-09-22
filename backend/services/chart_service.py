from __future__ import annotations

import base64
from typing import Any, Dict

import plotly.graph_objects as go
from plotly.io import to_image

from services.forex_service import forex_service
from services.market_service import market_service


class ChartService:
    """Generación de gráficos financieros listos para exponer vía REST."""

    async def generate_price_chart(
        self,
        symbol: str,
        asset_type: str = "crypto",
        interval: str = "1h",
        limit: int = 120,
    ) -> Dict[str, Any]:
        asset_type = asset_type.lower()
        if asset_type == "forex":
            series = await forex_service.get_time_series(symbol, interval=interval, outputsize=limit)
            timestamps = [item["datetime"] for item in series]
            opens = [item["open"] for item in series]
            highs = [item["high"] for item in series]
            lows = [item["low"] for item in series]
            closes = [item["close"] for item in series]
        else:
            data = await market_service.get_binance_klines(symbol.upper(), interval, limit)
            if not data:
                raise RuntimeError("No se encontraron datos para el símbolo solicitado")
            timestamps = [item["time"] for item in data]
            opens = [item["open"] for item in data]
            highs = [item["high"] for item in data]
            lows = [item["low"] for item in data]
            closes = [item["close"] for item in data]

        figure = go.Figure(
            data=[
                go.Candlestick(
                    x=timestamps,
                    open=opens,
                    high=highs,
                    low=lows,
                    close=closes,
                    name=symbol.upper(),
                )
            ]
        )
        figure.update_layout(
            title=f"{symbol.upper()} ({asset_type})",
            xaxis_title="Tiempo",
            yaxis_title="Precio",
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
        )

        image_bytes: bytes = to_image(figure, format="png", scale=2)
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "symbol": symbol.upper(),
            "asset_type": asset_type,
            "interval": interval,
            "image_base64": encoded,
            "content_type": "image/png",
        }


chart_service = ChartService()
