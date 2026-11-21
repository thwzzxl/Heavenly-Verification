import os
import asyncio
import logging
from collections import deque
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

CANAL_REGRAS = int(os.getenv('CANAL_REGRAS', '0'))
CANAL_VERIFICACAO = int(os.getenv('CANAL_VERIFICACAO', '0'))
CANAL_LOGS = int(os.getenv('CANAL_LOGS', '0'))
CANAL_CHAT = int(os.getenv('CANAL_CHAT', '0'))
CANAL_PICS = int(os.getenv('CANAL_PICS', '0'))
CANAL_SUGESTOES = int(os.getenv('CANAL_SUGESTOES', '0'))
CANAL_CMD = int(os.getenv('CANAL_CMD', '0'))
CANAL_SUPORTE = int(os.getenv('CANAL_SUPORTE', '0'))
CARGO_REGRAS = int(os.getenv('CARGO_REGRAS', '0'))
CARGO_VERIFICADO = int(os.getenv('CARGO_VERIFICADO', '0'))
CARGO_MEMBROS = int(os.getenv('CARGO_MEMBROS', '0'))
COR = discord.Color.from_rgb(47, 49, 54)

LIMITE_ENTRADAS = 5
JANELA_SEGUNDOS = 10
IDADE_CONTA_DIAS = 7
INTERVALO_ALERTA_SEGUNDOS = 60

logging.basicConfig(level=logging.INFO)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bloqueios = {}
entradas = {}
ultimo_alerta = {}

# Cooldown individual por botão, com limpeza periódica para não acumular memória.
COOLDOWN_BOTOES = 1
cooldowns = {}
tentativas_cooldown = 0


def verificar_cooldown(guild_id, member_id, acao):
    global tentativas_cooldown
    agora = asyncio.get_running_loop().time()
    tentativas_cooldown += 1
    if tentativas_cooldown % 100 == 0:
        for chave, expira in list(cooldowns.items()):
            if expira <= agora:
                del cooldowns[chave]
    chave = (guild_id, member_id, acao)
    expira = cooldowns.get(chave, 0)
    if expira > agora:
        return expira - agora
    cooldowns[chave] = agora + COOLDOWN_BOTOES
    return 0


def bloqueio_membro(guild_id, member_id):
    chave = (guild_id, member_id)
    if chave not in bloqueios:
        bloqueios[chave] = asyncio.Lock()
    return bloqueios[chave]


async def responder(interaction, mensagem):
    if interaction.response.is_done():
        await interaction.followup.send(mensagem, ephemeral=True)
    else:
        await interaction.response.send_message(mensagem, ephemeral=True)


async def enviar_log(guild, titulo, descricao):
    canal = guild.get_channel(CANAL_LOGS)
    if canal is None:
        try:
            canal = await guild.fetch_channel(CANAL_LOGS)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            logging.warning('Canal de logs indisponível no servidor %s', guild.id)
            return
    if getattr(canal, 'guild', None) != guild or not hasattr(canal, 'send'):
        return
    embed = discord.Embed(title=titulo, description=descricao, color=COR,
                          timestamp=datetime.now(timezone.utc))
    embed.set_footer(text='Heavenly • Segurança')
    try:
        await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException):
        logging.exception('Não foi possível enviar log')


class BotaoRegras(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Aceito as regras', emoji='✅',
                       style=discord.ButtonStyle.success,
                       custom_id='heavenly:aceitar_regras')
    async def aceitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None or interaction.channel_id != CANAL_REGRAS:
            return await responder(interaction, 'Use o painel no canal de regras do servidor.')
        restante = verificar_cooldown(guild.id, interaction.user.id, 'regras')
        if restante:
            return await responder(interaction, f'Aguarde {restante:.0f} segundo(s) antes de clicar novamente.')
        async with bloqueio_membro(guild.id, interaction.user.id):
            try:
                membro = await guild.fetch_member(interaction.user.id)
                regras = guild.get_role(CARGO_REGRAS)
                verificado = guild.get_role(CARGO_VERIFICADO)
                membros = guild.get_role(CARGO_MEMBROS)
                if not all((regras, verificado, membros)):
                    return await responder(interaction, 'Um dos cargos não foi encontrado. Avise a moderação.')
                if verificado in membro.roles or membros in membro.roles:
                    return await responder(interaction, 'Você já possui um cargo de acesso. Avise a moderação se precisar de ajuda.')
                if regras in membro.roles:
                    return await responder(interaction, f'Você já aceitou as regras! Acesse <#{CANAL_VERIFICACAO}>.')
                await membro.add_roles(regras, reason='Aceitou as regras do Heavenly')
                await responder(interaction, f'Regras aceitas! Agora acesse <#{CANAL_VERIFICACAO}>.')
            except discord.Forbidden:
                await responder(interaction, 'O bot não tem permissão para entregar o cargo. Avise a moderação.')
            except discord.HTTPException:
                logging.exception('Erro ao aceitar regras')
                await responder(interaction, 'Não foi possível atualizar seu cargo. Tente novamente.')
            except Exception:
                logging.exception('Erro inesperado no botão de regras')
                await responder(interaction, 'Ocorreu um erro inesperado. Avise a moderação.')


class BotaoVerificacao(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Verificar', emoji='🔓',
                       style=discord.ButtonStyle.success,
                       custom_id='heavenly:verificar')
    async def verificar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None or interaction.channel_id != CANAL_VERIFICACAO:
            return await responder(interaction, 'Use o painel no canal de verificação do servidor.')
        restante = verificar_cooldown(guild.id, interaction.user.id, 'verificacao')
        if restante:
            return await responder(interaction, f'Aguarde {restante:.0f} segundo(s) antes de clicar novamente.')
        async with bloqueio_membro(guild.id, interaction.user.id):
            try:
                membro = await guild.fetch_member(interaction.user.id)
                regras = guild.get_role(CARGO_REGRAS)
                verificado = guild.get_role(CARGO_VERIFICADO)
                membros = guild.get_role(CARGO_MEMBROS)
                if not all((regras, verificado, membros)):
                    return await responder(interaction, 'Um dos cargos não foi encontrado. Avise a moderação.')
                if verificado in membro.roles and membros in membro.roles:
                    if regras in membro.roles:
                        await membro.remove_roles(regras, reason='Limpeza da verificação')
                    return await responder(interaction, 'Você já está verificado no Heavenly!')
                # A aceitação das regras é obrigatória para iniciar a verificação.
                if regras not in membro.roles:
                    return await responder(interaction, f'Aceite as regras primeiro em <#{CANAL_REGRAS}>.')
                await membro.add_roles(verificado, membros, reason='Verificação concluída no Heavenly')
                await membro.remove_roles(regras, reason='Verificação concluída')
                await responder(interaction, 'Verificação concluída! Bem-vindo ao **Heavenly**!')
                # O log é informativo e não deve desfazer a verificação se falhar.
                try:
                    await enviar_log(
                        guild,
                        'Heavenly | Verificação concluída',
                        (
                            f'**Membro:** {membro.mention}\n'
                            f'**ID:** `{membro.id}`\n'
                            '**Cargos recebidos:** Verificado, Membros\n'
                            f'**Horário:** {discord.utils.format_dt(discord.utils.utcnow(), style="F")}'
                        )
                    )
                except Exception:
                    logging.exception('Erro inesperado ao registrar verificação')
            except discord.Forbidden:
                await responder(interaction, 'O bot não tem permissão para gerenciar os cargos. Avise a moderação.')
            except discord.HTTPException:
                logging.exception('Erro ao verificar membro')
                await responder(interaction, 'Não foi possível concluir a verificação. Tente novamente.')
            except Exception:
                logging.exception('Erro inesperado no botão de verificação')
                await responder(interaction, 'Ocorreu um erro inesperado. Avise a moderação.')


class HeavenlyBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(BotaoRegras())
        self.add_view(BotaoVerificacao())


bot = HeavenlyBot(command_prefix='!', intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print('Heavenly Verification e antiraid estão online!')


@bot.event
async def on_member_join(membro: discord.Member):
    guild = membro.guild
    agora = datetime.now(timezone.utc)
    fila = entradas.setdefault(guild.id, deque())
    fila.append(agora)
    while fila and (agora - fila[0]).total_seconds() > JANELA_SEGUNDOS:
        fila.popleft()

    idade = agora - membro.created_at
    if idade < timedelta(days=IDADE_CONTA_DIAS):
        await enviar_log(
            guild, 'Conta recente detectada',
            f'Membro: {membro.mention} (`{membro.id}`)\n'
            f'Conta criada: {discord.utils.format_dt(membro.created_at, style="R")}\n'
            'Aviso informativo: conta recente não significa necessariamente risco.'
        )

    anterior = ultimo_alerta.get(guild.id)
    if len(fila) >= LIMITE_ENTRADAS and (
        anterior is None or (agora - anterior).total_seconds() >= INTERVALO_ALERTA_SEGUNDOS
    ):
        ultimo_alerta[guild.id] = agora
        await enviar_log(
            guild, 'Possível raid detectada',
            f'**{len(fila)} entradas nos últimos {JANELA_SEGUNDOS} segundos.**\n'
            'Verifique as entradas recentes. Nenhuma punição automática foi aplicada.'
        )


@bot.command(name='painel')
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def painel(ctx):
    if ctx.channel.id == CANAL_REGRAS:
        embed = discord.Embed(
            title='Heavenly | Termos e Regras',
            description=(
                'Seja bem-vindo ao **Heavenly**!\n\n'
                'Para fazer parte da comunidade, leia e aceite as regras.\n\n'
                'Clique em **Aceito as regras** para desbloquear o canal de verificação.'
            ), color=COR
        )
        embed.set_footer(text='Heavenly • Termos da Comunidade')
        await ctx.send(embed=embed, view=BotaoRegras())
    elif ctx.channel.id == CANAL_VERIFICACAO:
        embed = discord.Embed(
            title='Heavenly | Verificação',
            description=(
                'Você está quase lá!\n\n'
                'Clique em **Verificar** para concluir sua entrada no Heavenly.\n\n'
                '**Depois da verificação:**\n\n'
                '• Você recebe os cargos de acesso.\n'
                '• Os canais da comunidade são liberados.\n'
                '• Sua entrada no servidor é concluída.\n\n'
                '**Guia rápido da comunidade**\n'
                f'• <#{CANAL_CHAT}> — Converse com a comunidade.\n'
                f'• <#{CANAL_PICS}> — Compartilhe imagens permitidas.\n'
                f'• <#{CANAL_SUGESTOES}> — Envie ideias para o servidor.\n'
                f'• <#{CANAL_CMD}> — Utilize comandos de bots.\n'
                f'• <#{CANAL_SUPORTE}> — Peça ajuda à equipe.\n\n'
                'Clique no nome de um canal para acessá-lo após a verificação.'
            ), color=COR
        )
        embed.set_footer(text='Heavenly • Sistema de Verificação')
        await ctx.send(embed=embed, view=BotaoVerificacao())
    else:
        await ctx.send('Use !painel no canal de regras ou de verificação.')


@painel.error
async def painel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('Apenas administradores podem criar os painéis.')
    elif isinstance(error, commands.BotMissingPermissions):
        logging.warning('Faltam permissões para publicar o painel: %s', error)
    else:
        logging.error('Erro no comando painel: %s', error, exc_info=(type(error), error, error.__traceback__))


if not TOKEN:
    raise RuntimeError('Configure DISCORD_TOKEN nas variáveis de ambiente')

if any(not value for value in (CANAL_REGRAS, CANAL_VERIFICACAO, CANAL_LOGS, CARGO_REGRAS, CARGO_VERIFICADO, CARGO_MEMBROS)):
    raise RuntimeError('Configure os IDs de canais e cargos nas variáveis de ambiente')

bot.run(TOKEN)
