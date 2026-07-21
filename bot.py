
import discord
import os
import time
import random
import string
from datetime import datetime

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# ── Channel IDs ───────────────────────────────────────────────────────────────

WELCOME_CHANNEL_ID   = 1473104188396409064   # #welcome   — greeting on join
VERIFY_CHANNEL_ID    = 1528095037756538970   # #verify    — code-based verification
ADMIN_LOG_CHANNEL_ID = 1528098394072027187   # #admin-log — private leave notices

# ── Role names ────────────────────────────────────────────────────────────────

VERIFIED_ROLE_NAME   = "Verified"     # Granted after successful verification
UNVERIFIED_ROLE_NAME = "Unverified"   # Assigned on join — blocks all other channels

# ── Colours ───────────────────────────────────────────────────────────────────

EMBED_COLOR   = 0x5865F2   # Blurple  (welcome / verify prompts)
SUCCESS_COLOR = 0x57F287   # Green    (verified confirmation)
GOODBYE_COLOR = 0xED4245   # Red      (leave notification)

# ── In-memory verification store: { member_id: code } ────────────────────────

pending_verifications: dict[int, str] = {}

# ── Intents ───────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members         = True
intents.message_content = True

client = discord.Client(intents=intents)

# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_code(length: int = 6) -> str:
    """Return a random uppercase alphanumeric verification code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


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


# ─── Member joins ─────────────────────────────────────────────────────────────
@client.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    # 1. Assign Unverified role (locks all other channels)
    unverified_role = await get_or_create_role(
        guild, UNVERIFIED_ROLE_NAME, color=discord.Color.greyple()
    )
    await member.add_roles(unverified_role, reason="New member — pending verification")

    # 2. Generate & store unique verification code
    code = generate_code()
    pending_verifications[member.id] = code

    # 3. Rich welcome embed in #welcome channel
    welcome_channel = client.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = discord.Embed(
            title=f"🎉 Welcome to {guild.name}!",
            description=(
                f"Hey {member.mention}, great to have you here!\n\n"
                f"📬 **Check your DMs** — we've sent you a verification code.\n"
                f"Then head to <#{VERIFY_CHANNEL_ID}> and type it to unlock the server. 🔓"
            ),
            color=EMBED_COLOR,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 Member",           value=member.mention,                          inline=True)
        embed.add_field(name="📅 Account Created",  value=member.created_at.strftime("%d %b %Y"),  inline=True)
        embed.add_field(name="🎊 Member #",         value=str(guild.member_count),                 inline=True)
        embed.set_footer(
            text=f"{guild.name} • Check your DMs for your verification code",
            icon_url=guild.icon.url if guild.icon else None,
        )
        await welcome_channel.send(embed=embed)

    # 4. Send code via DM
    dm_sent = False
    try:
        dm_embed = discord.Embed(
            title="🔐 Your Verification Code",
            description=(
                f"Hi **{member.display_name}**, welcome to **{guild.name}**!\n\n"
                f"Go to <#{VERIFY_CHANNEL_ID}> and type the code below to verify yourself:\n\n"
                f"```\n{code}\n```\n"
                f"⚠️ **Do not share this code with anyone.**"
            ),
            color=EMBED_COLOR,
        )
        dm_embed.set_footer(text=f"{guild.name} • Verification System")
        await member.send(embed=dm_embed)
        dm_sent = True
    except discord.Forbidden:
        pass  # Handled below

    # 5. Post prompt in #verify channel
    verify_channel = client.get_channel(VERIFY_CHANNEL_ID)
    if verify_channel:
        if not dm_sent:
            # DMs disabled — show code in channel (auto-deletes after 90s)
            await verify_channel.send(
                f"⚠️ {member.mention} we couldn't DM you.\n"
                f"Your one-time code is:\n```\n{code}\n```\n"
                f"Type it here to verify. *(Deletes in 90 s)*",
                delete_after=90,
            )
        else:
            prompt_embed = discord.Embed(
                title="🔐 Verification Required",
                description=(
                    f"{member.mention}, check your DMs for your unique code,\n"
                    f"then **type it here** to unlock the server. 👇"
                ),
                color=EMBED_COLOR,
                timestamp=datetime.utcnow(),
            )
            prompt_embed.set_thumbnail(url=member.display_avatar.url)
            prompt_embed.set_footer(text="Type your code here — it will be deleted automatically")
            await verify_channel.send(embed=prompt_embed)


# ─── Messages — verification + commands ───────────────────────────────────────
@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # ── Code verification in #verify ──────────────────────────────────────────
    if message.channel.id == VERIFY_CHANNEL_ID:
        user_id    = message.author.id
        typed_code = message.content.strip().upper()

        # Delete the message immediately (keeps channel clean)
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        if user_id not in pending_verifications:
            await message.channel.send(
                f"⚠️ {message.author.mention} No pending verification found. "
                f"If you just joined, please wait a moment or contact an admin.",
                delete_after=8,
            )
            return

        expected = pending_verifications[user_id]

        if typed_code != expected:
            await message.channel.send(
                f"❌ {message.author.mention} Incorrect code. "
                f"Please check your DMs and try again.",
                delete_after=6,
            )
            return

        # ✅ Correct code — grant access
        del pending_verifications[user_id]
        guild  = message.guild
        member = guild.get_member(user_id)
        if not member:
            return

        verified_role   = await get_or_create_role(guild, VERIFIED_ROLE_NAME, color=discord.Color.green())
        unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)

        await member.add_roles(verified_role, reason="Verified via code")
        if unverified_role and unverified_role in member.roles:
            await member.remove_roles(unverified_role, reason="Verification complete")

        await message.channel.send(
            f"✅ {member.mention} You're verified! Welcome to the server! 🎉",
            delete_after=8,
        )

        try:
            success_embed = discord.Embed(
                title="✅ You're Verified!",
                description=(
                    f"You now have full access to **{guild.name}**.\n"
                    f"Enjoy your stay — feel free to introduce yourself! 🎉"
                ),
                color=SUCCESS_COLOR,
            )
            success_embed.set_footer(text=guild.name)
            await member.send(embed=success_embed)
        except discord.Forbidden:
            pass

        return

    # ── !ping command ─────────────────────────────────────────────────────────
    if message.content.lower().strip() == "!ping":
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


# ─── Member leaves — admin log only ──────────────────────────────────────────
@client.event
async def on_member_remove(member: discord.Member):
    pending_verifications.pop(member.id, None)

    log_channel = client.get_channel(ADMIN_LOG_CHANNEL_ID)
    if not log_channel:
        return

    guild = member.guild
    roles = [r.name for r in member.roles if r.name != "@everyone"]

    embed = discord.Embed(
        title="📤 Member Left",
        description=f"**{member.display_name}** (`{member}`) has left the server.",
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


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is not set!")
    client.run(TOKEN)
