# FULL CODE — PART 1
import discord
from discord.ext import commands
import os
from datetime import datetime, timedelta
from collections import defaultdict

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

work_data = defaultdict(lambda: {
    "clocked_in": False,
    "last_clock_in": None,
    "car": 0,
    "bike": 0,
    "engine": 0,
    "car_full": 0,
    "bike_full": 0,
    "repair": 0,
    "earnings": 0,
    "total_time": 0
})

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))

PRICE_CONFIG = {
    "car": 30000,
    "bike": 30000,
    "engine": 300000,
    "car_full": 700000,
    "bike_full": 300000,
    "repair": 15000
}

class ResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="⚠️ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only admins can reset the leaderboard.", ephemeral=True)
            return
        work_data.clear()
        await interaction.response.send_message("✅ Leaderboard has been reset.", ephemeral=True)
        await update_leaderboard()
# FULL CODE — PART 2 (continued)
class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are already clocked in.", ephemeral=True)
        else:
            work_data[user_id]["clocked_in"] = True
            work_data[user_id]["last_clock_in"] = datetime.utcnow()
            await interaction.response.send_message("You clocked in!", ephemeral=True)
            await log_action(f"{interaction.user.mention} Clocked In at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are not clocked in.", ephemeral=True)
        else:
            start = work_data[user_id]["last_clock_in"]
            duration = (datetime.utcnow() - start).total_seconds()
            work_data[user_id]["total_time"] += duration
            work_data[user_id]["clocked_in"] = False
            work_data[user_id]["last_clock_in"] = None
            await interaction.response.send_message("You clocked out!", ephemeral=True)
            await log_action(f"{interaction.user.mention} Clocked Out at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You must clock in before performing this action.", ephemeral=True)
            return
        work_data[user_id][action] += 1
        work_data[user_id]["earnings"] += PRICE_CONFIG[action]
        await interaction.response.send_message(f"{action.replace('_', ' ').title()} recorded!", ephemeral=True)
        await log_action(f"{interaction.user.mention} performed {action.replace('_', ' ').title()} at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        await update_leaderboard()
        # FULL CODE — PART 3 (continued)
    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car")
    async def upgrade_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike")
    async def upgrade_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine")
    async def engine_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.secondary, custom_id="car_full")
    async def car_full_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.secondary, custom_id="bike_full")
    async def bike_full_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike_full")

    @discord.ui.button(label="Repair", style=discord.ButtonStyle.primary, custom_id="repair")
    async def repair_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "repair")

    @discord.ui.button(label="🔄 Refresh Leaderboard", style=discord.ButtonStyle.secondary, custom_id="refresh_leaderboard")
    async def refresh_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can refresh the leaderboard.", ephemeral=True)
            return
        await update_leaderboard()
        await interaction.response.send_message("✅ Leaderboard refreshed!", ephemeral=True)

    @discord.ui.button(label="⚠️ Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard")
    async def reset_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to reset the leaderboard.", ephemeral=True)
            return
        await interaction.response.send_message("⚠️ Are you sure you want to reset the leaderboard?", view=ResetView(), ephemeral=True)
        # FULL CODE — PART 4 (end of file)
async def log_action(message: str):
    try:
        channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(message)
    except Exception as e:
        print(f"Logging failed: {e}")

async def update_leaderboard():
    try:
        channel = await bot.fetch_channel(LEADERBOARD_CHANNEL_ID)
    except:
        print("❌ LEADERBOARD_CHANNEL_ID is invalid or missing.")
        return

    leaderboard = sorted(work_data.items(), key=lambda x: x[1]["earnings"], reverse=True)

    lines = []
    total_earned = 0

    for user_id, data in leaderboard:
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.name
        except:
            name = f"<@{user_id}>"

        earned = data['earnings']
        total_earned += earned
        time_str = str(timedelta(seconds=int(data["total_time"])))

        lines.append(
            f"{name}\n"
            f"  🚗 Car: {data['car']} | 🛵 Bike: {data['bike']} | 🛠️ Engine: {data['engine']}\n"
            f"  🚙 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']} | 🔧 Repair: {data['repair']}\n"
            f"  💳 Earnings: £{earned:,} | ⏱️ Time: {time_str}\n"
        )

    leaderboard_text = "🏆 Work Leaderboard\n\n" + "\n".join(lines) + f"\n💰 Total Earnings: £{total_earned:,}"

    async for msg in channel.history(limit=5):
        if msg.author == bot.user:
            await msg.delete()

    await channel.send(f"```{leaderboard_text}```")

    async for msg in channel.history(limit=5):
        if msg.author == bot.user and msg.embeds:
            await msg.delete()

    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(WorkPanel())
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Panel**", view=WorkPanel())
        await update_leaderboard()

if not DISCORD_BOT_TOKEN:
    raise ValueError("❌ DISCORD_BOT_TOKEN not set in environment variables.")

bot.run(DISCORD_BOT_TOKEN)
