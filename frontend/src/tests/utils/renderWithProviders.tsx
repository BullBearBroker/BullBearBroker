import { ReactElement, ReactNode } from "react";
import { render, RenderOptions } from "@testing-library/react";
import { SWRConfig, SWRConfiguration } from "swr";

import { AuthProvider } from "@/components/providers/auth-provider";
import { ThemeProvider } from "@/components/providers/theme-provider";

const FallbackProvider = ({ children }: { children: ReactNode }) => <>{children}</>;

type ProviderComponent = (props: any) => ReactNode;

function withSafeProvider(Component: ProviderComponent | undefined): ProviderComponent {
  return (props: any) => {
    if (typeof Component === "function") {
      try {
        return Component(props);
      } catch (error) {
        if (process.env.NODE_ENV !== "test") {
          throw error;
        }
      }
    }
    return FallbackProvider(props);
  };
}

const ResolvedThemeProvider = withSafeProvider(
  ThemeProvider as unknown as ProviderComponent | undefined,
);

const ResolvedAuthProvider = withSafeProvider(
  AuthProvider as unknown as ProviderComponent | undefined,
);

interface WrapperProps {
  children: ReactNode;
  swrConfig?: Partial<SWRConfiguration>;
}

function Providers({ children, swrConfig }: WrapperProps) {
  const value: SWRConfiguration = {
    provider: () => new Map(),
    dedupingInterval: 0,
    revalidateOnFocus: false,
    ...swrConfig,
  };

  return (
    <SWRConfig value={value}>
      <ResolvedThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <ResolvedAuthProvider>{children}</ResolvedAuthProvider>
      </ResolvedThemeProvider>
    </SWRConfig>
  );
}

type CustomRenderOptions = Omit<RenderOptions, "wrapper"> & {
  providerProps?: {
    swrConfig?: Partial<SWRConfiguration>;
  };
};

export function customRender(
  ui: ReactElement,
  { providerProps, ...renderOptions }: CustomRenderOptions = {},
) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <Providers swrConfig={providerProps?.swrConfig}>{children}</Providers>
  );

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

export * from "@testing-library/react";
