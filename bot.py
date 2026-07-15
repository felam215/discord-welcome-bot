import discord
import os
import time

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# --- Intents ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)

# Change this to match your welcome channel name
WELCOME_CHANNEL = "general"

# ── Events ────────────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user} (ID: {client.user.id})")
    print("Bot is online and ready!")

@client.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    # Try welcome → general → system channel fallback
    channel = (
        discord.utils.get(guild.text_channels, name="welcome")
        or discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL)
        or guild.system_channel
    )

    if channel:
        await channel.send(
            f"👋 Hey {member.mention}, welcome to **{guild.name}**! "
            f"We're so glad you're here. Feel free to introduce yourself! 🎉\n"
            f"You are our **#{guild.member_count}** member!"
        )

# ── Commands ──────────────────────────────────────────────────────────────────

@client.event
async def on_message(message: discord.Message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    content = message.content.lower().strip()

    # !ping — latency check
    if content == "!ping":
        ws_latency = round(client.latency * 1000)
        t0 = time.perf_counter()
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
