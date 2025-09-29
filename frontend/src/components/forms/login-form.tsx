"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const fieldErrors: FieldErrors = {};
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();

    if (!validateEmail(trimmedEmail)) {
      fieldErrors.email = "Debe ingresar un correo válido";
    }

    if (trimmedPassword.length < 6) {
      fieldErrors.password = "La contraseña debe tener al menos 6 caracteres";
    }

    setErrors(fieldErrors);

    if (Object.keys(fieldErrors).length > 0) {
      return;
    }

    setFormError(null);
    setSubmitting(true);

    try {
      await loginUser(trimmedEmail, trimmedPassword);
      router.push("/");
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Error al iniciar sesión";
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit} noValidate>
      <div className="space-y-2">
        <Label htmlFor="email">Correo electrónico</Label>
        <Input
          id="email"
          placeholder="Correo electrónico"
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
        <Label htmlFor="password">Contraseña</Label>
        <Input
          id="password"
          placeholder="Contraseña"
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

      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Iniciando..." : "Iniciar Sesión"}
      </Button>
    </form>
  );
}
