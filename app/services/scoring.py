import httpx
import os

RD_API = "https://api.rd.services"


async def get_headers():
    token = os.getenv("RD_ACCESS_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


async def fetch_leads():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{RD_API}/platform/contacts", headers=await get_headers())
        return r.json()


async def fetch_landing_pages():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{RD_API}/platform/landing_pages", headers=await get_headers())
        return r.json()


async def run_full_sync(client_id: int):
    leads = await fetch_leads()
    pages = await fetch_landing_pages()

    return {
        "ok": True,
        "summary": {
            "leads": len(leads.get("contacts", [])),
            "landing_pages": len(pages.get("items", []))
        }
    }
