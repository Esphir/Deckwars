from commands import bot


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - {bot.user.id}')
    try:
        synced = await bot.tree.sync()
        print(f'synced {len(synced)} commands(s)')
    except Exception as e:
        print(e)


bot.run()
