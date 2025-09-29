"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface FieldErrors {
  name?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

type RiskProfile = "conservador" | "moderado" | "agresivo";

function validateEmail(email: string) {
  const emailPattern = /^(?:[\w!#$%&'*+/=?`{|}~^.-]+)@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$/;
  return emailPattern.test(email.trim());
}

export default function RegisterForm() {
  const router = useRouter();
  const { registerUser } = useAuth();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("moderado");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const riskOptions = useMemo(
    () => [
      { value: "conservador", label: "Conservador" },
      { value: "moderado", label: "Moderado" },
      { value: "agresivo", label: "Agresivo" },
    ],
    []
  );

  const clearFieldError = (field: keyof FieldErrors) => {
    setErrors((prev) => {
      if (!prev[field]) {
        return prev;
      }
      const nextErrors = { ...prev };
      delete nextErrors[field];
      return nextErrors;
    });
    if (formError) {
      setFormError(null);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const fieldErrors: FieldErrors = {};

    const trimmedName = name.trim();
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();
    const trimmedConfirm = confirmPassword.trim();

    if (!trimmedName) {
      fieldErrors.name = "El nombre es obligatorio";
    }

    if (!trimmedEmail) {
      fieldErrors.email = "El correo es obligatorio";
    } else if (!validateEmail(trimmedEmail)) {
      fieldErrors.email = "Debe ingresar un correo válido";
    }

    if (!trimmedPassword) {
      fieldErrors.password = "La contraseña es obligatoria";
    } else if (trimmedPassword.length < 6) {
      fieldErrors.password = "La contraseña debe tener al menos 6 caracteres";
    }

    if (!trimmedConfirm) {
      fieldErrors.confirmPassword = "Debe confirmar la contraseña";
    } else if (trimmedPassword && trimmedPassword !== trimmedConfirm) {
      fieldErrors.confirmPassword = "Las contraseñas no coinciden";
    }

    setErrors(fieldErrors);

    if (Object.keys(fieldErrors).length > 0) {
      return;
    }

    setFormError(null);
    setSubmitting(true);

    try {
      await registerUser(trimmedEmail, trimmedPassword, trimmedName, riskProfile);
      router.push("/");
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Error al registrar la cuenta";
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit} noValidate>
      <div className="space-y-2">
        <Label htmlFor="name">Nombre</Label>
        <Input
          id="name"
          placeholder="Nombre"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            clearFieldError("name");
          }}
          autoComplete="name"
          aria-invalid={errors.name ? "true" : "false"}
          aria-describedby={errors.name ? "name-error" : undefined}
        />
        {errors.name ? (
          <p id="name-error" className="text-sm text-destructive">
            {errors.name}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Correo electrónico</Label>
        <Input
          id="email"
          type="email"
          placeholder="Correo electrónico"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            clearFieldError("email");
          }}
          autoComplete="email"
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
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            clearFieldError("password");
            if (confirmPassword) {
              clearFieldError("confirmPassword");
            }
          }}
          autoComplete="new-password"
          aria-invalid={errors.password ? "true" : "false"}
          aria-describedby={errors.password ? "password-error" : undefined}
        />
        {errors.password ? (
          <p id="password-error" className="text-sm text-destructive">
            {errors.password}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirmPassword">Confirmar contraseña</Label>
        <Input
          id="confirmPassword"
          type="password"
          placeholder="Confirmar contraseña"
          value={confirmPassword}
          onChange={(event) => {
            setConfirmPassword(event.target.value);
            clearFieldError("confirmPassword");
          }}
          autoComplete="new-password"
          aria-invalid={errors.confirmPassword ? "true" : "false"}
          aria-describedby={
            errors.confirmPassword ? "confirmPassword-error" : undefined
          }
        />
        {errors.confirmPassword ? (
          <p id="confirmPassword-error" className="text-sm text-destructive">
            {errors.confirmPassword}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="riskProfile">Perfil de riesgo</Label>
        <select
          id="riskProfile"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          value={riskProfile}
          onChange={(event) => {
            setRiskProfile(event.target.value as RiskProfile);
          }}
        >
          {riskOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {formError ? (
        <div className="rounded-md bg-destructive/15 px-3 py-2 text-sm text-destructive">
          {formError}
        </div>
      ) : null}

      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Registrando..." : "Registrarse"}
      </Button>
    </form>
  );
}
