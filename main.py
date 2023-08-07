import json
import discord
from discord import app_commands

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        await tree.sync(guild=discord.Object(id=792572437292253224))
        print("Online")

client = MyClient(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)

@tree.context_menu(name="Скачать мод", guild=discord.Object(id=792572437292253224))
async def hello(interaction: discord.Interaction, _message: discord.Message):
    await interaction.response.send_message(f'Your favourite fruit seems to be')

#TODO функция косой черты где передаем ссылку / id

#TODO функция косой черты отправляющая статистику

#TODO функция косой черты отправляющая информацию о проекте

with open('key.json', 'r') as file:
    # Загружаем содержимое файла в переменную
    TOKEN = json.load(file)["key"]
client.run(TOKEN)