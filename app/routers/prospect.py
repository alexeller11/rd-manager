from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def prospect(data: dict):
    return {
        "diagnostico": "Empresa não utiliza automações",
        "oportunidade": "Implantar funil de nutrição",
        "potencial": "R$ 5.000/mês"
    }
