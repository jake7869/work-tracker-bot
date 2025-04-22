import os
import discord
from discord.ext import commands
from datetime import datetime

# --- ENV VAR VALIDATION ---
def get_env_var(name, required=True, is_int=False):
    value = os.getenv(name)
    if value is None:
        if required:
            print(f"[ERROR] Environment variable '{name}' is missing.")
        return None
    try:
        return int(value) if is_int else value
    except ValueError:
        print(f"[ERROR] Environment variable '{name}' should be an integer, but got: {value}")
        return None

DISCORD_BOT_TOKEN = get_env_var("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = get_env_var("PANEL_CHANNEL_ID", is_int=True)
LOG_CHANNEL_ID = get_env_var("LOG_CHANNEL_ID", is_int=True)
LEADERBOARD_CHANNEL_ID = get_env_var("LEADERBOARD_CHANNEL_ID", is_int=True)
BACKUP_CHANNEL_ID = get_env_var("BACKUP_CHANNEL_ID", is_int=True)

if not all([DISCORD_BOT_TOKEN, PANEL_CHANNEL_ID, LOG_CHANNEL_ID, LEADERBOARD_CHANNEL_ID, BACKUP_CHANNEL_ID]):
    raise ValueError("One or more environment variables are not set correctly.")

# --- DISCORD SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_states = {}  # Tracks who is clocked in
leaderboard = {}  # Tracks stats

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def ensure_clocked_in(self, interaction):
        if user_states.get(interaction.user.id) != "in":
            await interaction.response.send_message("You need to clock in first before doing that!", ephemeral=True)
            return False
        return True

    async def update_leaderboard(self):
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if channel:
            sorted_lb = sorted(leaderboard.items(), key=lambda x: sum(x[1].values()), reverse=True)
            lines = [f"<@{uid}>: Car Upgrades: {data.get('car', 0)}, Bike Upgrades: {data.get('bike', 0)}, Car Parts: {data.get('carpart', 0)}, Bike Parts: {data.get('bikepart', 0)}"
                     for uid, data in sorted_lb]
            msg = "**Leaderboard**\n" + ("\n".join(lines) if lines else "No activity yet.")

            async for m in channel.history(limit=10):
                if m.author == bot.user:
                    await m.edit(content=msg)
                    return
            await channel.send(msg)

    async def log_action(self, user, action):
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"{user.mention} {action} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_states[interaction.user.id] = "in"
        await self.log_action(interaction.user, "Clocked In")
        await interaction.response.send_message("You clocked in!", ephemeral=True)

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_states.pop(interaction.user.id, None)
        await self.log_action(interaction.user, "Clocked Out")
        await interaction.response.send_message("You clocked out!", ephemeral=True)

    @discord.ui.button(label="Car Full Upgrade", style=discord.ButtonStyle.primary, custom_id="upgrade_car")
    async def upgrade_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_clocked_in(interaction): return
        leaderboard.setdefault(interaction.user.id, {}).setdefault("car", 0)
        leaderboard[interaction.user.id]["car"] += 1
        await self.log_action(interaction.user, "Fully Upgraded Car")
        await interaction.response.send_message("Car fully upgraded!", ephemeral=True)
        await self.update_leaderboard()

    @discord.ui.button(label="Bike Full Upgrade", style=discord.ButtonStyle.primary, custom_id="upgrade_bike")
    async def upgrade_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_clocked_in(interaction): return
        leaderboard.setdefault(interaction.user.id, {}).setdefault("bike", 0)
        leaderboard[interaction.user.id]["bike"] += 1
        await self.log_action(interaction.user, "Fully Upgraded Bike")
        await interaction.response.send_message("Bike fully upgraded!", ephemeral=True)
        await self.update_leaderboard()

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.secondary, custom_id="install_car_part")
    async def car_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_clocked_in(interaction): return
        leaderboard.setdefault(interaction.user.id, {}).setdefault("carpart", 0)
        leaderboard[interaction.user.id]["carpart"] += 1
        await self.log_action(interaction.user, "Installed a Car Part")
        await interaction.response.send_message("Car part installed!", ephemeral=True)
        await self.update_leaderboard()

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.secondary, custom_id="install_bike_part")
    async def bike_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_clocked_in(interaction): return
        leaderboard.setdefault(interaction.user.id, {}).setdefault("bikepart", 0)
        leaderboard[interaction.user.id]["bikepart"] += 1
        await self.log_action(interaction.user, "Installed a Bike Part")
        await interaction.response.send_message("Bike part installed!", ephemeral=True)
        await self.update_leaderboard()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(WorkPanel())

    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=50):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**🛠️ Work Panel**", view=WorkPanel())

bot.run(DISCORD_BOT_TOKEN)
