// QA: Frontend env validator – fails fast in CI but prints friendly hints
const REQUIRED = [
  "NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_VAPID_PUBLIC_KEY",
];

const missing = REQUIRED.filter((k) => !process.env[k]);

if (missing.length) {
  console.error("❌ Faltan variables de entorno en Frontend:", missing);
  console.error(
    "Sugerencia: copia frontend/.env.example a frontend/.env.local y completa valores.",
  );
  process.exit(1);
} else {
  console.log("✅ Frontend env ok");
}
