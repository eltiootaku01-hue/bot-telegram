# -*- coding: utf-8 -*-
import os
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.db.models import User
from src.services.drop_service import spawn_card_drop, claim_card_drop

# Configuración del motor de base de datos SQLite
engine = create_engine("sqlite:///bot_database.db", echo=False)


class ClaimDropView(discord.ui.View):
    """
    Vista interactiva que contiene el botón 'Reclamar Carta' para Discord.
    """
    def __init__(self, drop_id: int):
        super().__init__(timeout=300)  # Expira en 5 minutos
        self.drop_id = drop_id

    @discord.ui.button(
        label="🎴 ¡Reclamar Carta!", 
        style=discord.ButtonStyle.primary, 
        custom_id="claim_drop_btn"
    )
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        discord_user = interaction.user

        with Session(engine) as session:
            # 1. Buscar o crear al usuario en la BD usando su discord_id
            user = session.scalars(
                select(User).where(User.discord_id == discord_user.id)
            ).first()

            if not user:
                user = User(
                    id=discord_user.id,  # Asigna ID de origen
                    discord_id=discord_user.id,
                    username=discord_user.name
                )
                session.add(user)
                session.commit()

            # 2. Ejecutar el reclamo utilizando la lógica central de drop_service
            success, message = claim_card_drop(
                session=session,
                drop_id=self.drop_id,
                user_id=user.id,
                username=discord_user.name
            )

            if success:
                # Modificar el botón para reflejar que la carta ya fue reclamada
                button.disabled = True
                button.label = f"Reclamada por {discord_user.display_name}"
                button.style = discord.ButtonStyle.success

                await interaction.response.edit_message(view=self)
                await interaction.followup.send(
                    f"✅ ¡Felicidades {discord_user.mention}! {message}", 
                    ephemeral=False
                )
            else:
                # Notificación privada en caso de fallo (ej. si alguien fue más rápido)
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)


class TCGDiscordBot(commands.Bot):
    """
    Cliente principal del Bot de Discord con soporte para Slash Commands.
    """
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Sincronizar los comandos de barra diagonal (Slash Commands)
        await self.tree.sync()
        print("✓ Comandos de Discord sincronizados.")


bot = TCGDiscordBot()


@bot.tree.command(name="drop", description="Solicita el lanzamiento de una carta silvestre en este canal.")
async def drop_command(interaction: discord.Interaction):
    """
    Comando Slash /drop para generar una carta aleatoria en un canal de Discord.
    """
    await interaction.response.defer()

    channel_id = interaction.channel_id
    guild_id = interaction.guild_id or channel_id

    with Session(engine) as session:
        drop, card_instance, card = spawn_card_drop(
            session=session,
            group_id=guild_id,
            message_thread_id=channel_id
        )

        # Crear tarjeta visual Embed
        embed = discord.Embed(
            title="✨ ¡UNA CARTA SILVESTRE HA APARECIDO!",
            description=(
                f"🎴 **Personaje:** {card.name}
"
                f"⭐ **Rareza:** {card.rarity}
"
                f"🌊 **Elemento:** {card.element or 'Neutro'}

"
                f"¡Presiona el botón para agregarla a tu mazo!"
            ),
            color=discord.Color.gold()
        )

        if card.image_url:
            embed.set_image(url=card.image_url)

        view = ClaimDropView(drop_id=drop.id)
        await interaction.followup.send(embed=embed, view=view)


def run_discord_bot():
    token = os.getenv("DISCORD_BOT_TOKEN", "TU_DISCORD_BOT_TOKEN")
    if token == "TU_DISCORD_BOT_TOKEN":
        print("⚠️ Advertencia: No se ha configurado DISCORD_BOT_TOKEN en las variables de entorno.")
        return
    bot.run(token)


if __name__ == "__main__":
    run_discord_bot()
