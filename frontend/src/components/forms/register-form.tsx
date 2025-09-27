"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function RegisterForm() {
  const { registerUser } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [riskProfile, setRiskProfile] = useState<
    "conservador" | "moderado" | "agresivo"
  >("moderado");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const validate = () => {
    if (!name) return "El nombre es obligatorio";
    if (!email.match(/^[^@]+@[^@]+\.[^@]+$/))
      return "Debe ingresar un correo válido";
    if (password.length < 6)
      return "La contraseña debe tener al menos 6 caracteres";
    if (password !== confirmPassword) return "Las contraseñas no coinciden";
    return null;
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await registerUser(email, password, name || undefined, riskProfile);
      router.push("/");
    } catch (err) {
      console.error(err);
      setError(
        err instanceof Error ? err.message : "No se pudo crear la cuenta"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="name" className="block text-sm font-medium">
          Nombre
        </label>
        <Input
          id="name"
          placeholder="Nombre"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>

      <div>
        <label htmlFor="email" className="block text-sm font-medium">
          Correo electrónico
        </label>
        <Input
          id="email"
          type="email"
          placeholder="Correo electrónico"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium">
          Contraseña
        </label>
        <Input
          id="password"
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>

      <div>
        <label htmlFor="confirmPassword" className="block text-sm font-medium">
          Confirmar contraseña
        </label>
        <Input
          id="confirmPassword"
          type="password"
          placeholder="Confirmar contraseña"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
      </div>

      <div>
        <label htmlFor="riskProfile" className="block text-sm font-medium">
          Perfil de riesgo
        </label>
        <select
          id="riskProfile"
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          value={riskProfile}
          onChange={(event) =>
            setRiskProfile(
              event.target.value as "conservador" | "moderado" | "agresivo"
            )
          }
        >
          <option value="conservador">Conservador</option>
          <option value="moderado">Moderado</option>
          <option value="agresivo">Agresivo</option>
        </select>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? "Creando cuenta..." : "Registrarse"}
      </Button>
    </form>
  );
}
