import discord
import re
import time
import os
import logging

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("DISCORD_TOKEN") 

if TOKEN: 
    logging.info("✅ Token carregado com sucesso") 
else: 
    logging.error("❌ Token não encontrado! Verifique Config Vars no Heroku")

intents = discord.Intents.default()
intents.message_content = True 
intents.messages = True
client = discord.Client(intents=intents)

logging.info(f"Intents configurados:") 
logging.info(f" - messages: {intents.messages}")
logging.info(f" - message_content: {intents.message_content}") 



last_used = {}

COOLDOWN = 10  

@client.event
async def on_ready():
    logging.info(f"Bot conectado como {client.user}")
    print(f"Bot conectado como {client.user}")

@client.event
async def on_message(message):
    logging.info(f"Mensagem recebida: {message.content}")
    if message.author == client.user:
        return
    
    urls = re.findall(r'(https?://\S+)', message.content)
    for url in urls:
       
        if "youtube.com" in url or "youtu.be" in url or "spotify.com" in url:
            now = time.time()
            author = message.author
            logging.info(f"Link detectado na mensagem de {author}: {url}")
            name = author.display_name
            logging.info(f"Nome do autor: {name}")
            channel = message.author.voice.channel
            logging.info(f"Canal de voz do autor: {channel}")
            channel_id = message.channel.id

            if message.author.voice:
                 channel = message.author.voice.channel
                 logging.info(f"Canal de voz do autor: {channel}")
                 await channel.connect();
                 await message.channel.send(f"f"🚪 Entrei no canal de voz: {channel.name}"")
            else:
                logging.warning(f"Usuário {name} não está em um canal de voz")
                await message.channel.send("⚠️ Você precisa estar em um canal de voz para usar este comando!")
                return
            
          
            if channel_id not in last_used or now - last_used[channel_id] > COOLDOWN:
                await message.channel.send(f"m!play {url}")
                last_used[channel_id] = now
                logging.info(f"Mensagem recebida no canal: {message.channel.name}")
                logging.info(f"Comando enviado: m!play {url} no canal {channel_id}")
            else:
                await message.channel.send("⏳ Cooldown ativo, aguarde alguns segundos antes de postar outro link!")
                logging.warning(f"Cooldown ativo no canal {channel_id}")


TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
