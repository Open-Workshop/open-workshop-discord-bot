import json
import tools
import requests
import discord
from discord import app_commands, colour
from discord.ui import Button


SERVER_ADDRESS = 'https://43093.zetalink.ru:8000'


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
    try:
        res = requests.get(url=SERVER_ADDRESS + "/statistics/info/all", timeout=10)
        info = json.loads(res.content)

        embedVar = discord.Embed(title="Общая статистика", description=f"""
Пользователям отправлено {info.get('mods_sent_count')} файлов.
Сервис работает {await tools.format_seconds(seconds=info.get('statistics_days', 0), word="день")}.

У {info.get('games', 0)} игр сохранено {info.get('mods', 0)} модов, {info.get('mods_dependencies', 0)} из которых имеют зависимости на другие моды.
Сервису известно об {await tools.format_seconds(seconds=info.get('genres', 0), word="жанр")} игр и {await tools.format_seconds(seconds=info.get('mods_tags', 0), word="тег")} для модов.
        """, color=colour.Color.dark_gray())

        await interaction.response.send_message(embed=embedVar)
    except:
        await interaction.response.send_message("При получении общей статистики возникла странная ошибка...")

@tree.command(name='project', guild=discord.Object(id=792572437292253224))
async def project(interaction: discord.Interaction):
    view = discord.ui.View()  # Establish an instance of the discord.ui.View class
    style = discord.ButtonStyle.gray  # The button will be gray in color

    embedVar = discord.Embed(title="Это бесплатный open-source проект с открытым API! 😍")

    item = Button(style=style, emoji="👨‍💻", label="GitHub проекта", url="https://github.com/Open-Workshop")
    view.add_item(item=item)

    item = Button(style=style, emoji="📝", label="Discord сервер автора", url="https://discord.gg/UnJnGHNbBp")
    view.add_item(item=item)

    item = Button(style=style, emoji="☎", label="Такой же бот в Telegram", url="https://t.me/get_from_steam_bot")
    view.add_item(item=item)

    item = Button(style=style, emoji="🤩", label="API бота", url="https://43093.zetalink.ru:8000")
    view.add_item(item=item)

    await interaction.response.send_message(embed=embedVar, view=view)

@tree.context_menu(name="Скачать мод", guild=discord.Object(id=792572437292253224))
async def download_context(interaction: discord.Interaction, _message: discord.Message):
    await interaction.response.send_message(f'Your favourite fruit seems to be')
    # TODO функция контекстного меню где передаем ссылку / id

@tree.command(name='download', guild=discord.Object(id=792572437292253224))
async def download(interaction: discord.Interaction, link:str):
    # TODO функция косой черты где передаем ссылку / id

    await interaction.response.send_message(f'{link}')


# TODO при присоедении на сервер писать в первый же доступный канал приветственное письмо, с сообщением об отказе об ответственности


with open('key.json', 'r') as file:
    # Загружаем содержимое файла в переменную
    TOKEN = json.load(file)["key"]
client.run(TOKEN)