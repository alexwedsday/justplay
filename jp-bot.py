import discord
import re
import time
import os
import logging
import json

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
        "format": "bestaudio/best", 
        "noplaylist": True, 
        "ignoreerrors": True, 
        "default_search": "ytsearch", 
        "quiet": True,
        'cookiefile': 'cookies.txt'
    }

    ffmpeg_opts = {
        'options': '-vn'
    }

    try:
        from yt_dlp.utils import DownloadError

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except DownloadError as e:
            logging.warning("Formato solicitado não disponível; tentando sem especificar 'format'...")
            ydl_retry_opts = dict(ydl_opts)
            ydl_retry_opts.pop('format', None)
            try:
                with yt_dlp.YoutubeDL(ydl_retry_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            except DownloadError as e2:
                logging.exception("Retry falhou: formato ainda indisponível")
                # Tentar obter a lista de formatos via binário yt-dlp para diagnóstico
                try:
                    import subprocess
                    proc = subprocess.run(['yt-dlp', '--list-formats', url], capture_output=True, text=True, timeout=15)
                    formats_out = proc.stdout or proc.stderr
                except Exception as sub_err:
                    logging.exception("Erro ao executar yt-dlp --list-formats")
                    formats_out = f"Não foi possível listar formatos: {sub_err}"

                # Truncar a saída para evitar mensagens muito longas no Discord
                formats_preview = formats_out.strip().splitlines()[:20]
                preview_text = "\n".join(formats_preview)
                await message.channel.send(f"""❌ Formato solicitado indisponível e retry falhou. Formatos disponíveis (ou erro de listagem):
```
{preview_text}
```""")
                raise

        # Se for playlist, pega o primeiro item válido
        if isinstance(info, dict) and 'entries' in info:
            entries = [e for e in info['entries'] if e]
            if not entries:
                raise Exception("Nenhuma entrada encontrada na playlist.")
            info = entries[0]

        logging.info(f"Informações extraídas para {url}: {json.dumps(ydl.sanitize_info(info), indent=2)}")

        audio_url = info.get('url')
        if not audio_url:
            formats = info.get('formats') or []
            if formats:
                audio_format = sorted(formats, key=lambda f: (f.get('abr') or 0, f.get('filesize') or 0), reverse=True)[0]
                audio_url = audio_format.get('url')
            else:
                raise Exception("Nenhuma URL de áudio encontrada nas informações extraídas.")

        if not audio_url:
            raise Exception("Não foi possível obter a URL de áudio válida.")

        vc.play(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts))
        await message.channel.send(f"🎵 Tocando agora: {info.get('title', url)}")
    except Exception as e:
        logging.exception("Erro em play_url")
        await message.channel.send(f"❌ Erro ao tentar tocar o áudio: {e}")

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
