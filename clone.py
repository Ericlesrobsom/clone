import os
import configparser
import json
import requests
import asyncio
import nest_asyncio
import re
from pyrogram import Client, errors
from pyrogram.types import Chat
from pyrogram.enums import ChatType
from colorama import init, Fore

# Inicializa a colorama para cores no terminal
init(autoreset=True)

# Ajuste para loops de eventos no Google Colab
nest_asyncio.apply()

# Caminho base para salvar os arquivos, agora será o diretório atual do script
BASE_SAVE_PATH = os.path.dirname(os.path.realpath(__file__))

# Função que exibe informações sobre o autor e o código
def exibir_informacoes_autor():
    print(Fore.GREEN + "🥷" * 10)
    print(Fore.GREEN + "Bem-vindo ao *Downloader de Mídias Telegram*! 💾: [Ninja-Saite]")
    print(Fore.GREEN + "🎯 Objetivo: Automatizar o download de mídias de canais restritos no Telegram.")
    print("=" * 80)

# Exibe as informações quando o script é executado
exibir_informacoes_autor()

# Função para verificar a permissão de execução no Worker
def verificar_permissao(script_id):
    url = f"https://idstele.sextasoares.workers.dev/verificar?id={script_id}"  # URL do seu Worker no Cloudflare
    try:
        response = requests.get(url)
        data = response.json()

        if data['status'] == "OK":
            print(Fore.GREEN + "Permissão concedida. Continuando a execução...")
            return True
        else:
            print(Fore.RED + "Permissão negada. O script não pode ser executado. Entre em contato com TELEGRAM " + Fore.BLUE + "@SWPAID")
            return False
    except Exception as e:
        print(Fore.RED + f"Erro ao verificar permissão: {e}")
        return False

# ID único do script
scriptID = "7498818"

# Verificar se o script pode ser executado
if not verificar_permissao(scriptID):
    exit()  # Interrompe a execução do script

# *** Opção para configurar diretamente as credenciais no código ***

# Se desejar usar credenciais fixas, insira abaixo:
CREDENCIAIS_FIXAS = {
    "api_id": "29533906",
    "api_hash": "d4cc8f155af98c7700b68b5466570109"
}

# Função para solicitar API_ID e API_HASH ao usuário e salvar no config.ini
def get_api_credentials():
    print(Fore.YELLOW + "Por favor, obtenha suas credenciais em: " + Fore.BLUE + "https://my.telegram.org/auth")
    api_id = input("Digite seu API_ID: ").strip()
    api_hash = input("Digite seu API_HASH: ").strip()
    config = configparser.ConfigParser()
    config['pyrogram'] = {
        'api_id': api_id,
        'api_hash': api_hash
    }
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    return api_id, api_hash

# Perguntar ao usuário se ele quer usar credenciais fixas
usar_fixas = input("Deseja usar as credenciais fixas configuradas no código? (s/n): ").strip().lower()
if usar_fixas == 's':
    api_id = CREDENCIAIS_FIXAS["api_id"]
    api_hash = CREDENCIAIS_FIXAS["api_hash"]
else:
    # Verificar se o arquivo config.ini existe
    if not os.path.exists('config.ini'):
        print(Fore.YELLOW + "Arquivo config.ini não encontrado.")
        api_id, api_hash = get_api_credentials()
    else:
        # Ler API_ID e API_HASH do config.ini
        config = configparser.ConfigParser()
        config.read("config.ini")
        api_id = config.get("pyrogram", "api_id")
        api_hash = config.get("pyrogram", "api_hash")

        # Perguntar se deseja usar as credenciais salvas ou fornecer novas
        print(Fore.CYAN + "Credenciais salvas encontradas:")
        print(Fore.CYAN + f"API_ID: {api_id}")
        usar_salvas = input("Deseja usar as credenciais salvas? (s/n): ").strip().lower()

        if usar_salvas != 's':
            api_id, api_hash = get_api_credentials()

# Criar um cliente Pyrogram
app = Client("my_session", api_id=api_id, api_hash=api_hash)

# Função para limpar e corrigir o nome do arquivo
def limpar_nome_arquivo(nome):
    # Remove quebras de linha e substitui por um espaço
    nome_limpo = nome.replace("\n", " ").replace("\r", " ")
    # Troca a extensão para '.mp4' se for '.file'
    if nome_limpo.endswith('.file'):
        nome_limpo = nome_limpo[:-5] + '.mp4'
    return nome_limpo

async def list_channels():
    channels = []
    print(Fore.GREEN + "Buscando canais...")
    async with app:
        async for dialog in app.get_dialogs():
            try:
                chat = dialog.chat
                if chat and chat.type in (ChatType.CHANNEL, ChatType.SUPERGROUP):
                    channels.append(chat)
            except AttributeError:
                print(Fore.RED + "Erro ao acessar informações de um diálogo. Ignorando...")
                continue
        if not channels:
            print(Fore.YELLOW + "Você não é membro de nenhum canal.")
            return []
        print(Fore.CYAN + "Canais:")
        for idx, channel in enumerate(channels, start=1):
            print(Fore.CYAN + f"{idx} - {channel.title}")
    return channels

async def download_media(message, folder):
    try:
        # Usar o nome do arquivo original se disponível
        if message.document and message.document.file_name:
            file_name = message.document.file_name
        elif message.caption:
            file_name = message.caption[:100].replace("/", "_").replace("\\", "_") + ".file"
        else:
            extension = ".mp4" if message.video or message.animation else (
                ".jpg" if message.photo else (
                    ".mp3" if message.audio else (
                        ".ogg" if message.voice else ".file")))

            file_name = f"{message.id}{extension}"

        # Limpar o nome do arquivo, removendo o texto indesejado e ajustando a extensão
        file_name = limpar_nome_arquivo(file_name)

        path = os.path.join(folder, file_name)

        if os.path.exists(path):
            print(Fore.YELLOW + f"Arquivo {file_name} já existe. Pulando download.")
            return True

        while True:
            try:
                await message.download(file_name=path)
                print(Fore.GREEN + f"Download concluído: {file_name}")
                return True
            except errors.FloodWait as e:
                print(Fore.RED + f"Aguardando {e.value} segundos...")
                await asyncio.sleep(e.value)
            except Exception as e:
                print(Fore.RED + f"Erro ao baixar {file_name}: {e}")
                return False
    except Exception as e:
        print(Fore.RED + f"Erro ao processar mensagem: {e}")

async def download_from_channel(channel: Chat):
    # Criar pasta para o canal
    folder_name = channel.title.replace("/", "_").replace("\\", "_")
    save_path = os.path.join(BASE_SAVE_PATH, folder_name)
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    async with app:
        # Pega todas as mensagens do canal de cima para baixo
        messages = []
        async for message in app.get_chat_history(channel.id):
            if message.media:
                messages.append(message)

        # Baixar as mensagens na ordem de cima para baixo (mais antigas primeiro)
        for message in messages:
            await download_media(message, save_path)

async def main():
    channels = await list_channels()
    if not channels:
        return

    channel_number = int(input("Selecione um canal digitando seu número: "))
    if 1 <= channel_number <= len(channels):
        channel = channels[channel_number - 1]
        print(f"Baixando arquivos do canal: {channel.title}")
        await download_from_channel(channel)
    else:
        print("Número inválido.")

if __name__ == "__main__":
    app.run(main())
