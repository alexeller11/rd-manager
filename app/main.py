You reached the start of the range
Mar 28, 2026, 7:45 PM
Starting Container
(node:14) Warning: SECURITY WARNING: The SSL modes 'prefer', 'require', and 'verify-ca' are treated as aliases for 'verify-full'.
In the next major version (pg-connection-string v3.0.0 and pg v9.0.0), these modes will adopt standard libpq semantics, which have weaker security guarantees.
To prepare for this change:
- If you want the current behavior, explicitly use 'sslmode=verify-full'
- If you want libpq compatibility now, use 'uselibpqcompat=true&sslmode=require'
See https://www.postgresql.org/docs/current/libpq-ssl.html for libpq SSL mode definitions.
(Use `node --trace-warnings ...` to show where the warning was created)
> meta-ads-analyzer@2.0.0 start
> node server.js
✅ Servidor rodando na porta 7860
✅ Database schema ready (Neon)
Erro salvar DB: value too long for type character varying(32)
