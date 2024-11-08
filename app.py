import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
from dotenv import load_dotenv
import os

load_dotenv()

# Telegram Bot API Token и учетные данные
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_KEY")
LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")
LOGIN_FLAG = True
refresh_token = ""

def api_login(context: ContextTypes.DEFAULT_TYPE):
    global LOGIN_FLAG, refresh_token
    if LOGIN_FLAG:
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }
        json_data = {
            'login': LOGIN,
            'password': PASSWORD,
        }
        response = requests.post('https://ipeye.ru/api/rest/users/login', headers=headers, json=json_data)
        if response.status_code == 200:
            LOGIN_FLAG = False
            refresh_token = response.json()['message']['refresh_token']
            return response.json()['message']['access_token']
        else:
            context.application.create_task(notify_invalid_response(context, f"Ошибка: Не удалось получить токен авторизации. {response.status_code}"))
            return None
    else:
        json_data = {
            "refresh_token": refresh_token
        }
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }
        response = requests.post('https://ipeye.ru/api/rest/users/refresh', headers=headers, json=json_data)
        if response.status_code == 200:
            refresh_token = response.json()['message']['refresh_token']
            return response.json()['message']['access_token']
        else:
            context.application.create_task(notify_invalid_response(context, f"Ошибка: Не удалось обновить токен авторизации. {response.status_code}"))
            return None

async def notify_invalid_response(context: ContextTypes.DEFAULT_TYPE, message: str = "Ошибка: Не удалось получить данные от API. Проверьте соединение или повторите попытку позже."):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=message
    )

def make_api_request(context: ContextTypes.DEFAULT_TYPE):
    access_token = api_login(context)
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    response = requests.get('https://ipeye.ru/api/rest/devices', headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        context.application.create_task(notify_invalid_response(context, "Ошибка: Не удалось получить данные от API."))
        return None

async def periodic_api_check(context: ContextTypes.DEFAULT_TYPE):
    flag = True
    stores = make_api_request(context)
    if stores and stores.get('status') == True:
        for device in stores['message']:
            if device['status'] == False:
                flag = False
                await context.bot.send_message(
                    chat_id=context.job.chat_id,
                    text=f"Магазин {device['name']} камера не доступна."
                )
    if stores is None:
        await notify_invalid_response(context)
    else:
        if flag:
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text="Данные успешно получены от API. Вы можете запросить список магазинов командой /get_stores."
            )

async def get_stores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stores = make_api_request(context)
    stores_list = ""
    if stores and stores.get('status') == True:
        for device in stores['message']:
            if device['status'] == False:
                stores_list += f"Магазин {device['name']} камера не доступна.\n"
    else:
        stores_list = "Ошибка: Не удалось получить данные от API. Проверьте соединение или повторите попытку позже."
    await update.message.reply_text(f"Список магазинов:\n{stores_list}")

async def start_periodic_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job = context.job_queue.run_repeating(periodic_api_check, interval=600, first=0, chat_id=update.effective_chat.id)
    context.user_data["job"] = job
    await update.message.reply_text("Периодический запрос к API начат. Каждые 10 минут будет проверка.")

def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .job_queue(JobQueue())
        .build()
    )
    
    app.add_handler(CommandHandler("get_stores", get_stores))
    app.add_handler(CommandHandler("start_check", start_periodic_check))

    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
