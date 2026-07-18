
import discord
import os
import time
from datetime import datetime

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# ── Config ────────────────────────────────────────────────────────────────────

VERIFIED_ROLE_NAME   = "Verified"     # Role granted after verification
UNVERIFIED_ROLE_NAME = "Unverified"   # Role given on join (blocks public channels)
VERIFY_CHANNEL       = "verify"       # Public channel where new members verify
GOODBYE_CHANNEL      = "mod-log"      # Private staff channel for leave notifications
VERIFY_EMOJI         = "✅"           # Emoji members react with to verify

EMBED_COLOR    = 0x5865F2   # Blurple (welcome / verify)
SUCCESS_COLOR  = 0x57F287   # Green   (verified)
GOODBYE_COLOR  = 0xED4245   # Red     (goodbye)

# ── Intents ───────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_or_create_role(guild: discord.Guild, name: str, **kwargs) -> discord.Role:
    role = discord.utils.get(guild.roles, name=name)
    if not role:
        role = await guild.create_role(name=name, **kwargs)
    return role

# ── Events ────────────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user} (ID: {client.user.id})")
    print("Bot is online and ready!")

# ─── New member joins ─────────────────────────────────────────────────────────
@client.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    # 1. Assign Unverified role to lock public channels
    unverified_role = await get_or_create_role(
        guild, UNVERIFIED_ROLE_NAME, color=discord.Color.greyple()
    )
    await member.add_roles(unverified_role, reason="New member — pending verification")

    # 2. Post verification prompt in #verify
    verify_channel = discord.utils.get(guild.text_channels, name=VERIFY_CHANNEL)
    if verify_channel:
        embed = discord.Embed(
            title="👋 Welcome! One quick step to get in...",
            description=(
                f"Hey {member.mention}, welcome to **{guild.name}**!\n\n"
                f"React with {VERIFY_EMOJI} below to verify yourself and unlock the server. 🔓"
            ),
            color=EMBED_COLOR,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Why verify?",
            value="This keeps the server safe from bots and spam.",
            inline=False
        )
        embed.set_footer(text=f"React with {VERIFY_EMOJI} to continue")
        msg = await verify_channel.send(embed=embed)
        await msg.add_reaction(VERIFY_EMOJI)

    # 3. DM the new member with instructions
    try:
        dm_embed = discord.Embed(
            title=f"👋 Welcome to {guild.name}!",
            description=(
                f"Hi **{member.display_name}**, thanks for joining!\n\n"
                f"To access the server, head to the **#verify** channel and "
                f"react with {VERIFY_EMOJI} to get verified. It only takes a second! 🎉"
            ),
            color=EMBED_COLOR,
        )
        dm_embed.set_footer(text=f"Sent from {guild.name}")
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        pass  # DMs disabled — silently skip

# ─── Reaction added — handle verification ─────────────────────────────────────
@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # Ignore bot's own reactions
    if payload.user_id == client.user.id:
        return

    # Only handle the verify emoji
    if str(payload.emoji) != VERIFY_EMOJI:
        return

    guild = client.get_guild(payload.guild_id)
    if not guild:
        return

    # Only process reactions in the #verify channel
    channel = client.get_channel(payload.channel_id)
    if not channel or channel.name != VERIFY_CHANNEL:
        return

    # Make sure the reacted message was posted by the bot
    try:
        message = await channel.fetch_message(payload.message_id)
        if message.author != client.user:
            return
    except Exception:
        return

    member = guild.get_member(payload.user_id)
    if not member:
        return

    # Get or create Verified role
    verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
    if not verified_role:
        verified_role = await guild.create_role(
            name=VERIFIED_ROLE_NAME,
            color=discord.Color.green(),
            reason="Auto-created by bot for verification",
        )

    # Skip if already verified
    if verified_role in member.roles:
        return

    # Grant Verified, revoke Unverified
    await member.add_roles(verified_role, reason="Member verified via reaction")
    unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
    if unverified_role and unverified_role in member.roles:
        await member.remove_roles(unverified_role, reason="Member verified")

    # Confirmation in #verify (auto-deletes after 6s)
    await channel.send(
        f"✅ {member.mention} is now verified and has access to the server! Welcome! 🎉",
        delete_after=6,
    )

    # Confirmation DM
    try:
        success_embed = discord.Embed(
            title="✅ You're Verified!",
            description=(
                f"You now have full access to **{guild.name}**.\n"
                f"Enjoy your stay and feel free to introduce yourself! 🎉"
            ),
            color=SUCCESS_COLOR,
        )
        success_embed.set_footer(text=guild.name)
        await member.send(embed=success_embed)
    except discord.Forbidden:
        pass

# ─── Member leaves — notify private staff channel ─────────────────────────────
@client.event
async def on_member_remove(member: discord.Member):
    guild = member.guild

    # Post ONLY to private #mod-log
    log_channel = discord.utils.get(guild.text_channels, name=GOODBYE_CHANNEL)
    if not log_channel:
        return

    roles = [r.name for r in member.roles if r.name != "@everyone"]
    embed = discord.Embed(
        title="📤 Member Left",
        description=f"**{member.display_name}** has left the server.",
        color=GOODBYE_COLOR,
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name="📅 Joined",
        value=member.joined_at.strftime("%d %b %Y") if member.joined_at else "Unknown",
        inline=True,
    )
    embed.add_field(name="👥 Members now", value=str(guild.member_count), inline=True)
    embed.add_field(
        name="🏷️ Roles held",
        value=", ".join(roles) if roles else "None",
        inline=False,
    )
    embed.set_footer(text=f"User ID: {member.id}")
    await log_channel.send(embed=embed)

# ── Commands ──────────────────────────────────────────────────────────────────

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    content = message.content.lower().strip()

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
