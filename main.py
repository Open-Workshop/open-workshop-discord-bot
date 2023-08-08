import json
import discord
import tools
from discord import app_commands
import requests
from datetime import timedelta
import matplotlib.pyplot as plt
from urllib.parse import urlparse
from urllib.parse import parse_qs
import io


SERVER_ADDRESS = 'https://43093.zetalink.ru:8000'
type_map = None


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        await tree.sync(guild=discord.Object(id=792572437292253224))
        print("Online")

client = MyClient(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)

@tree.command(name='statistics', guild=discord.Object(id=792572437292253224))
async def statistics(interaction: discord.Interaction):
    plt.clf()
    global type_map

    try:
        if not type_map:
            res = requests.get(url=SERVER_ADDRESS + "/statistics/info/type_map", headers={"Accept-Language": "ru, en"},
                               timeout=10)
            info = json.loads(res.content)
            type_map = info["result"]
    except:
        await interaction.response.send_message("При получении переводов возникла странная ошибка...")

    try:
        # Произвольные данные
        res = requests.get(url=SERVER_ADDRESS + "/statistics/hour", timeout=10)
        info = json.loads(res.content)

        output = await tools.graf(info, "date_time")
        for i in output[0].keys():
            plt.plot(output[0][i][0], output[0][i][1], label=type_map.get(i, "ERROR"))

        # Настройка внешнего вида графика
        plt.title("Статистика сегодня")
        plt.xlabel("Час")
        plt.ylabel("Кол-во обращений")
        plt.legend(fontsize='xx-small')
        # Задаем метки делений на оси x
        plt.xticks([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23])
        # Создание объекта для сохранения изображения в памяти
        buffer = io.BytesIO()
        # Сохранение графика в буфер
        plt.savefig(buffer, format='png')
        buffer.seek(0)

        # Отправка изображения через Telegram Bot API
        await interaction.response.send_message(file=buffer)
    except:
        await interaction.response.send_message("При получении статистики за день возникла странная ошибка...")

    try:
        plt.clf()
        # Произвольные данные
        res = requests.get(url=SERVER_ADDRESS + "/statistics/day", timeout=10)
        info = json.loads(res.content)

        output = await tools.graf(info, "date")

        shift = output[1][0].toordinal()
        for i in output[0].keys():
            plt.plot([x - shift for x in output[0][i][0]], output[0][i][1], label=type_map.get(i, "ERROR"))

        # Настройка внешнего вида графика
        plt.title("Статистика за 7 дней")
        plt.xlabel("День")
        plt.ylabel("Кол-во обращений")
        plt.legend(fontsize='xx-small')
        # Задаем метки делений на оси x
        start_value = 0
        end_value = len(output[1]) - 1
        step = 1

        numbers = list(range(start_value, end_value + 1, step))
        dates = [str(output[1][-1] - timedelta(days=end_value - i)).removesuffix(" 00:00:00").removeprefix("20") for i
                 in range(start_value, end_value + 1, step)]

        plt.xticks(numbers, dates)
        # Создание объекта для сохранения изображения в памяти
        buffer = io.BytesIO()
        # Сохранение графика в буфер
        plt.savefig(buffer, format='png')
        buffer.seek(0)

        # Отправка изображения через Telegram Bot API
        #await bot.send_photo(chat_id=message.chat.id, photo=buffer)
    except:
        await interaction.response.send_message("При получении статистики за 7 дней возникла странная ошибка...")

    try:
        res = requests.get(url=SERVER_ADDRESS + "/statistics/info/all", timeout=10)
        info = json.loads(res.content)
        await interaction.response.send_message(f"""
    Пользователям отправлено {info.get('mods_sent_count')} файлов.
    Сервис работает {await tools.format_seconds(seconds=info.get('statistics_days', 0), word="день")}.

    У {info.get('games', 0)} игр сохранено {info.get('mods', 0)} модов, {info.get('mods_dependencies', 0)} из которых имеют зависимости на другие моды.
    Сервису известно об {await tools.format_seconds(seconds=info.get('genres', 0), word="жанр")} игр и {await tools.format_seconds(seconds=info.get('mods_tags', 0), word="тег")} для модов.
            """)
    except:
        await interaction.response.send_message("При получении общей статистики возникла странная ошибка...")

@tree.command(name='project', guild=discord.Object(id=792572437292253224))
async def project(interaction: discord.Interaction):
    # TODO функция косой черты отправляющая информацию о проекте

    await interaction.response.send_message(f'Нет')

@tree.context_menu(name="Скачать мод", guild=discord.Object(id=792572437292253224))
async def download_context(interaction: discord.Interaction, _message: discord.Message):
    await interaction.response.send_message(f'Your favourite fruit seems to be')

@tree.command(name='download', guild=discord.Object(id=792572437292253224))
async def download(interaction: discord.Interaction, link:str):
    # TODO функция косой черты где передаем ссылку / id

    await interaction.response.send_message(f'{link}')


with open('key.json', 'r') as file:
    # Загружаем содержимое файла в переменную
    TOKEN = json.load(file)["key"]
client.run(TOKEN)