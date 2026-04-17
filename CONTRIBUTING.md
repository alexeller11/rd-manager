# Contribuindo com o RD Manager IA

Obrigado pelo interesse em contribuir! Siga as diretrizes abaixo.

## Como contribuir

1. **Fork** este repositório
2. Crie uma branch com nome descritivo: `git checkout -b feat/nome-da-feature`
3. Faça suas alterações com commits claros
4. Abra um **Pull Request** descrevendo o que foi feito

## Padrão de commits

Use o padrão [Conventional Commits](https://www.conventionalcommits.org/pt-BR/):

```
feat: adiciona novo módulo de campanhas
fix: corrige bug no callback OAuth
chore: atualiza dependências
docs: melhora README
refactor: reorganiza serviços de IA
```

## Estrutura do projeto

```
app/
├── routers/       # Endpoints REST (um arquivo por domínio)
├── services/      # Lógica de negócio
├── models/        # Modelos de banco de dados
├── schemas/       # Schemas Pydantic (validação)
├── templates/     # Frontend React SPA
└── tests/         # Testes automatizados
```

## Rodando localmente

Veja o `README.md` para instruções completas de instalação e execução.

## Testes

Sempre rode os testes antes de abrir um PR:

```bash
pytest app/tests/ -v
```

## Dúvidas?

Abra uma [Issue](https://github.com/alexeller11/rd-manager/issues) com a tag `question`.
