"use client";

import { ComponentType, ReactNode, createElement, forwardRef } from "react";

type MotionProps = Record<string, unknown> & { children?: ReactNode };

type MotionLikeComponent = ComponentType<MotionProps>;

type AnimatePresenceLikeProps = { children?: ReactNode } & Record<string, unknown>;

type AnimatePresenceLike = ComponentType<AnimatePresenceLikeProps>;

type FramerExports = {
  AnimatePresence?: AnimatePresenceLike;
  motion?: Record<string, MotionLikeComponent>;
};

const createMotionElement = (element: string) =>
  forwardRef<HTMLElement, MotionProps>(function MotionElement({ children, ...rest }, ref) {
    const {
      initial: _initial,
      animate: _animate,
      exit: _exit,
      transition: _transition,
      layout: _layout,
      whileHover: _whileHover,
      whileTap: _whileTap,
      ...domProps
    } = rest;

    const elementProps = { ...domProps, ref } as Record<string, unknown>;
    return createElement(element, elementProps, children as ReactNode);
  });

const createFallbackMotion = () => {
  const cache = new Map<PropertyKey, MotionLikeComponent>();

  return new Proxy(
    {},
    {
      get: (_target, element: PropertyKey) => {
        if (element === "__esModule") {
          return false;
        }

        const key = typeof element === "string" ? element : "div";

        if (!cache.has(key)) {
          cache.set(key, createMotionElement(key));
        }

        return cache.get(key) as MotionLikeComponent;
      },
    },
  ) as Record<string, MotionLikeComponent>;
};

const fallbackAnimatePresence: AnimatePresenceLike = ({ children }) => <>{children}</>;

const optionalRequire = (() => {
  try {
    // eslint-disable-next-line no-new-func
    return Function("return require")();
  } catch {
    return null;
  }
})();

function resolveFramerMotion(): Required<FramerExports> {
  if (optionalRequire) {
    try {
      const mod: FramerExports = optionalRequire("framer-motion");
      if (mod?.AnimatePresence && mod?.motion) {
        return {
          AnimatePresence: mod.AnimatePresence,
          motion: mod.motion,
        };
      }
    } catch {
      if (process.env.NODE_ENV === "development") {
        console.warn("framer-motion no está disponible, usando animaciones de reserva livianas.");
      }
    }
  }

  return {
    AnimatePresence: fallbackAnimatePresence,
    motion: createFallbackMotion(),
  };
}

const resolvedMotion = resolveFramerMotion();

export const AnimatePresence = resolvedMotion.AnimatePresence;
export const motion = resolvedMotion.motion;
