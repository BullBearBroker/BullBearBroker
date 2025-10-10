"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { HttpError } from "@/lib/api";
import { authMessages } from "@/lib/i18n/auth";
import { trackEvent } from "@/lib/analytics";

interface FieldErrors {
  email?: string;
  password?: string;
}

function validateEmail(email: string) {
  const emailPattern = /^(?:[\w!#$%&'*+/=?`{|}~^.-]+)@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$/;
  return emailPattern.test(email.trim());
}

export default function LoginForm() {
  const router = useRouter();
  const { loginUser } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [rateLimitUntil, setRateLimitUntil] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const lastSubmitRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const lastRateLimitMarker = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!rateLimitUntil) {
      setRemainingSeconds(0);
      return;
    }

    const updateCountdown = () => {
      const diff = Math.ceil((rateLimitUntil - Date.now()) / 1000);
      if (diff <= 0) {
        setRateLimitUntil(null);
        setRemainingSeconds(0);
      } else {
        setRemainingSeconds(diff);
      }
    };

    updateCountdown();
    const interval = window.setInterval(updateCountdown, 1000);
    return () => window.clearInterval(interval);
  }, [rateLimitUntil]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (rateLimitUntil && rateLimitUntil > Date.now()) {
      return;
    }

    const now = Date.now();
    if (now - lastSubmitRef.current < 1000) {
      return;
    }

    const fieldErrors: FieldErrors = {};
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();

    if (!validateEmail(trimmedEmail)) {
      fieldErrors.email = authMessages.validation.email;
    }

    if (trimmedPassword.length < 6) {
      fieldErrors.password = authMessages.validation.password;
    }

    setErrors(fieldErrors);

    if (Object.keys(fieldErrors).length > 0) {
      return;
    }

    lastSubmitRef.current = now;
    setFormError(null);
    setSubmitting(true);

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      await loginUser(trimmedEmail, trimmedPassword, { signal: controller.signal });
      controllerRef.current = null;
      router.push("/");
    } catch (error) {
      controllerRef.current = null;
      if (
        error &&
        typeof error === "object" &&
        "name" in error &&
        (error as { name?: string }).name === "AbortError"
      ) {
        return;
      }
      if (error instanceof HttpError) {
        if (error.status === 429) {
          const seconds = Math.max(1, Math.round((error.retryAfter ?? remainingSeconds) || 60));
          const nextUntil = Date.now() + seconds * 1000;
          setRateLimitUntil(nextUntil);
          setRemainingSeconds(seconds);
          setFormError(authMessages.errors.rateLimited({ seconds }));
          if (lastRateLimitMarker.current !== nextUntil) {
            trackEvent("login_rate_limited_ui", {
              reason: "http_429",
              retry_after_seconds: seconds,
            });
            lastRateLimitMarker.current = nextUntil;
          }
          return;
        }
        if (error.status === 401) {
          setFormError(authMessages.errors.invalidCredentials);
          return;
        }
        setFormError(error.message || authMessages.errors.generic);
        return;
      }
      const message =
        error instanceof Error && error.message ? error.message : authMessages.errors.generic;
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit} noValidate>
      <div className="space-y-2">
        <Label htmlFor="email">{authMessages.labels.email}</Label>
        <Input
          id="email"
          placeholder={authMessages.placeholders.email}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => {
            const nextValue = event.target.value;
            setEmail(nextValue);
            setErrors((prev) => {
              if (!prev.email) {
                return prev;
              }
              const nextErrors = { ...prev };
              delete nextErrors.email;
              return nextErrors;
            });
            if (formError) {
              setFormError(null);
            }
          }}
          disabled={submitting || remainingSeconds > 0}
          aria-invalid={errors.email ? "true" : "false"}
          aria-describedby={errors.email ? "email-error" : undefined}
        />
        {errors.email ? (
          <p id="email-error" className="text-sm text-destructive">
            {errors.email}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">{authMessages.labels.password}</Label>
        <Input
          id="password"
          placeholder={authMessages.placeholders.password}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => {
            const nextValue = event.target.value;
            setPassword(nextValue);
            setErrors((prev) => {
              if (!prev.password) {
                return prev;
              }
              const nextErrors = { ...prev };
              delete nextErrors.password;
              return nextErrors;
            });
            if (formError) {
              setFormError(null);
            }
          }}
          disabled={submitting || remainingSeconds > 0}
          aria-invalid={errors.password ? "true" : "false"}
          aria-describedby={errors.password ? "password-error" : undefined}
        />
        {errors.password ? (
          <p id="password-error" className="text-sm text-destructive">
            {errors.password}
          </p>
        ) : null}
      </div>

      {formError ? (
        <div className="rounded-md bg-destructive/15 px-3 py-2 text-sm text-destructive">
          {formError}
        </div>
      ) : null}

      <Button type="submit" className="w-full" disabled={submitting || remainingSeconds > 0}>
        {submitting
          ? authMessages.actions.submitting
          : remainingSeconds > 0
            ? authMessages.errors.rateLimited({ seconds: remainingSeconds })
            : authMessages.actions.submit}
      </Button>
    </form>
  );
}
