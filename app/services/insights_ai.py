def generate_insight(data):
    if data["leads"] < 50:
        return "Baixo volume de leads. Possível problema de tráfego ou conversão."

    if data["landing_pages"] == 0:
        return "Nenhuma landing page ativa. Grande oportunidade de captação."

    return "Operação saudável com oportunidades de escala."
