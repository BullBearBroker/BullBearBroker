import React from "react";

type ResponsiveContainerProps = {
  width?: number | string;
  height?: number | string;
  children?: React.ReactNode | ((dimensions: { width: number; height: number }) => React.ReactNode);
};

const DEFAULT_WIDTH = 800;
const DEFAULT_HEIGHT = 400;

const createMockComponent = (name: string) => {
  const MockComponent: React.FC<React.PropsWithChildren<{ className?: string; style?: React.CSSProperties }>> = ({
    children,
    className,
    style,
  }) => (
    <div data-recharts-mock={name} className={className} style={style}>
      {typeof children === "function" ? (children as () => React.ReactNode)() : children}
    </div>
  );
  MockComponent.displayName = `Mock${name}`;
  return MockComponent;
};

export const Area = createMockComponent("Area");
export const AreaChart = createMockComponent("AreaChart");
export const Bar = createMockComponent("Bar");
export const CartesianGrid = createMockComponent("CartesianGrid");
export const ComposedChart = createMockComponent("ComposedChart");
export const Legend = createMockComponent("Legend");
export const Line = createMockComponent("Line");
export const LineChart = createMockComponent("LineChart");
export const ReferenceLine = createMockComponent("ReferenceLine");
export const Tooltip = createMockComponent("Tooltip");
export const XAxis = createMockComponent("XAxis");
export const YAxis = createMockComponent("YAxis");

export const ResponsiveContainer: React.FC<ResponsiveContainerProps> = ({
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  children,
}) => {
  const numericWidth = typeof width === "number" ? width : DEFAULT_WIDTH;
  const numericHeight = typeof height === "number" ? height : DEFAULT_HEIGHT;

  const resolvedChildren =
    typeof children === "function"
      ? (children as (dimensions: { width: number; height: number }) => React.ReactNode)({
          width: numericWidth,
          height: numericHeight,
        })
      : children;

  const resolvedWidth = typeof width === "number" ? `${width}px` : width ?? "100%";
  const resolvedHeight = typeof height === "number" ? `${height}px` : height ?? `${DEFAULT_HEIGHT}px`;

  return (
    <div
      data-recharts-mock="ResponsiveContainer"
      style={{
        width: resolvedWidth,
        height: resolvedHeight,
        minWidth: resolvedWidth,
        minHeight: resolvedHeight,
      }}
    >
      {resolvedChildren}
    </div>
  );
};

export default {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
};
