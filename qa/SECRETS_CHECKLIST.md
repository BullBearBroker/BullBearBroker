# QA: Secrets Checklist

1. Confirm `backend/.env` is up to date and contains the authoritative credentials.
2. Sync runtime files:
   - `cp backend/.env backend/.env.local`
   - `cp frontend/.env.example frontend/.env.local` and fill only `NEXT_PUBLIC_*` keys.
3. Run the validators:
   - `make env-validate-backend`
   - `make env-validate-frontend`
4. Execute `make secrets-scan` and review `qa/SECRETS_REPORT.md` for potential leaks.
5. Inspect git status to ensure no `.env*` files or secrets appear in staged changes.
6. Before release, rotate any credentials exposed during QA and update vault/storage accordingly.
