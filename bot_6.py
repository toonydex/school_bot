import discord
from discord.ext import commands
import json
import os
import time
from datetime import datetime, timedelta, timezone

# ─────────────────────────────
# CONFIG
# ─────────────────────────────

TOKEN = ("MTUwNjE2MDYwNDE5MTM5MTk3Ng.GgU4My.Ws-MMs0yOhPfH5bUr4QWU037KwF6yiA9sIBHXw")  # or paste string directly for testing
PREFIX = "!"

DATA_FILE = "points.json"

DEV_ID = 1487316967038652558
WELCOME_CHANNEL_NAME = "welcome"

POINTS_PER_LEVEL = 100
MAX_LEVEL = 150

# ─────────────────────────────
# BOT SETUP
# ─────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ─────────────────────────────
# DATA HANDLING
# ─────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()
spam_tracker = {}

# ─────────────────────────────
# LEVEL SYSTEM
# ─────────────────────────────

def get_level(points):
    return min(points // POINTS_PER_LEVEL, MAX_LEVEL)

def points_to_next_level(points):
    level = get_level(points)
    if level >= MAX_LEVEL:
        return 0
    return POINTS_PER_LEVEL - (points % POINTS_PER_LEVEL)

def progress_bar(points):
    level = get_level(points)
    if level >= MAX_LEVEL:
        return "████████████████████ MAX"

    filled = (points % POINTS_PER_LEVEL) * 20 // POINTS_PER_LEVEL
    return "█" * filled + "░" * (20 - filled)

# ─────────────────────────────
# USER HANDLING
# ─────────────────────────────

def get_user(uid):
    uid = str(uid)

    if uid not in data:
        data[uid] = {
            "points": 0,
            "daily_streak": 0,
            "last_daily": None
        }

    return data[uid]

# ─────────────────────────────
# EVENTS
# ─────────────────────────────

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)

    if channel:
        embed = discord.Embed(
            title=f"🎉 Welcome, {member.display_name}!",
            description=(
                f"Hey {member.mention} 👋\n\n"
                "📌 Read rules\n"
                "💬 Chat & earn XP\n"
                "📈 Use !level to check progress"
            ),
            color=discord.Color.green()
        )

        avatar = member.avatar.url if member.avatar else member.default_avatar.url
        embed.set_thumbnail(url=avatar)
        embed.set_footer(text=f"Member #{member.guild.member_count}")

        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user = get_user(message.author.id)
    old_level = get_level(user["points"])

    # XP gain
    user["points"] += 1
    new_level = get_level(user["points"])

    if new_level > old_level:
        await message.channel.send(
            f"🎉 {message.author.mention} reached **Level {new_level}**!"
        )

    # ───── SPAM DETECTION ─────
    uid = str(message.author.id)
    now = time.time()
    content = message.content.lower().strip()

    spam_tracker.setdefault(uid, [])
    spam_tracker[uid].append((content, now))

    # keep last 10 sec only
    spam_tracker[uid] = [
        (msg, t) for msg, t in spam_tracker[uid]
        if now - t <= 10
    ]

    same_count = sum(1 for msg, _ in spam_tracker[uid] if msg == content)

    if same_count >= 5:
        user["points"] = max(0, user["points"] - 20)
        spam_tracker[uid] = []

        await message.channel.send(
            f"⚠️ {message.author.mention} Spam detected! -20 XP"
        )

    save_data()
    await bot.process_commands(message)

# ─────────────────────────────
# COMMANDS
# ─────────────────────────────

@bot.command()
async def level(ctx, member: discord.Member = None):
    target = member or ctx.author
    user = get_user(target.id)

    pts = user["points"]
    lvl = get_level(pts)

    bar = progress_bar(pts)
    to_next = points_to_next_level(pts)

    if lvl >= MAX_LEVEL:
        progress_text = "🏆 MAX LEVEL"
    else:
        progress_text = f"{pts % POINTS_PER_LEVEL}/{POINTS_PER_LEVEL} XP → next level ({to_next} left)"

    await ctx.send(
        f"📊 **{target.display_name}**\n"
        f"Level: **{lvl}/{MAX_LEVEL}**\n"
        f"XP: **{pts}**\n"
        f"`{bar}`\n"
        f"{progress_text}"
    )

@bot.command()
async def points(ctx, member: discord.Member = None):
    target = member or ctx.author
    user = get_user(target.id)

    await ctx.send(
        f"🏆 **{target.display_name}**\n"
        f"XP: **{user['points']}**\n"
        f"Level: **{get_level(user['points'])}**"
    )

# ─────────────────────────────
# DAILY SYSTEM (FIXED TIMEZONE)
# ─────────────────────────────

@bot.command()
async def daily(ctx):
    user = get_user(ctx.author.id)

    today = datetime.now(timezone.utc).date()

    if user["last_daily"]:
        last = datetime.fromisoformat(user["last_daily"]).date()

        if last == today:
            await ctx.send("❌ You already claimed today.")
            return

        if last == today - timedelta(days=1):
            user["daily_streak"] += 1
        else:
            user["daily_streak"] = 1
    else:
        user["daily_streak"] = 1

    reward = 25 + (user["daily_streak"] * 5)

    old_level = get_level(user["points"])
    user["points"] += reward
    new_level = get_level(user["points"])

    user["last_daily"] = str(today)

    save_data()

    msg = (
        f"🎁 Daily claimed!\n"
        f"+{reward} XP\n"
        f"🔥 Streak: {user['daily_streak']} days\n"
        f"📈 Level: {new_level}"
    )

    if new_level > old_level:
        msg += f"\n🎉 Level up to **{new_level}**!"

    await ctx.send(msg)

# ─────────────────────────────
# LEADERBOARD
# ─────────────────────────────

@bot.command()
async def leaderboard(ctx):
    top = sorted(data.items(), key=lambda x: x[1]["points"], reverse=True)[:5]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    text = "🏆 **Leaderboard**\n\n"

    for i, (uid, info) in enumerate(top):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else "Unknown"

        text += f"{medals[i]} {name} — {info['points']} XP (Lvl {get_level(info['points'])})\n"

    await ctx.send(text)

# ─────────────────────────────
# DONATION SYSTEM
# ─────────────────────────────

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    sender = get_user(ctx.author.id)
    receiver = get_user(member.id)

    if amount <= 0:
        return await ctx.send("❌ Invalid amount.")

    if sender["points"] < amount:
        return await ctx.send("❌ Not enough XP.")

    sender["points"] -= amount
    receiver["points"] += amount

    save_data()

    await ctx.send(f"💸 {ctx.author.mention} → {member.mention}: {amount} XP")

# ─────────────────────────────
# RUN BOT
# ─────────────────────────────

bot.run(TOKEN)
print(TOKEN)