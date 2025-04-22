import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict

# Load environment variables from Railway (dotenv not needed)
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID"))

# Validate environment variables
if not all([TOKEN, PANEL_CHANNEL_ID, LOG_CHANNEL_ID, LEADERBOARD_CHANNEL_ID, BACKUP_CHANNEL_ID]):
    raise ValueError("One or more environment variables are not set correctly.")

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

data_file = "leaderboard.json"

# Load/save data
def load_data():
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            return json.load(f)
    return defaultdict(lambda: defaultdict(int))

def save_data(data):
    with open(data_file, "w") as f:
        json.dump(data, f)

leaderboard_data = load_data()

# Panel view
class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        buttons = [
            ("✅ Clock In", "clock_in", discord.ButtonStyle.success),
            ("❌ Clock Out", "clock_out", discord.ButtonStyle.danger),
            ("🚗 Car Upgrade", "car_upgrade", discord.ButtonStyle.primary),
            ("🏍️ Bike Upgrade", "bike_upgrade", discord.ButtonStyle.primary),
            ("🔩 Car Part", "car_part", discord.ButtonStyle.secondary),
            ("🏍️ Bike Part", "bike_part", discord.ButtonStyle.secondary)
        ]
        for label, cid, style in buttons:
            self.add_item(Button(label=label, style=style, custom_id=cid))

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        await panel_channel.purge(limit=10)
        await panel_channel.send("**🛠️ Shift Logging & Service Panel**", view=PanelView())
    update_leaderboard.start()
    check_monthly_reset.start()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    cid = interaction.data.get("custom_id")
    user = interaction.user
    if cid:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"{timestamp} - {user.name} clicked `{cid}`"

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(log_msg)

        month = datetime.utcnow().strftime("%Y-%m")
        leaderboard_data.setdefault(month, defaultdict(int))
        leaderboard_data[month][str(user.id)] += 1
        save_data(leaderboard_data)

        await interaction.response.send_message("✅ Logged!", ephemeral=True)

@tasks.loop(minutes=10)
async def update_leaderboard():
    month = datetime.utcnow().strftime("%Y-%m")
    leaderboard = leaderboard_data.get(month, {})
    if not leaderboard:
        return

    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
    lb_text = "**🏆 Monthly Leaderboard**\n"
    for i, (user_id, count) in enumerate(sorted_leaderboard[:10], start=1):
        lb_text += f"{i}. <@{user_id}> — {count} logs\n"

    lb_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if lb_channel:
        async for msg in lb_channel.history(limit=10):
            await msg.delete()
        await lb_channel.send(lb_text)

@tasks.loop(hours=24)
async def check_monthly_reset():
    today = datetime.utcnow().strftime("%d")
    if today == "01":
        last_month = (datetime.utcnow().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        backup = leaderboard_data.get(last_month, {})
        if backup:
            sorted_backup = sorted(backup.items(), key=lambda x: x[1], reverse=True)
            backup_text = f"📦 **{last_month} Leaderboard Backup**\n"
            for i, (user_id, count) in enumerate(sorted_backup, start=1):
                backup_text += f"{i}. <@{user_id}> — {count} logs\n"

            backup_channel = bot.get_channel(BACKUP_CHANNEL_ID)
            if backup_channel:
                await backup_channel.send(backup_text)

        leaderboard_data[datetime.utcnow().strftime("%Y-%m")] = defaultdict(int)
        save_data(leaderboard_data)

# Run bot
bot.run(TOKEN)
