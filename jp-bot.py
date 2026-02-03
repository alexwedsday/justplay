import discord
import re
import time
import os

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)


last_used = {}

COOLDOWN = 10  

@client.event
async def on_ready():
    print(f"Bot conectado como {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    urls = re.findall(r'(https?://\S+)', message.content)
    for url in urls:
       
        if "youtube.com" in url or "youtu.be" in url or "spotify.com" in url:
            now = time.time()
            channel_id = message.channel.id
            
          
            if channel_id not in last_used or now - last_used[channel_id] > COOLDOWN:
                await message.channel.send(f"m!play {url}")
                last_used[channel_id] = now
            else:
                await message.channel.send("⏳ Cooldown ativo, aguarde alguns segundos antes de postar outro link!")


TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
