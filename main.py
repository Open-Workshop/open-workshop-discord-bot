import io
import time
import json
import tools
import asyncio
import aiohttp
import discord
from discord import app_commands
from discord.ui import Button


SERVER_ADDRESS = 'https://api.openworkshop.su'
WEBSITE_ADDRESS = 'https://openworkshop.su'


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        await tree.sync()
        print("Online")



activity = discord.Activity(
    type=discord.ActivityType.playing,
    name="скачивание модов"
)

client = MyClient(intents=discord.Intents.default(), activity=activity)
tree = app_commands.CommandTree(client)

@tree.command(name='statistics', description="Небольшая статистика работы сервиса")
async def statistics(interaction: discord.Interaction):
    global SERVER_ADDRESS
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.get(url=SERVER_ADDRESS+"/statistics/info/all", timeout=10)

            text = await response.text()
            info = json.loads(text)

            embedVar = discord.Embed(title="Общая статистика", description=f"""
                Пользователям отправлено `{info.get('mods_sent_count')} файлов`.
                Сервис работает `{await tools.format_seconds(seconds=info.get('statistics_days', 0), word="день")}`.
                
                У `{info.get('games', 0)} игр` сохранено `{info.get('mods', 0)} модов`, `{info.get('mods_dependencies', 0)}` из которых имеют зависимости на другие моды.
                Сервису известно об `{await tools.format_seconds(seconds=info.get('genres', 0), word="жанр")} игр` и `{await tools.format_seconds(seconds=info.get('mods_tags', 0), word="тег")}` для модов.
            
                Бот находится на `{await tools.format_seconds(seconds=len(client.guilds), word="сервере")}`.
            """, color=discord.Color.dark_gray())

            await interaction.response.send_message(embed=embedVar)
    except asyncio.TimeoutError:
        await interaction.response.send_message("Превышено время ожидания при получении общей статистики.")

@tree.command(name='project', description="Информация о проекте и полезные ссылки :)")
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

    item = Button(style=style, emoji="🤩", label="API бота", url=SERVER_ADDRESS)
    view.add_item(item=item)
    
    item = Button(style=style, emoji="☝", label="Сайт", url=WEBSITE_ADDRESS)
    view.add_item(item=item)

    await interaction.response.send_message(embed=embedVar, view=view)

# Функции-точки входа
@tree.context_menu(name="Скачать мод")
async def download_context(interaction: discord.Interaction, message: discord.Message):
    await main_download(interaction=interaction, link=message.content)

@tree.command(name='download', description="Скачай мод напрямую со Open Workshop передав ссылку на мод или ID мода!")
async def download(interaction: discord.Interaction, link:str):
    await main_download(interaction=interaction, link=link)


# Основной обработчик загрузки модов
async def main_download(interaction: discord.Interaction, link:str):
    global SERVER_ADDRESS

    channel = client.get_channel(interaction.channel_id)

    try:
        start_time = time.time()

        link = await tools.pars_link(link=link)
        if link is bool:
            await interaction.response.send_message("Ты мне какую-то не правильную ссылку скинул! 🧐")
            return

        if link.isdigit():
            link = int(link)
            if link <= 0:
                await interaction.response.send_message("Я даже без проверки знаю, что такого мода нету :)")
            else:
                try:
                    async with aiohttp.ClientSession() as session:
                        response = await session.get(url=SERVER_ADDRESS+f"/info/mod/{str(link)}", timeout=10)
                        data = await response.text()

                        # Если больше 30 мб (получаю от сервера в байтах, а значит и сравниваю в них)
                        info = json.loads(data)
                        if info["result"] is not None and info["result"].get("size", 0) > 10485760:
                            view = discord.ui.View()  # Establish an instance of the discord.ui.View class
                            style = discord.ButtonStyle.gray  # The button will be gray in color

                            embedVar = discord.Embed(title=f"Ого! `{info['result'].get('name', str(link))}` весит {round(info['result'].get('size', 1)/1048576, 1)} мегабайт!\nСкачай его по прямой ссылке :smirk_cat:")

                            itemD = Button(style=style, label="Скачать", url=SERVER_ADDRESS+f"/download/{link}")
                            view.add_item(item=itemD)
                            itemW = Button(style=style, label="Станица на сайте", url=WEBSITE_ADDRESS+f"/mod/{link}")
                            view.add_item(item=itemW)

                            await interaction.response.send_message(embed=embedVar, view=view)
                            return
                except:
                    await interaction.response.send_message("Похоже, что сервер не отвечает 😔 _(point=2)_")
                    return -1

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url=SERVER_ADDRESS+f"/download/steam/{str(link)}", timeout=20) as response:
                            if response.headers.get('content-type') == "application/zip":
                                await interaction.response.send_message("Сейчас пришлю...")

                                file_content = await response.read()
                                file_name = await tools.get_name(response.headers.get("content-disposition", "ERROR.zip"))
                                print(f"File name: {file_name}")

                                file = discord.File(io.BytesIO(file_content), filename=file_name)

                                view = discord.ui.View()  # Establish an instance of the discord.ui.View class
                                style = discord.ButtonStyle.gray  # The button will be gray in color
                                itemW = Button(style=style, label="Станица на сайте",
                                               url=WEBSITE_ADDRESS + f"/mod/{link}")
                                view.add_item(item=itemW)

                                await channel.send(f"Ваш запрос занял {await tools.format_seconds(round(time.time()-start_time, 1))}", file=file, view=view)
                                return
                            else:
                                result = await response.read()
                                header_result = response.headers
                except:
                    print("ERROR")
                    await interaction.response.send_message("Похоже, что сервер не отвечает 😔 _(point=3)_")
                    return -1


                if header_result.get('content-type') == "application/json":
                    data = json.loads(result.decode())
                    if data["error_id"] in [0, 2, 3]:
                        await interaction.response.send_message("На сервере нету этого мода :(")
                    else:
                        await interaction.response.send_message("Сервер прислал неожиданный ответ 😧 _(point=2)_")
                else:
                    await interaction.response.send_message("Сервер прислал неожиданный ответ 😧 _(point=3)_")
        else:
            if type(link).__name__ == 'str' and (link.startswith("https://steamcommunity.com") or link.startswith("https://store.steampowered.com") or link.startswith("https://openworkshop.su")):
                await interaction.response.send_message("Мне нужна ссылка конкретно на мод! _(или его ID)_")
            elif type(link).__name__ == 'str' and (link.startswith("https://") or link.startswith("http://")):
                await interaction.response.send_message("Пока что я умею скачивать только c Open Workshop и ассоцированные моды со Steam 😿")
            else:
                await interaction.response.send_message("Если ты хочешь скачать мод, то просто скинь ссылку или `ID` мода в чат!")
    except:
        await interaction.response.send_message("Ты вызвал странную ошибку...\nПопробуй загрузить мод еще раз!")



with open('key.json', 'r') as file:
    # Загружаем содержимое файла в переменную
    TOKEN = json.load(file)["key"]
client.run(TOKEN)