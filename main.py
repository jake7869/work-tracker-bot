import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# === CONFIG ===
PANEL_CHANNEL = 1344409201123786758
LOG_CHANNEL = 1390028891791298731
LEADERBOARD_CHANNEL = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

# === TASK INFO ===
TASKS = {
    "car": {"label": "Car Full Upgrade", "emoji": "🚗", "amount": 500_000},
    "bike": {"label": "Bike Full Upgrade", "emoji": "🏍️", "amount": 250_000},
    "engine": {"label": "Engine Upgrade", "emoji": "⚙️", "amount": 250_000},
    "carpart": {"label": "Car Part", "emoji": "🛠️", "amount": 20_000},
    "bikepart": {"label": "Bike Part", "emoji": "💪", "amount": 20_000},
}

# === DATA ===
clocked_in = {}
user_data = {}
strikes = {}
leaderboard_msg_id = None
warning_sent = {}

def format_time(seconds):
    return str(timedelta(seconds=int(seconds)))

async def log_action(msg):
    channel = bot.get_channel(LOG_CHANNEL)
    if channel:
        await channel.send(msg)

async def update_leaderboard():
    global leaderboard_msg_id
    channel = bot.get_channel(LEADERBOARD_CHANNEL)
    if not channel:
        return

    embed = discord.Embed(title="🏆 Work Leaderboard", color=discord.Color.orange())
    total_bank = 0

    for uid, data in user_data.items():
        member = channel.guild.get_member(uid)
        if not member:
            continue
        status = "🟢" if uid in clocked_in else "🔴"
        live_time = data["time"]
        if uid in clocked_in:
            live_time += (datetime.utcnow() - clocked_in[uid]).total_seconds()

        task_lines = "\n".join(
            f"{TASKS[k]['emoji']} {TASKS[k]['label']}: {data.get(k, 0)}" for k in TASKS
        )

        embed.add_field(
            name=f"{status} {member.display_name}",
            value=(
                f"💰 £{data['money']:,}\n"
                f"⏱️ Time Worked: {format_time(live_time)}\n"
                f"{task_lines}"
            ),
            inline=False
        )
        total_bank += data["money"]

    embed.add_field(name="🏛️ Money in Bank", value=f"£{total_bank // 2:,}", inline=False)

    try:
        if leaderboard_msg_id:
            msg = await channel.fetch_message(leaderboard_msg_id)
            await msg.edit(embed=embed)
        else:
            msg = await channel.send(embed=embed)
            leaderboard_msg_id = msg.id
    except:
        msg = await channel.send(embed=embed)
        leaderboard_msg_id = msg.id

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.get_channel(PANEL_CHANNEL).send("**Work Tracker Panel**", view=WorkPanel())
    update_leaderboard.start()
    auto_clockout.start()

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for key, task in TASKS.items():
            self.add_item(discord.ui.Button(label=task["label"], emoji=task["emoji"], style=discord.ButtonStyle.primary, custom_id=key))
        self.add_item(discord.ui.Button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clockin"))
        self.add_item(discord.ui.Button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clockout"))
        self.add_item(discord.ui.Button(label="Reset Leaderboard", style=discord.ButtonStyle.secondary, custom_id="reset"))

@bot.event
async def on_interaction(interaction):
    if not interaction.type == discord.InteractionType.component:
        return
    uid = interaction.user.id
    name = interaction.user.display_name

    if uid not in user_data:
        user_data[uid] = {"money": 0, "time": 0, **{k: 0 for k in TASKS}}

    custom_id = interaction.data["custom_id"]

    if custom_id == "clockin":
        if uid in clocked_in:
            await interaction.response.send_message("❌ You are already clocked in.", ephemeral=True)
            return
        clocked_in[uid] = datetime.utcnow()
        await interaction.response.send_message("🟢 You are now clocked in.", ephemeral=True)
        await log_action(f"🟢 {interaction.user.mention} clocked in.")
        await update_leaderboard()

    elif custom_id == "clockout":
        if uid not in clocked_in:
            await interaction.response.send_message("❌ You are not clocked in.", ephemeral=True)
            return
        delta = (datetime.utcnow() - clocked_in.pop(uid)).total_seconds()
        user_data[uid]["time"] += delta
        warning_sent.pop(uid, None)
        await interaction.response.send_message("🔴 You are now clocked out.", ephemeral=True)
        await log_action(f"🔴 {interaction.user.mention} clocked out. Time added: {format_time(delta)}")
        await update_leaderboard()

    elif custom_id == "reset":
        if ADMIN_ROLE_ID in [role.id for role in interaction.user.roles]:
            user_data.clear()
            clocked_in.clear()
            warning_sent.clear()
            await interaction.response.send_message("♻️ Leaderboard reset.", ephemeral=True)
            await log_action(f"♻️ {interaction.user.mention} reset the leaderboard.")
            await update_leaderboard()
        else:
            await interaction.response.send_message("❌ You are not authorized.", ephemeral=True)

    elif custom_id in TASKS:
        if uid not in clocked_in:
            await interaction.response.send_message("❌ You must clock in first.", ephemeral=True)
            return
        user_data[uid][custom_id] += 1
        user_data[uid]["money"] += TASKS[custom_id]["amount"]
        await interaction.response.send_message(f"✅ {TASKS[custom_id]['label']} logged.", ephemeral=True)
        await log_action(f"{interaction.user.mention} completed **{TASKS[custom_id]['label']}**")
        await update_leaderboard()

@tasks.loop(seconds=60)
async def auto_clockout():
    now = datetime.utcnow()
    for uid, start in list(clocked_in.items()):
        elapsed = (now - start).total_seconds()
        if uid in warning_sent:
            if elapsed >= 10800:  # 2h + 30min warning
                user = bot.get_user(uid)
                strikes[uid] = strikes.get(uid, 0) + 1
                user_data[uid]["time"] = max(0, user_data[uid]["time"] - 0)
                await log_action(f"⛔ {user.mention} was auto-clocked out after no reply. Strike {strikes[uid]} given. <@&{ADMIN_ROLE_ID}>")
                if strikes[uid] >= 3:
                    del user_data[uid]
                    await log_action(f"❌ {user.mention} reached 3 strikes. Data wiped.")
                    strikes[uid] = 0
                try:
                    await user.send(f"⛔ You were auto-clocked out and received Strike {strikes[uid]}.")
                except:
                    pass
                del clocked_in[uid]
                del warning_sent[uid]
                await update_leaderboard()
        elif elapsed >= 7200:  # 2 hours
            user = bot.get_user(uid)
            try:
                await user.send("⚠️ You’ve been clocked in for 2 hours. Reply to stay clocked in or you’ll be removed in 30 minutes.")
                warning_sent[uid] = now
            except:
                pass

@tasks.loop(seconds=60)
async def update_leaderboard():
    await update_leaderboard()

bot.run("YOUR_TOKEN_HERE")
