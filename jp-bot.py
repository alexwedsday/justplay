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
    
    # Se houver cookies passados via ENV, grava em cookies.txt para uso pelo yt-dlp
    cookies_env = os.getenv('YTDL_COOKIES')
    if cookies_env:
        try:
            with open('cookies.txt', 'w') as cf:
                cf.write(cookies_env)
        except Exception:
            logging.exception("Erro ao escrever cookies em cookies.txt")

    # Opções padrão para streaming
    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "ignoreerrors": True,
        "default_search": "ytsearch",
        "quiet": True,
        'cookiefile': 'cookies.txt',
        # js_runtimes deve ser um dicionário de {runtime: {config}}
        "js_runtimes": {"node": {}},
    }

    ffmpeg_opts = {
        'options': '-vn'
    }

    try:
        from yt_dlp.utils import DownloadError

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except DownloadError:
            logging.warning("Formato solicitado não disponível; tentando sem especificar 'format'...")
            ydl_retry_opts = dict(ydl_opts)
            ydl_retry_opts.pop('format', None)
            try:
                with yt_dlp.YoutubeDL(ydl_retry_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            except DownloadError:
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

                # Tentar fallback de download: baixa o arquivo e reproduz localmente
                try:
                    ydl_dl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': '/tmp/%(id)s.%(ext)s',
                        'noplaylist': True,
                        'quiet': True,
                        'cookiefile': 'cookies.txt',
                    }
                    with yt_dlp.YoutubeDL(ydl_dl_opts) as ydl:
                        info_dl = ydl.extract_info(url, download=True)
                        if not info_dl:
                            raise Exception('Download fallback não retornou informações')
                        filename = ydl.prepare_filename(info_dl)

                    # Procurar pelo arquivo baixado (considerando possíveis conversões de extensão)
                    base = os.path.splitext(filename)[0]
                    candidates = [f"{base}.{ext}" for ext in ("m4a","mp3","webm","mp4","opus","wav")]
                    candidates.append(filename)
                    existing = None
                    import glob
                    for c in candidates:
                        if os.path.exists(c):
                            existing = c
                            break
                    if not existing:
                        matches = glob.glob(base + '.*')
                        if matches:
                            existing = matches[0]
                    if not existing:
                        raise Exception('Arquivo de áudio não encontrado após download')

                    # Para segurança, para qualquer reprodução atual
                    if getattr(vc, 'is_playing', None) and (vc.is_playing() or vc.is_paused()):
                        try:
                            vc.stop()
                        except Exception:
                            logging.exception('Falha ao parar reprodução atual')

                    try:
                        vc.play(discord.FFmpegPCMAudio(existing, **ffmpeg_opts))
                        await message.channel.send(f"🎵 Tocando agora (download): {info_dl.get('title', url)}")
                        return
                    except Exception as play_err:
                        logging.exception('Erro ao reproduzir arquivo baixado')
                        await message.channel.send(f"❌ Erro ao reproduzir arquivo baixado: {play_err}")
                        return
                except Exception:
                    logging.exception('Fallback de download falhou')
                    await message.channel.send('❌ Fallback de download falhou. Verifique logs.')
                    return

        # Validação: garante que `info` foi retornado
        if not info:
            logging.error("yt-dlp retornou None para 'info' — conteúdo possivelmente indisponível ou requer cookies/JS runtime")
            # Antes de falhar completamente, tentar fallback de download como último recurso
            try:
                ydl_dl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': '/tmp/%(id)s.%(ext)s',
                    'noplaylist': True,
                    'quiet': True,
                    'cookiefile': 'cookies.txt',
                }
                with yt_dlp.YoutubeDL(ydl_dl_opts) as ydl:
                    info_dl = ydl.extract_info(url, download=True)
                    if info_dl:
                        filename = ydl.prepare_filename(info_dl)
                        base = os.path.splitext(filename)[0]
                        import glob
                        matches = glob.glob(base + '.*')
                        if matches:
                            existing = matches[0]
                            vc.play(discord.FFmpegPCMAudio(existing, **ffmpeg_opts))
                            await message.channel.send(f"🎵 Tocando agora (download): {info_dl.get('title', url)}")
                            return
            except Exception:
                logging.exception('Fallback de download falhou após info None')

            await message.channel.send("❌ Não foi possível extrair informações do vídeo — pode estar indisponível, privado ou exigir cookies/JS runtime.")
            return

        # Se for playlist, pega o primeiro item válido
        if isinstance(info, dict) and 'entries' in info:
            entries = [e for e in info['entries'] if e]
            if not entries:
                await message.channel.send("❌ Nenhuma entrada encontrada na playlist.")
                return
            info = entries[0]

        # Log seguro das informações (sanitize se disponível)
        sanitizer = getattr(yt_dlp, 'sanitize_info', None)
        safe_info = sanitizer(info) if sanitizer else info
        try:
            logging.info(f"Informações extraídas para {url}: {json.dumps(safe_info, indent=2)}")
        except Exception:
            logging.info("Informações extraídas (não serializáveis) — consulte logs")

        # Garante que info seja um dicionário antes de usar .get
        if not isinstance(info, dict):
            await message.channel.send("❌ Estrutura de dados inesperada retornada pelo extractor.")
            return

        audio_url = info.get('url')
        if not audio_url:
            formats = info.get('formats') or []
            if formats:
                audio_format = sorted(formats, key=lambda f: (f.get('abr') or 0, f.get('filesize') or 0), reverse=True)[0]
                audio_url = audio_format.get('url')
            else:
                await message.channel.send("❌ Nenhuma URL de áudio encontrada nas informações extraídas.")
                return

        if not audio_url:
            await message.channel.send("❌ Não foi possível obter a URL de áudio válida.")
            return

        # Tentar reproduzir com tratamento de erros e tentativa de recovery
        try:
            if getattr(vc, 'is_playing', None) and (vc.is_playing() or vc.is_paused()):
                try:
                    vc.stop()
                except Exception:
                    logging.exception('Falha ao parar reprodução atual')

            vc.play(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts))
            await message.channel.send(f"🎵 Tocando agora: {info.get('title', url)}")
        except Exception as e_play:
            logging.exception("Erro ao iniciar reprodução via streaming")
            # tentativa de recuperação: parar, desconectar (se necessário), e reconectar/mover para o canal do autor
            try:
                channel = message.author.voice.channel if message.author and message.author.voice else None

                # Tenta parar e desconectar o VoiceClient atual com segurança
                try:
                    if getattr(vc, 'is_playing', None) and (vc.is_playing() or vc.is_paused()):
                        vc.stop()
                except Exception:
                    logging.exception('Falha ao parar reprodução atual durante recuperação')

                try:
                    if getattr(vc, 'is_connected', None):
                        if vc.is_connected():
                            await vc.disconnect()
                except Exception:
                    logging.exception('Falha ao desconectar VoiceClient durante recuperação')

                if channel:
                    try:
                        # Se não há conexão ativa, conecta; caso contrário, tenta mover a conexão existente
                        if message.guild.voice_client is None:
                            new_vc = await channel.connect()
                        else:
                            new_vc = message.guild.voice_client
                            try:
                                await new_vc.move_to(channel)
                            except Exception:
                                logging.exception('Falha ao mover VoiceClient para o canal durante recuperação')

                        # Tenta tocar com a conexão nova/existente
                        try:
                            new_vc.play(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts))
                            await message.channel.send(f"🎵 Tocando agora (reconectado): {info.get('title', url)}")
                            return
                        except Exception:
                            logging.exception('Falha ao reproduzir após reconectar/mover')
                    except discord.ClientException as ce:
                        logging.exception('ClientException ao conectar/mover: já conectado?')
                        existing_vc = message.guild.voice_client
                        if existing_vc:
                            try:
                                # Tenta mover e tocar com a conexão existente
                                try:
                                    await existing_vc.move_to(channel)
                                except Exception:
                                    logging.exception('Falha ao mover existing VoiceClient durante recuperação')
                                existing_vc.play(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts))
                                await message.channel.send(f"🎵 Tocando agora (reconectado): {info.get('title', url)}")
                                return
                            except Exception:
                                logging.exception('Falha ao tocar com existing VoiceClient durante recuperação')
                    except Exception:
                        logging.exception('Falha ao reconectar e reproduzir')
            except Exception:
                logging.exception('Erro na rotina de recuperação da voz')

            await message.channel.send(f"❌ Erro ao tentar tocar o áudio: {e_play}")
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
