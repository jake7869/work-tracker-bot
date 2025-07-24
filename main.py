import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from discord import SelectOption
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# IDs
PANEL_CHANNEL_ID = 1344409201123786758
LEADERBOARD_CHANNEL_ID = 1364065995408281651
LOG_CHANNEL_ID = 1390028891791298731
ADMIN_ROLE_ID = 1391785348262264925

# Data
users_data = {}
message_ids = {"panel": None, "leaderboard": None}

PRICES = {
    "Car Part": 50000,
    "Bike Part": 50000,
    "Car Full Upgrade": 850000,
    "Bike Full Upgrade": 300000,
    "Engine Upgrade": 500000
}

def get_status_emoji(user_id):
    return ":green_circle:" if users_data.get(user_id, {}).get("clocked_in") else ":red_circle:"

def get_username(guild, user_id):
    member = guild.get_member(user_id)
    return member.display_name if member else f"<@{user_id}>"

def format_leaderboard(guild):
    if not users_data:
        return "No data yet."
    
    leaderboard = sorted(users_data.items(), key=lambda x: x[1].get("earnings", 0), reverse=True)
    embed = discord.Embed(title="📊 Work Leaderboard", color=discord.Color.gold())
    total_earned = 0

    for user_id, data in leaderboard:
        name = get_username(guild, user_id)
        emoji = get_status_emoji(user_id)
        earnings = data.get("earnings", 0)
        time_spent = str(data.get("total_time", timedelta()))
        embed.add_field(
            name=f"{emoji} **{name}**",
            value=(
                f"**Time:** {time_spent}\n"
                f"**Car Parts:** {data.get('Car Part', 0)}\n"
                f"**Bike Parts:** {data.get('Bike Part', 0)}\n"
                f"**Car Full Upgrades:** {data.get('Car Full Upgrade', 0)}\n"
                f"**Bike Full Upgrades:** {data.get('Bike Full Upgrade', 0)}\n"
                f"**Engine Upgrades:** {data.get('Engine Upgrade', 0)}\n"
                f"**Total Earned:** £{earnings:,}"
            ),
            inline=False
        )
        total_earned += earnings

    embed.set_footer(text=f"💰 Total Money Earned: £{total_earned:,}")
    return embed

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if message_ids["leaderboard"]:
        try:
            msg = await channel.fetch_message(message_ids["leaderboard"])
            await msg.edit(embed=format_leaderboard(channel.guild))
            return
        except:
            pass
    msg = await channel.send(embed=format_leaderboard(channel.guild))
    message_ids["leaderboard"] = msg.id

async def log_action(content):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(content)

class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ActionButton("Clock In", "green"))
        self.add_item(ActionButton("Clock Out", "red"))
        self.add_item(ActionButton("Car Part", "blurple"))
        self.add_item(ActionButton("Bike Part", "blurple"))
        self.add_item(ActionButton("Car Full Upgrade", "gray"))
        self.add_item(ActionButton("Bike Full Upgrade", "gray"))
        self.add_item(ActionButton("Engine Upgrade", "gray"))
        self.add_item(ActionButton("Reset Leaderboard", "red", admin=True))
        self.add_item(ActionButton("Refresh Leaderboard", "blurple", admin=True))
        self.add_item(AdminDropdown())

class ActionButton(Button):
    def __init__(self, label, color, admin=False):
        super().__init__(label=label, style=getattr(discord.ButtonStyle, color), custom_id=label)
        self.admin = admin

    async def callback(self, interaction: discord.Interaction):
        if self.admin and ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return

        user_id = interaction.user.id
        now = datetime.utcnow()

        if self.label == "Clock In":
            if users_data.get(user_id, {}).get("clocked_in"):
                await interaction.response.send_message("You're already clocked in.", ephemeral=True)
                return
            users_data.setdefault(user_id, {
                "Car Part": 0,
                "Bike Part": 0,
                "Car Full Upgrade": 0,
                "Bike Full Upgrade": 0,
                "Engine Upgrade": 0,
                "earnings": 0,
                "total_time": timedelta(),
                "clocked_in": True,
                "clock_in_time": now
            })
            users_data[user_id]["clocked_in"] = True
            users_data[user_id]["clock_in_time"] = now
            await interaction.response.send_message(f"⏱️ {interaction.user.mention} clocked in at {now}", ephemeral=True)
            await log_action(f"📝 {interaction.user.mention} clocked in at {now}")
        elif self.label == "Clock Out":
            if users_data.get(user_id, {}).get("clocked_in"):
                delta = now - users_data[user_id]["clock_in_time"]
                users_data[user_id]["total_time"] += delta
                users_data[user_id]["clocked_in"] = False
                await interaction.response.send_message(f"✅ {interaction.user.mention} clocked out. Time: {delta}", ephemeral=True)
                await log_action(f"📤 {interaction.user.mention} clocked out. Time: {delta}")
            else:
                await interaction.response.send_message("You're not clocked in.", ephemeral=True)
        elif self.label == "Reset Leaderboard":
            users_data.clear()
            await interaction.response.send_message("Leaderboard reset.", ephemeral=True)
            await log_action(f"🔴 {interaction.user.mention} reset the leaderboard.")
        elif self.label == "Refresh Leaderboard":
            await update_leaderboard()
            await interaction.response.send_message("Leaderboard refreshed.", ephemeral=True)
        else:
            if not users_data.get(user_id, {}).get("clocked_in"):
                await interaction.response.send_message("Please clock in first.", ephemeral=True)
                return
            users_data[user_id][self.label] += 1
            users_data[user_id]["earnings"] += PRICES[self.label]
            await interaction.response.send_message(f"{interaction.user.mention} completed {self.label}.", ephemeral=True)
            await log_action(f"📋 {interaction.user.mention} completed **{self.label}** at {now}")

        await update_leaderboard()

class AdminDropdown(Select):
    def __init__(self):
        options = [
            SelectOption(label="Force Clock Out", value="force_clockout"),
            SelectOption(label="Remove Car Part", value="remove_car_part"),
            SelectOption(label="Remove Car Full Upgrade", value="remove_car_upgrade"),
            SelectOption(label="Remove Bike Part", value="remove_bike_part"),
            SelectOption(label="Remove Bike Full Upgrade", value="remove_bike_upgrade"),
            SelectOption(label="Remove Engine Upgrade", value="remove_engine"),
            SelectOption(label="Remove Time", value="remove_time"),
        ]
        super().__init__(placeholder="Admin Tools", options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        guild = interaction.guild
        members = [m for m in guild.members if not m.bot]

        view = View()
        select = Select(
            placeholder="Select member...",
            options=[SelectOption(label=m.display_name, value=str(m.id)) for m in members],
            min_values=1,
            max_values=1
        )

        async def user_selected(inner_interaction: discord.Interaction):
            target_id = int(select.values[0])
            if target_id not in users_data:
                await inner_interaction.response.send_message("User has no data.", ephemeral=True)
                return

            action = self.values[0]
            data = users_data[target_id]
            name = get_username(interaction.guild, target_id)

            if action == "force_clockout":
                if data.get("clocked_in"):
                    delta = datetime.utcnow() - data["clock_in_time"]
                    data["total_time"] += delta
                    data["clocked_in"] = False
                    await log_action(f"⛔ {interaction.user.mention} forced clock-out of {name}")
                    await inner_interaction.response.send_message("Forced clock out.", ephemeral=True)
            elif action == "remove_time":
                data["total_time"] = timedelta()
                await log_action(f"⏳ {interaction.user.mention} reset total time for {name}")
                await inner_interaction.response.send_message("Time reset.", ephemeral=True)
            else:
                label_map = {
                    "remove_car_part": "Car Part",
                    "remove_car_upgrade": "Car Full Upgrade",
                    "remove_bike_part": "Bike Part",
                    "remove_bike_upgrade": "Bike Full Upgrade",
                    "remove_engine": "Engine Upgrade"
                }
                key = label_map[action]
                if data.get(key, 0) > 0:
                    data[key] -= 1
                    data["earnings"] -= PRICES[key]
                    await log_action(f"🗑️ {interaction.user.mention} removed 1 {key} from {name}")
                    await inner_interaction.response.send_message(f"Removed 1 {key}.", ephemeral=True)
                else:
                    await inner_interaction.response.send_message(f"{key} already 0.", ephemeral=True)

            await update_leaderboard()

        select.callback = user_selected
        view.add_item(select)
        await interaction.response.send_message("Select user to apply action:", view=view, ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        if message_ids["panel"]:
            try:
                msg = await panel_channel.fetch_message(message_ids["panel"])
                await msg.edit(content="**Work Tracker Panel**", view=WorkButtons())
                return
            except:
                pass
        msg = await panel_channel.send("**Work Tracker Panel**", view=WorkButtons())
        message_ids["panel"] = msg.id

    await update_leaderboard()

bot.run(os.getenv("DISCORD_TOKEN"))
