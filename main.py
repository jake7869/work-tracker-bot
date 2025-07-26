import discord
from discord.ext import tasks
import asyncio
import datetime

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

channel_id = 1344409201123786758
log_channel_id = 1390028891791298731
leaderboard_channel_id = 1364065995408281651
admin_role_id = 1391785348262264925

TASK_LABELS = {
    "car": "🚗 Car Full Upgrades",
    "bike": "🏍️ Bike Full Upgrades",
    "engine": "⚙️ Engine Upgrades",
    "car_part": "❎ Car Parts",
    "bike_part": "💪 Bike Parts"
}

TASK_PRICES = {
    "car": 500000,
    "bike": 250000,
    "engine": 250000,
    "car_part": 20000,
    "bike_part": 20000
}

data = {}
clocked_in_users = {}
strikes = {}

class WorkButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in"))
        self.add_item(discord.ui.Button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out"))
        self.add_item(discord.ui.Button(label="Car Full Upgrade", style=discord.ButtonStyle.primary, custom_id="car"))
        self.add_item(discord.ui.Button(label="Bike Full Upgrade", style=discord.ButtonStyle.primary, custom_id="bike"))
        self.add_item(discord.ui.Button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine"))
        self.add_item(discord.ui.Button(label="Car Part", style=discord.ButtonStyle.secondary, custom_id="car_part"))
        self.add_item(discord.ui.Button(label="Bike Part", style=discord.ButtonStyle.secondary, custom_id="bike_part"))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)
    await channel.purge()
    await channel.send("**Work Tracker Panel**", view=WorkButtons())
    auto_clock_out.start()
    await update_leaderboard(bot.get_guild(channel.guild.id))

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        user_id = str(interaction.user.id)
        guild = interaction.guild

        if interaction.data["custom_id"] == "clock_in":
            if user_id in clocked_in_users:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ You are already clocked in.", ephemeral=True)
                return
            clocked_in_users[user_id] = datetime.datetime.utcnow()
            if user_id not in data:
                data[user_id] = {task: 0 for task in TASK_LABELS}
                data[user_id]["time"] = 0
                data[user_id]["total"] = 0
            await update_leaderboard(guild)
            if not interaction.response.is_done():
                await interaction.response.send_message("🟢 You are now clocked in.", ephemeral=True)
            await log_action(f"🟢 {interaction.user.mention} clocked in.")

        elif interaction.data["custom_id"] == "clock_out":
            if user_id not in clocked_in_users:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ You are not clocked in.", ephemeral=True)
                return
            delta = (datetime.datetime.utcnow() - clocked_in_users[user_id]).total_seconds()
            data[user_id]["time"] += delta
            del clocked_in_users[user_id]
            await update_leaderboard(guild)
            if not interaction.response.is_done():
                await interaction.response.send_message("🔴 You are now clocked out.", ephemeral=True)
            await log_action(f"🔴 {interaction.user.mention} clocked out.")

        else:
            if user_id not in clocked_in_users:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ You must clock in first.", ephemeral=True)
                return
            task = interaction.data["custom_id"]
            data.setdefault(user_id, {task: 0 for task in TASK_LABELS})
            data[user_id][task] += 1
            data[user_id]["total"] += TASK_PRICES[task]
            await update_leaderboard(guild)
            await log_action(f"✅ {interaction.user.mention} completed **{TASK_LABELS[task]}** (+£{TASK_PRICES[task]:,})")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"✅ Logged: {TASK_LABELS[task]}", ephemeral=True)

async def log_action(message):
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        await log_channel.send(message)

async def update_leaderboard(guild):
    leaderboard_channel = bot.get_channel(leaderboard_channel_id)
    if not leaderboard_channel:
        return

    await leaderboard_channel.purge()

    embed = discord.Embed(title="🏆 Work Leaderboard", color=discord.Color.green())
    sorted_data = sorted(data.items(), key=lambda x: x[1]["total"], reverse=True)
    total_money = 0

    for user_id, stats in sorted_data:
        member = guild.get_member(int(user_id))
        if not member:
            continue

        status = "🟢" if user_id in clocked_in_users else "🔴"
        time_worked = data[user_id]["time"]
        if user_id in clocked_in_users:
            time_worked += (datetime.datetime.utcnow() - clocked_in_users[user_id]).total_seconds()
        time_str = str(datetime.timedelta(seconds=int(time_worked)))

        embed.add_field(
            name=f"{status} {member.display_name}",
            value=(
                f"💰 £{stats['total']:,}\n"
                f"⏱️ Time Worked: {time_str}\n"
                f"🚗 Car Full Upgrades: {stats['car']}\n"
                f"🏍️ Bike Full Upgrades: {stats['bike']}\n"
                f"⚙️ Engine Upgrades: {stats['engine']}\n"
                f"❎ Car Parts: {stats['car_part']}\n"
                f"💪 Bike Parts: {stats['bike_part']}"
            ),
            inline=False
        )
        total_money += stats["total"]

    embed.add_field(name="🏛️ Money in Bank", value=f"£{int(total_money / 2):,}", inline=False)
    await leaderboard_channel.send(embed=embed)

@tasks.loop(seconds=30)
async def auto_clock_out():
    now = datetime.datetime.utcnow()
    to_remove = []

    for user_id, clocked_in_time in list(clocked_in_users.items()):
        delta = (now - clocked_in_time).total_seconds()

        if delta >= 5400 and delta < 7200:
            user = await bot.fetch_user(int(user_id))
            try:
                await user.send("⚠️ You’ve been clocked in for 90 minutes. Reply to this DM within 30 minutes or you’ll be clocked out and penalized.")
            except:
                pass

        elif delta >= 7200:
            user = await bot.fetch_user(int(user_id))
            data[user_id]["time"] = max(data[user_id]["time"] - 0, 0)
            strikes[user_id] = strikes.get(user_id, 0) + 1
            await log_action(f"⛔ {user.mention} was auto-clocked out after 2 hours. Strike {strikes[user_id]} applied. <@&{admin_role_id}>")
            try:
                await user.send(f"⛔ You were clocked out for being inactive. You now have {strikes[user_id]} strike(s).")
            except:
                pass

            if strikes[user_id] >= 3:
                del data[user_id]
                strikes[user_id] = 0
                await log_action(f"❌ {user.mention} reached 3 strikes. Leaderboard data wiped. <@&{admin_role_id}>")

            to_remove.append(user_id)

    for user_id in to_remove:
        if user_id in clocked_in_users:
            del clocked_in_users[user_id]

bot.run("YOUR_TOKEN_HERE")
