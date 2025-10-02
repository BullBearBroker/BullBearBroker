export const authMessages = {
  labels: {
    email: "Correo electrónico",
    password: "Contraseña",
  },
  placeholders: {
    email: "Correo electrónico",
    password: "Contraseña",
  },
  actions: {
    submit: "Iniciar Sesión",
    submitting: "Iniciando...",
  },
  validation: {
    email: "Debe ingresar un correo válido",
    password: "La contraseña debe tener al menos 6 caracteres",
  },
  errors: {
    generic: "Error al iniciar sesión",
    invalidCredentials: "Credenciales inválidas",
    rateLimited: ({ seconds }: { seconds: number }) =>
      `Demasiados intentos. Inténtalo en ~${seconds} s`,
  },
};

export type AuthRateLimitMessageParams = Parameters<
  typeof authMessages.errors.rateLimited
>[0];
