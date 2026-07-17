
import discord
import os
import time
from datetime import datetime

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# ── Config ────────────────────────────────────────────────────────────────────

WELCOME_CHANNEL = "general"   # fallback if no #welcome channel exists
GOODBYE_CHANNEL = "general"   # channel for goodbye messages
EMBED_COLOR     = 0x5865F2    # Discord blurple — change to any hex colour
GOODBYE_COLOR   = 0xED4245    # Red for goodbye

# ── Intents ───────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_channel(guild: discord.Guild, preferred: str):
    return (
        discord.utils.get(guild.text_channels, name="welcome")
        or discord.utils.get(guild.text_channels, name=preferred)
        or guild.system_channel
    )

# ── Events ────────────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user} (ID: {client.user.id})")
    print("Bot is online and ready!")

@client.event
async def on_member_join(member: discord.Member):
    guild  = member.guild
    avatar = member.display_avatar.url

    # ── 1. Rich embed in welcome channel ──────────────────────────────────────
    channel = get_channel(guild, WELCOME_CHANNEL)
    if channel:
        embed = discord.Embed(
            title=f"🎉 Welcome to {guild.name}!",
            description=(
                f"Hey {member.mention}, we're thrilled to have you here!\n\n"
                f"Feel free to introduce yourself and have a look around. 🎉"
            ),
            color=EMBED_COLOR,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=avatar)
        embed.add_field(name="👤 Member",       value=member.mention,                           inline=True)
        embed.add_field(name="📅 Joined Discord", value=member.created_at.strftime("%d %b %Y"), inline=True)
        embed.add_field(name="🎊 Member #",     value=str(guild.member_count),                  inline=True)
        embed.set_footer(
            text=f"{guild.name} • Welcome!",
            icon_url=guild.icon.url if guild.icon else None
        )
        await channel.send(embed=embed)

    # ── 2. Private DM to the new member ───────────────────────────────────────
    try:
        dm_embed = discord.Embed(
            title=f"👋 Welcome to {guild.name}!",
            description=(
                f"Hi **{member.display_name}**, thanks for joining **{guild.name}**!\n\n"
                f"Here are a few things to get you started:\n"
                f"• 📜 Check out the rules channel\n"
                f"• 🙋 Introduce yourself to the community\n"
                f"• 🎮 Have fun!\n\n"
                f"If you need help, just ask — we're friendly here! 😊"
            ),
            color=EMBED_COLOR,
            timestamp=datetime.utcnow(),
        )
        dm_embed.set_thumbnail(url=guild.icon.url if guild.icon else avatar)
        dm_embed.set_footer(text=f"Sent from {guild.name}")
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        # Member has DMs disabled — silently skip
        pass

@client.event
async def on_member_remove(member: discord.Member):
    guild  = member.guild
    avatar = member.display_avatar.url

    channel = (
        discord.utils.get(guild.text_channels, name="goodbye")
        or discord.utils.get(guild.text_channels, name=GOODBYE_CHANNEL)
        or guild.system_channel
    )

    if channel:
        embed = discord.Embed(
            title="👋 Someone just left...",
            description=f"**{member.display_name}** has left the server. We'll miss you!",
            color=GOODBYE_COLOR,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=avatar)
        embed.add_field(name="👥 Members remaining", value=str(guild.member_count), inline=True)
        embed.set_footer(text=f"{guild.name}")
        await channel.send(embed=embed)

# ── Commands ──────────────────────────────────────────────────────────────────

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    content = message.content.lower().strip()

    # !ping — latency check
    if content == "!ping":
        ws_latency = round(client.latency * 1000)
        t0  = time.perf_counter()
        msg = await message.reply("🏓 Pong! Measuring...")
        roundtrip = round((time.perf_counter() - t0) * 1000)
        await msg.edit(
            content=(
                f"🏓 **Pong!**\n"
                f"• WebSocket latency: **{ws_latency}ms**\n"
                f"• Roundtrip: **{roundtrip}ms**"
            )
        )

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is not set!")
    client.run(TOKEN)
