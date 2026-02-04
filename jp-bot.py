import discord
import re
import time
import os
import logging

try:
    import yt_dlp
except Exception:
    yt_dlp = None
    logging.warning("yt_dlp não disponível; a reprodução de URLs pode falhar se o pacote não estiver instalado.")

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

async def play_url(message, url):

    vc = message.guild.voice_client
    if vc is None:
        await message.channel.send("❌ Não estou conectado a um canal de voz.")
        return

    if yt_dlp is None:
        await message.channel.send("❌ O pacote yt-dlp não está instalado no ambiente do bot.")
        logging.error("yt_dlp não disponível")
        return

    ydl_opts = {
        'format': 'bestaudio',
        'quiet': True,
        'cookiefile': 'cookies.txt'
    }
    ffmpeg_opts = {
        'options': '-vn'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

       
        if getattr(vc, 'is_playing', None) and (vc.is_playing() or vc.is_paused()):
            vc.stop()

        vc.play(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts))
        await message.channel.send(f"🎵 Tocando agora: {info.get('title', url)}")
    except Exception as e:
        logging.exception("Erro em play_url")
        await message.channel.send(f"❌ Erro ao tentar tocar o áudio: {e}")
        raise

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
            channel_id = message.channel.id

            if message.author.voice:
                channel = message.author.voice.channel
                if message.guild.voice_client is None:
                    logging.info(f"Canal de voz do autor: {channel}")
                    await channel.connect()
                else:
                    logging.info(f"Bot já conectado a um canal de voz no servidor {message.guild.name}")
                    await message.guild.voice_client.move_to(channel)

            else:
                logging.warning(f"Usuário {name} não está em um canal de voz")
                await message.channel.send("⚠️ Você precisa estar em um canal de voz para usar este comando!")
                return
            
          
            if channel_id not in last_used or now - last_used[channel_id] > COOLDOWN:
                try:
                    last_used[channel_id] = now
                    await play_url(message, url)
                    logging.info(f"Mensagem recebida no canal: {message.channel.name}")
                    logging.info(f"Tocando url {url} no canal {channel_id}")
                except Exception as e:
                    logging.exception("Erro ao tocar áudio")
                    await message.channel.send(f"❌ Erro ao tentar tocar o áudio: {e}")
            else:
                await message.channel.send("⏳ Cooldown ativo, aguarde alguns segundos antes de postar outro link!")
                logging.warning(f"Cooldown ativo no canal {channel_id}")


TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)
