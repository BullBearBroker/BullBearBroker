"use client";

import React from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, info: React.ErrorInfo) => void;
  resetKeys?: React.DependencyList;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (process.env.NODE_ENV !== "test") {
      console.error("ErrorBoundary captured an error", error, info);
    }
    this.props.onError?.(error, info);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.hasError) {
      const { resetKeys = [] } = this.props;
      const { resetKeys: prevResetKeys = [] } = prevProps;
      const hasResetKeyChanged =
        resetKeys.length !== prevResetKeys.length ||
        resetKeys.some((key, index) => !Object.is(key, prevResetKeys[index]));
      if (hasResetKeyChanged || prevProps.children !== this.props.children) {
        this.reset();
      }
    }
  }

  reset() {
    this.setState({ hasError: false });
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
          >
            Ha ocurrido un error inesperado. Intenta recargar esta sección.
          </div>
        )
      );
    }

    return this.props.children;
  }
}
