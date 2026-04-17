# Changelog

Todas as mudanças notáveis deste projeto estão documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [1.2.0] — 2026-04-17

### Adicionado
- Módulo de Auditoria de Saúde (Health Audit) com score visual por cliente
- Módulo de Alertas automáticos por thresholds de performance
- Módulo de Prospecção com diagnóstico comercial via IA
- Relatório Executivo gerado por IA com análise semanal consolidada
- Dashboard público compartilhável por cliente
- Suporte a múltiplos usuários com convite por código

### Melhorado
- API v2 corrigida com endpoints padronizados
- Sincronização RD Station Marketing + CRM unificada
- Frontend React SPA totalmente refatorado
- Análise de Landing Pages com SEO/GEO via IA
- Flow Studio com mapa de etapas acionáveis

### Corrigido
- Bug no callback OAuth quando token expirado
- Erro de parse de leads sem campo `email`
- Problema de CORS em produção no Render

---

## [1.1.0] — 2026-03-10

### Adicionado
- Integração com RD Station CRM (OAuth separado)
- Geração de emails personalizados com Groq (LLaMA 3.3 70B)
- Geração de fluxos de automação estruturados
- Módulo de Segmentações e Workflows

### Melhorado
- Health Score com cálculo ponderado por módulos
- Dashboard da agência com KPIs consolidados

---

## [1.0.0] — 2026-02-01

### Lançamento inicial
- Autenticação JWT com bcrypt
- OAuth RD Station Marketing
- CRUD de clientes
- Sincronização básica de dados
- Dashboard inicial
