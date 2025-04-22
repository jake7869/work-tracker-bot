
import os
import json
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
from datetime import datetime, timedelta

# --- ENV VARS ---
def get_env_var(name, required=True, is_int=False):
    val = os.getenv(name)
    if val is None:
        if required:
            print(f"[ERROR] Missing env var: {name}")
        return None
    return int(val) if is_int else val

DISCORD_BOT_TOKEN = get_env_var("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = get_env_var("PANEL_CHANNEL_ID", is_int=True)
LOG_CHANNEL_ID = get_env_var("LOG_CHANNEL_ID", is_int=True)
LEADERBOARD_CHANNEL_ID = get_env_var("LEADERBOARD_CHANNEL_ID", is_int=True)
BACKUP_CHANNEL_ID = get_env_var("BACKUP_CHANNEL_ID", is_int=True)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

PRICES = {
    "car": 850000,
    "bike": 300000,
    "carpart": 50000,
    "bikepart": 50000,
    "engine": 500000,
}

DATA_FILE = "leaderboard.json"
CLOCK_FILE = "clock_data.json"

def load_json(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

leaderboard = load_json(DATA_FILE)
clock_data = load_json(CLOCK_FILE)

class WorkPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_clocked_in(self, user_id):
        return str(user_id) in clock_data

    def ensure_user_data(self, user_id, username):
        uid = str(user_id)
        leaderboard.setdefault(uid, {
            "car": 0, "bike": 0, "carpart": 0, "bikepart": 0, "engine": 0, "time": 0, "name": username
        })
        leaderboard[uid]["name"] = username

    async def update_leaderboard_embed(self):
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            return

        sorted_data = sorted(leaderboard.items(), key=lambda x: (
            sum(v * PRICES[k] for k, v in x[1].items() if k in PRICES)
        ), reverse=True)

        embed = discord.Embed(title="🏆 Leaderboard", color=discord.Color.gold())
        for user_id, data in sorted_data:
            total_money = sum(data[k] * PRICES.get(k, 0) for k in PRICES)
            time_str = str(timedelta(seconds=data.get("time", 0)))
            name = data.get("name", f"<@{user_id}>")
            embed.add_field(
                name=f"{name}",
                value=(
                    f"🚗 Car: {data['car']} | 🏍️ Bike: {data['bike']}
"
                    f"🔧 Car Parts: {data['carpart']} | 🛠️ Bike Parts: {data['bikepart']}
"
                    f"⚙️ Engine: {data['engine']}
"
                    f"💰 **£{total_money:,}**
"
                    f"⏱️ Clocked Time: `{time_str}`"
                ),
                inline=False
            )

        async for msg in channel.history(limit=5):
            if msg.author == bot.user and msg.embeds:
                await msg.edit(embed=embed)
                return
        await channel.send(embed=embed)

    async def log_action(self, user, action):
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"{user.mention} {action} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in clock_data:
            clock_data[uid] = datetime.utcnow().timestamp()
            save_json(CLOCK_FILE, clock_data)
            await self.log_action(interaction.user, "Clocked In")
            await interaction.response.send_message("✅ You clocked in!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You're already clocked in!", ephemeral=True)

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid in clock_data:
            clock_in_time = clock_data.pop(uid)
            session_time = int(datetime.utcnow().timestamp() - clock_in_time)
            self.ensure_user_data(uid, interaction.user.display_name)
            leaderboard[uid]["time"] += session_time
            save_json(DATA_FILE, leaderboard)
            save_json(CLOCK_FILE, clock_data)
            await self.log_action(interaction.user, f"Clocked Out (Session: {str(timedelta(seconds=session_time))})")
            await interaction.response.send_message("👋 You clocked out!", ephemeral=True)
            await self.update_leaderboard_embed()
        else:
            await interaction.response.send_message("⚠️ You are not clocked in!", ephemeral=True)

    async def handle_upgrade(self, interaction, category):
        uid = str(interaction.user.id)
        if uid not in clock_data:
            await interaction.response.send_message("⛔ You must clock in before doing that!", ephemeral=True)
            return
        self.ensure_user_data(uid, interaction.user.display_name)
        leaderboard[uid][category] += 1
        save_json(DATA_FILE, leaderboard)
        await self.log_action(interaction.user, f"Performed {category.capitalize().replace('part',' Part')} Upgrade")
        await interaction.response.send_message(f"✅ {category.capitalize().replace('part',' Part')} upgrade logged!", ephemeral=True)
        await self.update_leaderboard_embed()

    @discord.ui.button(label="Car Full Upgrade", style=discord.ButtonStyle.primary, custom_id="car")
    async def car_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_upgrade(interaction, "car")

    @discord.ui.button(label="Bike Full Upgrade", style=discord.ButtonStyle.primary, custom_id="bike")
    async def bike_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_upgrade(interaction, "bike")

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.secondary, custom_id="carpart")
    async def car_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_upgrade(interaction, "carpart")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.secondary, custom_id="bikepart")
    async def bike_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_upgrade(interaction, "bikepart")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.danger, custom_id="engine")
    async def engine_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_upgrade(interaction, "engine")

@bot.command()
async def resetleaderboard(ctx):
    leaderboard.clear()
    save_json(DATA_FILE, leaderboard)
    await ctx.send("📉 Leaderboard has been manually reset.")
    view = WorkPanel()
    await view.update_leaderboard_embed()

@tasks.loop(hours=24)
async def monthly_backup():
    now = datetime.utcnow()
    if now.day == 1:
        filename = f"leaderboard_backup_{now.strftime('%Y_%m')}.json"
        with open(filename, "w") as f:
            json.dump(leaderboard, f, indent=2)
        backup_channel = bot.get_channel(BACKUP_CHANNEL_ID)
        if backup_channel:
            await backup_channel.send("📦 Monthly leaderboard backup", file=discord.File(filename))

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(WorkPanel())
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("🛠️ Work Panel", view=WorkPanel())
    view = WorkPanel()
    await view.update_leaderboard_embed()
    monthly_backup.start()

bot.run(DISCORD_BOT_TOKEN)
