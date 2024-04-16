import discord

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.webhooks = True
intents.guild_messages = True
intents.guild_reactions = True
