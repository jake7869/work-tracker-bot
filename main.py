import os
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
from dotenv import load_dotenv
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Get env variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = os.getenv("PANEL_CHANNEL_ID")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
LEADERBOARD_CHANNEL_ID = os.getenv("LEADERBOARD_CHANNEL_ID")
BACKUP_CHANNEL_ID = os.getenv("BACKUP_CHANNEL_ID")

# Check for missing env vars
required_vars = {
    "DISCORD_BOT_TOKEN": TOKEN,
    "PANEL_CHANNEL_ID": PANEL_CHANNEL_ID,
    "LOG_CHANNEL_ID": LOG_CHANNEL_ID,
    "LEADERBOARD_CHANNEL_ID": LEADERBOARD_CHANNEL_ID,
    "BACKUP_CHANNEL_ID": BACKUP_CHANNEL_ID
}
missing = [k for k, v in required_vars.items() if not v]
if missing:
    raise ValueError(f"Missing environment variables: {', '.join(missing)}")

# Convert channel IDs to int
PANEL_CHANNEL_ID = int(PANEL_CHANNEL_ID)
LOG_CHANNEL_ID = int(LOG_CHANNEL_ID)
LEADERBOARD_CHANNEL_ID = int(LEADERBOARD_CHANNEL_ID)
BACKUP_CHANNEL_ID = int(BACKUP_CHANNEL_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory user data (you can replace this with a DB later)
user_data = {}

# Save leaderboard backup
def backup_leaderboard():
    now = datetime.utcnow()
    filename = f"leaderboard_backup_{now.strftime('%Y-%m')}.json"
    with open(filename, "w") as f:
        json.dump(user_data, f)
    return filename

# Button view
class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Clock In", style=discord.ButtonStyle.green, custom_id="clock_in"))
        self.add_item(Button(label="Clock Out", style=discord.ButtonStyle.red, custom_id="clock_out"))
        self.add_item(Button(label="Upgrade Car", style=discord.ButtonStyle.blurple, custom_id="upgrade_car"))
        self.add_item(Button(label="Install Part", style=discord.ButtonStyle.gray, custom_id="install_part"))

# Interaction handler
@bot.event
async def on_interaction(interaction: discord.Interaction):
    user = interaction.user
    action = interaction.data.get("custom_id")

    if action not in ["clock_in", "clock_out", "upgrade_car", "install_part"]:
        return

    user_data.setdefault(str(user.id), {"name": user.display_name, "actions": {}})
    user_record = user_data[str(user.id)]

    user_record["actions"].setdefault(action, 0)
    user_record["actions"][action] += 1

    # Log it
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(f"**{user.display_name}** clicked `{action}` at {datetime.utcnow().isoformat()}")

    # Acknowledge
    await interaction.response.send_message(f"You clicked **{action.replace('_', ' ').title()}**!", ephemeral=True)

    # Update leaderboard
    await update_leaderboard()

# Update leaderboard
async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    sorted_users = sorted(user_data.items(), key=lambda x: sum(x[1]["actions"].values()), reverse=True)

    lines = []
    for i, (uid, data) in enumerate(sorted_users[:10], 1):
        total = sum(data["actions"].values())
        lines.append(f"**{i}. {data['name']}** - {total} actions")

    content = "__**Leaderboard**__\n" + "\n".join(lines) if lines else "No activity yet."
    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.edit(content=content)
            return
    await channel.send(content)

# Setup permanent panel
async def ensure_panel():
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    async for msg in panel_channel.history(limit=10):
        if msg.author == bot.user:
            await msg.edit(content="**Work Tracker Panel**", view=PanelView())
            return
    await panel_channel.send("**Work Tracker Panel**", view=PanelView())

# Monthly reset
@tasks.loop(hours=1)
async def check_monthly_reset():
    now = datetime.utcnow()
    if now.day == 1 and now.hour == 0:
        filename = backup_leaderboard()
        backup_channel = bot.get_channel(BACKUP_CHANNEL_ID)
        await backup_channel.send("Monthly leaderboard backup", file=discord.File(filename))
        user_data.clear()
        await update_leaderboard()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}!")
    await ensure_panel()
    check_monthly_reset.start()

bot.run(TOKEN)
