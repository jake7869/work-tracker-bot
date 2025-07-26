import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Select
from discord import app_commands
import asyncio
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

data = {}
clocked_in = {}
strike_count = {}
leaderboard_message = None

CHANNEL_ID = 1234567890  # Replace with your leaderboard channel ID
ADMIN_ROLE_ID = 987654321  # Replace with your admin role ID

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    update_leaderboard.start()

class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Clock In", custom_id="clock_in"))
        self.add_item(Button(label="Clock Out", custom_id="clock_out"))
        self.add_item(Button(label="Car Part", custom_id="car_part"))
        self.add_item(Button(label="Bike Part", custom_id="bike_part"))
        self.add_item(Button(label="Engine Upgrade", custom_id="engine_upgrade"))
        self.add_item(Button(label="Car Full Upgrade", custom_id="car_full"))
        self.add_item(Button(label="Bike Full Upgrade", custom_id="bike_full"))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    now = datetime.utcnow()

    if interaction.data['component_type'] == 2:  # Button press
        button_id = interaction.data['custom_id']

        if user_id not in data:
            data[user_id] = {"name": username, "time": 0, "tasks": {"car": 0, "bike": 0, "engine": 0, "car_part": 0, "bike_part": 0}, "earnings": 0, "status": "🔴"}

        if button_id == "clock_in":
            if user_id in clocked_in:
                await interaction.response.send_message("⚠️ You are already clocked in.", ephemeral=True)
                return
            clocked_in[user_id] = now
            data[user_id]["status"] = "🟢"
            await interaction.response.send_message("✅ You are now clocked in.", ephemeral=True)
            asyncio.create_task(watch_clock(user_id, interaction.user))

        elif button_id == "clock_out":
            if user_id not in clocked_in:
                await interaction.response.send_message("⚠️ You are not clocked in.", ephemeral=True)
                return
            start = clocked_in.pop(user_id)
            worked = (now - start).total_seconds()
            data[user_id]["time"] += worked
            data[user_id]["status"] = "🔴"
            await interaction.response.send_message(f"⏱️ You are now clocked out. Time worked: {int(worked//60)} minutes.", ephemeral=True)

        elif user_id in clocked_in:
            task_map = {
                "car_part": ("Car Parts", "car_part", 20000),
                "bike_part": ("Bike Parts", "bike_part", 20000),
                "engine_upgrade": ("Engine Upgrades", "engine", 250000),
                "car_full": ("Car Full Upgrades", "car", 500000),
                "bike_full": ("Bike Full Upgrades", "bike", 250000),
            }
            if button_id in task_map:
                label, key, amount = task_map[button_id]
                data[user_id]["tasks"][key] += 1
                data[user_id]["earnings"] += amount
                await interaction.response.send_message(f"🛠️ {label} logged. £{amount:,} earned.", ephemeral=True)

        else:
            await interaction.response.send_message("⚠️ You must clock in first.", ephemeral=True)

@tasks.loop(seconds=30)
async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    sorted_data = sorted(data.items(), key=lambda x: x[1]['earnings'], reverse=True)

    embed = discord.Embed(title="🏆 Work Leaderboard")
    total_money = 0
    for uid, info in sorted_data:
        status = info.get("status", "🔴")
        time_worked = str(timedelta(seconds=int(info["time"])))
        earnings = info["earnings"]
        total_money += earnings
        tasks = info["tasks"]
        embed.add_field(
            name=f"{status} {info['name']}",
            value=(
                f"💰 £{earnings:,}\n"
                f"⏱️ Time Worked: {time_worked}\n"
                f"🚗 Car Full Upgrades: {tasks['car']}\n"
                f"🏍️ Bike Full Upgrades: {tasks['bike']}\n"
                f"⚙️ Engine Upgrades: {tasks['engine']}\n"
                f"🛠️ Car Parts: {tasks['car_part']}\n"
                f"💪 Bike Parts: {tasks['bike_part']}"
            ),
            inline=False
        )

    embed.add_field(name="🏛️ Money in Bank", value=f"£{total_money//2:,}", inline=False)

    if leaderboard_message:
        await leaderboard_message.edit(embed=embed)
    else:
        leaderboard_message = await channel.send(embed=embed)


async def watch_clock(user_id, user):
    await asyncio.sleep(7200)  # 2 hours
    if user_id in clocked_in:
        try:
            await user.send("⚠️ You've been clocked in for 2 hours. Please reply or you’ll be auto clocked out in 30 minutes.")
        except:
            pass
        try:
            def check(m): return m.author.id == user.id
            await bot.wait_for("message", timeout=1800, check=check)
        except asyncio.TimeoutError:
            if user_id in clocked_in:
                start = clocked_in.pop(user_id)
                worked = (datetime.utcnow() - start).total_seconds()
                data[user_id]["time"] += worked
                data[user_id]["status"] = "🔴"
                strike_count[user_id] = strike_count.get(user_id, 0) + 1
                if strike_count[user_id] >= 3:
                    data.pop(user_id)
                    strike_count.pop(user_id)
                admin_role = discord.utils.get(user.guild.roles, id=ADMIN_ROLE_ID)
                log_channel = bot.get_channel(CHANNEL_ID)
                if log_channel:
                    await log_channel.send(f"⚠️ {user.mention} auto clocked out. Strike {strike_count.get(user_id, 0)}. {admin_role.mention}")

bot.add_view(WorkButtons())
bot.run("YOUR_BOT_TOKEN")
