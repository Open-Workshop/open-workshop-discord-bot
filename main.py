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


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        await tree.sync()
        print("Online")

    async def on_guild_join(self, guild):
        # Получение первого доступного текстового канала
        channel = next((channel for channel in guild.text_channels if channel.permissions_for(guild.me).send_messages), None)

        if channel:
            await channel.send("""
Этот бот позволяет скачивать моды со Steam через чат Discord! 💨

**Разработчики не несут ответственность за контент получаемый через бота и ваши намеренья как его использовать. 📄**
**А так же оставляя бота на этом сервере вы подтверждаете, что все участники официально приобрели игру/программу на одной из площадок где она представлена! 🛒**
            """)
        else:
            print("Нет доступного канала для отправки сообщения.")

client = MyClient(intents=discord.Intents.default())
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
                Пользователям отправлено {info.get('mods_sent_count')} файлов.
                Сервис работает {await tools.format_seconds(seconds=info.get('statistics_days', 0), word="день")}.
                
                У {info.get('games', 0)} игр сохранено {info.get('mods', 0)} модов, {info.get('mods_dependencies', 0)} из которых имеют зависимости на другие моды.
                Сервису известно об {await tools.format_seconds(seconds=info.get('genres', 0), word="жанр")} игр и {await tools.format_seconds(seconds=info.get('mods_tags', 0), word="тег")} для модов.
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

    await interaction.response.send_message(embed=embedVar, view=view)

# Функции-точки входа
@tree.context_menu(name="Скачать мод")
async def download_context(interaction: discord.Interaction, message: discord.Message):
    await main_download(interaction=interaction, link=message.content)

@tree.command(name='download', description="Скачай мод напрямую со Steam передав ссылку на мод или ID мода в Steam!")
async def download(interaction: discord.Interaction, link:str):
    await main_download(interaction=interaction, link=link)


# TODO побороть ошибку параллельной загрузку
# Основной обработчик загрузки модов
async def main_download(interaction: discord.Interaction, link:str):
    global SERVER_ADDRESS
    await interaction.response.send_message("В обработке")

    channel = client.get_channel(interaction.channel_id)

    try:
        start_time = time.time()

        link = await tools.pars_link(link=link)
        if link is bool:
            await channel.send("Ты мне какую-то не правильную ссылку скинул! 🧐")
            return

        if link.isdigit():
            link = int(link)
            if link <= 0:
                await channel.send("Я даже без проверки знаю, что такого мода нету :)")
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

                            item = Button(style=style, label="Скачать", url=SERVER_ADDRESS+f"/download/{link}")
                            view.add_item(item=item)

                            await channel.send(embed=embedVar, view=view)
                            return
                except:
                    await channel.send("Похоже, что сервер не отвечает 😔 _(point=2)_")
                    return -1

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url=SERVER_ADDRESS+f"/download/steam/{str(link)}", timeout=20) as response:
                            if response.headers.get('content-type') == "application/zip":
                                file_content = await response.read()
                                file_name = await tools.get_name(response.headers.get("content-disposition", "ERROR.zip"))
                                print(f"File name: {file_name}")
                                file = discord.File(io.BytesIO(file_content), filename=file_name)
                                await channel.send(f"Ваш запрос занял {await tools.format_seconds(round(time.time()-start_time, 1))}", file=file)
                                return
                            else:
                                result = await response.read()
                                header_result = response.headers
                except:
                    print("ERROR")
                    await channel.send("Похоже, что сервер не отвечает 😔 _(point=3)_")
                    return -1


                if header_result.get('content-type') == "application/json":
                    data = json.loads(result.decode())
                    if data["error_id"] == 0 or data["error_id"] == 3:
                        await channel.send("На сервере нету этого мода, но он сейчас его загрузит! _(это может занять некоторое время)_")

                        for i in range(60):
                            await asyncio.sleep(1)
                            try:
                                async with aiohttp.ClientSession() as session:
                                    response = await session.get(url=SERVER_ADDRESS+f"/condition/mod/%5B{str(link)}%5D",
                                                                 timeout=10)
                                    res = await response.read()
                                    header_result = response.headers
                            except:
                                await channel.send("Похоже, что сервер не отвечает 😔 _(point=5)_")
                                return -1
                            if header_result.get('content-type') == "application/json":
                                data = json.loads(res.decode())
                                if data.get(str(link), None) == None:
                                    await channel.send("Серверу не удалось загрузить этот мод 😢")
                                    return -1
                                elif data[str(link)] <= 1:
                                    try:
                                        async with aiohttp.ClientSession() as session:
                                            response = await session.get(url=SERVER_ADDRESS + f"/info/mod/{str(link)}",
                                                                         timeout=10)
                                            data = await response.text()

                                            # Если больше 30 мб (получаю от сервера в байтах, а значит и сравниваю в них)
                                            info = json.loads(data)
                                            if info["result"] is not None and info["result"].get("size", 0) > 10485760:
                                                view = discord.ui.View()  # Establish an instance of the discord.ui.View class
                                                style = discord.ButtonStyle.gray  # The button will be gray in color

                                                embedVar = discord.Embed(
                                                    title=f"Ого! `{info['result'].get('name', str(link))}` весит {round(info['result'].get('size', 1) / 1048576, 1)} мегабайт!\nСкачай его по прямой ссылке :smirk_cat:")

                                                item = Button(style=style, label="Скачать",
                                                              url=SERVER_ADDRESS + f"/download/{link}")
                                                view.add_item(item=item)

                                                await channel.send(embed=embedVar, view=view)
                                                return
                                    except:
                                        await channel.send("Похоже, что сервер не отвечает 😔 _(point=4)_")
                                        return -1

                                    try:
                                        async with aiohttp.ClientSession() as session:
                                            async with session.get(url=SERVER_ADDRESS + f"/download/{str(link)}",
                                                                   timeout=20) as response:
                                                if response.headers.get('content-type') == "application/zip":
                                                    file_content = await response.read()
                                                    file_name = await tools.get_name(
                                                        response.headers.get("content-disposition", "ERROR.zip"))
                                                    print(file_name)
                                                    file = discord.File(io.BytesIO(file_content), filename=file_name)
                                                    await channel.send(
                                                        f"Ваш запрос занял {await tools.format_seconds(round(time.time() - start_time, 1))}",
                                                        file=file)
                                                    return
                                                else:
                                                    await channel.send("Серверу не удалось загрузить этот мод 😢")
                                    except:
                                        await channel.send("Похоже, что сервер не отвечает 😔 _(point=1)_")


                                    return
                            else:
                                await channel.send("Сервер прислал неожиданный ответ 😧 _(point=1)_")
                                return
                        await channel.send("Превышено время ожидания ответа с сервера!")
                        return -1

                    elif data["error_id"] == 1:
                        await channel.send("Сервер запускается и не может сейчас грузить моды! Повтори попытку через пару минут :)")
                    elif data["error_id"] == 2:
                        await channel.send("Сервер говорит что такого мода не существует 😢")
                    else:
                        await channel.send("Сервер прислал неожиданный ответ 😧 _(point=2)_")
                else:
                    await channel.send("Сервер прислал неожиданный ответ 😧 _(point=3)_")
        else:
            if link is str and (link.startswith("https://steamcommunity.com") or link.startswith("https://store.steampowered.com")):
                await channel.send("Мне нужна ссылка конкретно на мод! _(или его ID)_")
            elif link is str and (link.startswith("https://") or link.startswith("http://")):
                await channel.send("Пока что я умею скачивать только со Steam 😿")
            else:
                await channel.send("Если ты хочешь скачать мод, то просто скинь ссылку или `ID` мода в чат!")
    except:
        await channel.send("Ты вызвал странную ошибку...\nПопробуй загрузить мод еще раз!")



with open('key.json', 'r') as file:
    # Загружаем содержимое файла в переменную
    TOKEN = json.load(file)["key"]
client.run(TOKEN)