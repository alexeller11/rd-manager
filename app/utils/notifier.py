import telegram

# Substitua com o token do seu bot e o ID do chat
TELEGRAM_BOT_TOKEN = "8696159303:AAH0LeUQL5PmL5IRGtj7NSA137Bt5b0sPXE"
TELEGRAM_CHAT_ID = 1174531081

async def send_telegram_message(message):
    try:
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        async with bot:
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        print("Mensagem enviada para o Telegram com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar mensagem para o Telegram: {e}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(send_telegram_message("Teste de mensagem do Telegram!"))