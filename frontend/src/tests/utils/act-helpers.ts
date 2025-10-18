import { act } from "@testing-library/react";

/** Espera a que se vacíen microtareas y timers (fake timers o reales). */
export async function flushPromisesAndTimers() {
  await act(async () => {
    await Promise.resolve(); // microtareas
    try {
      const jestApi = (globalThis as {
        jest?: {
          getTimerCount?: () => number;
          runOnlyPendingTimers?: () => void;
        };
      }).jest;
      if (jestApi?.getTimerCount && jestApi.getTimerCount() > 0) {
        jestApi.runOnlyPendingTimers?.();
      }
    } catch {
      /* noop */
    }
  });
}

/** Ejecuta una función (sync o async) dentro de act y hace flush al final. */
export async function withAct<T>(fn: () => T | Promise<T>): Promise<T> {
  let result!: T;
  await act(async () => {
    result = await fn();
  });
  await flushPromisesAndTimers();
  return result;
}
