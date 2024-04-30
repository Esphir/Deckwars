import asyncio
import json
import discord
import uuid
from discord.ext import commands
from intents import intents

with open("cards.json", "r") as file:
    card_data = json.load(file)

ratings = {}
ratings_file = "ratings.json"
active_players = {}
duel_data = {}
game_over = False
game_phase = None
print("bot started")

bot = commands.Bot(command_prefix='!', intents=intents, application_id=1040675149348884530)


def assign_card_ids(cards):
    for card in cards:
        card["id"] = f"{card['name']}_{hash(card)}"


# initialize player ratings
def save_ratings(ratings):
    with open(ratings_file, "w") as f:
        json.dump(ratings, f)


# load ratings from a JSON file
def load_ratings():
    try:
        with open(ratings_file, "r") as f:
            ratings_data = json.load(f)
            ratings = {int(key): value for key, value in ratings_data.items()}
            return ratings
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def initialize_ratings(players):
    ratings = load_ratings()
    for player in players:
        if player.id not in ratings:
            ratings[player.id] = 100  # Initial rating of 100
    save_ratings(ratings)
    return ratings


def update_ratings(ratings, winner, loser):
    winner_rating = ratings.get(winner.id, 100)
    loser_rating = ratings.get(loser.id, 100)

    # Calculate rating difference
    rating_difference = loser_rating - winner_rating

    # Determine rating change
    if rating_difference <= 0:
        k = 32
    elif rating_difference <= 100:
        k = 24
    else:
        k = 16

    # Calculate new ratings
    winner_new_rating = winner_rating + k * (1 - (1 / (1 + 10 ** (rating_difference / 400))))
    loser_new_rating = loser_rating - k * (1 / (1 + 10 ** (rating_difference / 400)))

    # Update ratings
    ratings[winner.id] = winner_new_rating
    ratings[loser.id] = loser_new_rating

    save_ratings(ratings)


def get_player_rank(player):
    sorted_players = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
    rank = [player_id for player_id, _ in sorted_players].index(player.id) + 1
    return rank


@bot.command(name='duel')
async def duel(ctx, opponent: discord.Member):
    """
    Challenge another player to a duel!
    Usage: !duel @opponent
    Example: !duel @Sherlock
    """
    global duel_data
    global ratings
    duel_data[ctx.guild.id] = {
        "player1": ctx.author,
        "player2": opponent
    }
    global game_phase
    game_phase = "planning"
    player1 = ctx.author
    player2 = opponent

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        player1: discord.PermissionOverwrite(read_messages=True),
        player2: discord.PermissionOverwrite(read_messages=True)
    }

    if ctx.author.id not in ratings:
        initialize_ratings([ctx.author])
    if opponent.id not in ratings:
        initialize_ratings([opponent])

    duel_channel = await ctx.guild.create_text_channel("duel-room", overwrites=overwrites)

    guild_id = ctx.guild.id

    duel_data[guild_id] = {"player1": player1, "player2": player2, "duel_channel": duel_channel}
    embed = discord.Embed(title="Duel Invitation", color=discord.Color.blurple())
    embed.add_field(name="Duel Room",
                    value=f"A duel room has been opened for {player1.mention} and {player2.mention}."
                          f" Click on this to start: {duel_channel.mention}")

    await ctx.send(embed=embed)

    try:
        await duel_channel.send(f"Challenging {opponent.mention} to a duel!")

        active_players[player1] = {"phase": "planning", "deck": [], "limbo": [], "health": 20}
        active_players[player2] = {"phase": "planning", "deck": [], "limbo": [], "health": 20}

        await duel_channel.send(f"{player1.mention} and {player2.mention}, get ready for a duel!")

        card_embed = discord.Embed(title="List of Cards")
        for card in card_data:
            card_embed.add_field(
                name=card['name'],
                value=f"Attack: {card['attack']}\nHealth: {card['health']}\nAbility: {', '.join(card['ability'])}",
                inline=True
            )

        await duel_channel.send(embed=card_embed)
        await summon_cards(duel_channel, player1, player2)
    finally:
        await asyncio.sleep(6)
        await duel_channel.delete()


async def summon_cards(duel_channel, player1, player2):
    global game_phase
    game_phase = "planning"

    def check(message):
        return ((message.author == player1 or message.author == player2) and message.content.lower() != "done"
                and message.channel == duel_channel)

    for player in [player1, player2]:
        # Start the summoning phase message
        summon_phase_embed = discord.Embed(title=f"Summoning Phase for {player.display_name}",
                                           description="Summon your cards one by one. (Please select 3 cards)",
                                           color=discord.Color.blue())

        # Send the initial summoning phase message
        summon_msg = await duel_channel.send(embed=summon_phase_embed)

        summoned_cards = []

        while len(summoned_cards) < 3:
            try:
                response = await bot.wait_for("message", timeout=120.0, check=check)

                if response.content.lower() == "done":
                    if len(summoned_cards) == 3:
                        break
                    else:
                        done_embed = discord.Embed(title="Summoning Phase",
                                                   description="You need to summon 3 cards before typing 'done'.",
                                                   color=discord.Color.red())
                        await duel_channel.send(embed=done_embed)
                elif player == response.author:
                    card_name = response.content.lower()
                    card = next((c for c in card_data if c["name"].lower() == card_name), None)
                    if card:
                        if card in summoned_cards:
                            duplicate_embed = discord.Embed(title="Summoning Phase",
                                                            description="You can't choose the same card more than "
                                                                        "once.",
                                                            color=discord.Color.red())
                            await duel_channel.send(embed=duplicate_embed)
                        else:
                            if len(summoned_cards) < 3:
                                card["identifier"] = uuid.uuid4()
                                summoned_cards.append(card)
                                summon_success_embed = discord.Embed(title="Summoning Phase",
                                                                     description=f"You summoned {card['name']}.",
                                                                     color=discord.Color.green())
                                await duel_channel.send(embed=summon_success_embed)
                                print(summoned_cards)

                            else:
                                limit_exceeded_embed = discord.Embed(title="Summoning Phase",
                                                                     description="You can't have more than "
                                                                                 "3 cards in your deck.",
                                                                     color=discord.Color.red())
                                await duel_channel.send(embed=limit_exceeded_embed)
                    else:
                        not_in_collection_embed = discord.Embed(title="Summoning Phase",
                                                                description=f"{player.mention} You don't"
                                                                            f" have {card_name} in your collection.",
                                                                color=discord.Color.red())
                        await duel_channel.send(embed=not_in_collection_embed)
                else:
                    unauthorized_embed = discord.Embed(title="Summoning Phase",
                                                       description="Only the mentioned players can summon cards.",
                                                       color=discord.Color.red())
                    await duel_channel.send(embed=unauthorized_embed)
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(title="Summoning Phase",
                                              description="Time's up for this phase!",
                                              color=discord.Color.red())
                await duel_channel.send(embed=timeout_embed)
                break

        active_players[player]["limbo"] = summoned_cards

    await start_game(duel_channel, player1, player2)


async def start_game(duel_channel, player1, player2):
    global game_phase
    global game_over
    while True:
        await start_battle_phase(duel_channel, player1, player2)
        if game_over:
            active_players[player1] = {"limbo": []}
            active_players[player2] = {"limbo": []}
            game_phase = "planning"
            game_over = True
            break
        if await is_game_over(duel_channel, player1, player2):
            active_players[player1] = {"limbo": []}
            active_players[player2] = {"limbo": []}
            game_phase = "planning"
            game_over = True
            break
        elif game_phase == "stopped":
            break


async def is_game_over(duel_channel, player1, player2):
    global game_over
    for card in active_players[player1]["limbo"]:
        if card["health"] <= 0:
            print(player1)
            print(f"removed {card}")
            active_players[player1]["limbo"].remove(card)
            print(active_players[player1]["limbo"])
    for card in active_players[player2]["limbo"]:
        if card["health"] <= 0:
            print(player2)
            print(f"removed {card}")
            active_players[player2]["limbo"].remove(card)
            print(active_players[player2]["limbo"])

    if not active_players[player1]["limbo"] and not active_players[player2]["limbo"]:
        await duel_channel.send("It's a draw! Both players have no cards left. This channel will be deleted shortly.")
        game_over = True
    elif not active_players[player1]["limbo"]:
        await duel_channel.send(f"{player2.mention} has won the match. This channel will be deleted shortly.")
        game_over = True
        update_ratings(ratings, player1, player2)
    elif not active_players[player2]["limbo"]:
        await duel_channel.send(f"{player1.mention} has won the match. This channel will be deleted shortly.")
        game_over = True
        update_ratings(ratings, player1, player2)
    print("Game is not over")
    return game_over


async def start_battle_phase(duel_channel, player1, player2):
    used_identifiers = []

    for attacker, defender in [(player1, player2), (player2, player1)]:
        await duel_channel.send(f"{attacker.mention}, choose a card to attack with:")
        await display_player_cards(duel_channel, attacker)

        attacker_card_name = await get_chosen_card(duel_channel, attacker)
        attacker_card_identifier = next(
            card["identifier"] for card in active_players[attacker]["limbo"]
            if card["name"].lower() == attacker_card_name.lower()
        )

        attacker_card = next(
            c for c in active_players[attacker]["limbo"]
            if c["name"].lower() == attacker_card_name.lower() and c["identifier"] == attacker_card_identifier
        )

        if not attacker_card:
            await duel_channel.send(f"{attacker.mention}, you don't have {attacker_card_name} in your limbo.")
            continue

        await duel_channel.send(f"{defender.mention}, choose a card to defend:")
        await display_player_cards(duel_channel, defender)

        defender_card_name = await get_chosen_card(duel_channel, defender)
        defender_card_identifier = next(
            card["identifier"] for card in active_players[defender]["limbo"]
            if card["name"].lower() == defender_card_name.lower()
        )

        defender_card = next(
            c for c in active_players[defender]["limbo"]
            if c["name"].lower() == defender_card_name.lower() and c["identifier"] == defender_card_identifier
        )

        if not defender_card:
            await duel_channel.send(f"{defender.mention}, you don't have {defender_card_name} in your limbo.")
            continue

        await duel_channel.send(f"{attacker.mention} attacks with {attacker_card['name']}!")
        await duel_channel.send(f"{defender.mention} defends with {defender_card['name']}!")

        # Calculate damage and update health
        attacker_damage = attacker_card["attack"]
        defender_damage = defender_card["attack"]

        attacker_card_copy = attacker_card.copy()
        defender_card_copy = defender_card.copy()

        attacker_card_copy["health"] -= defender_damage
        defender_card_copy["health"] -= attacker_damage

        active_players[attacker]["limbo"] = [
            card if card["identifier"] != attacker_card["identifier"] else attacker_card_copy for card in
            active_players[attacker]["limbo"]]
        active_players[defender]["limbo"] = [
            card if card["identifier"] != defender_card["identifier"] else defender_card_copy for card in
            active_players[defender]["limbo"]]

        used_identifiers.extend([attacker_card_identifier, defender_card_identifier])
        await duel_channel.send(f"{defender_card['name']} took {attacker_damage} damage!")
        await duel_channel.send(f"{attacker_card['name']} took {defender_damage} damage!")

        if await is_game_over(duel_channel, player1, player2):
            break


async def display_player_cards(duel_channel, player):
    player_limbo = active_players[player]["limbo"]

    if not player_limbo:
        embed = discord.Embed(title=f"{player.display_name}'s Available Cards", description="No cards available.",
                              color=discord.Color.blue())
    else:
        embed = discord.Embed(title=f"{player.display_name}'s Available Cards", color=discord.Color.blue())
        for card in player_limbo:
            if card["health"] > 0:
                embed.add_field(
                    name=card['name'],
                    value=f"Attack: {card['attack']}\nHealth: {card['health']}",
                    inline=True

                )

    await duel_channel.send(embed=embed)


# function to get chosen card from the player
async def get_chosen_card(duel_channel, player):
    used_identifiers = []

    def check(message):
        return message.author == player and any(
            card["name"].lower() in message.content.lower() and card["identifier"] not in used_identifiers
            for card in active_players[player]["limbo"]
        )

    try:
        response = await bot.wait_for("message", timeout=120.0, check=check)
        chosen_card_name_lower = next(
            card["name"].lower() for card in active_players[player]["limbo"]
            if card["name"].lower() in response.content.lower() and card["identifier"] not in used_identifiers
        )

        chosen_card_identifier = next(
            card["identifier"] for card in active_players[player]["limbo"]
            if card["name"].lower() == chosen_card_name_lower and card["identifier"] not in used_identifiers
        )

        used_identifiers.append(chosen_card_identifier)

        return chosen_card_name_lower
    except asyncio.TimeoutError:
        await duel_channel.send(f"{player.mention}, time's up to choose a card for the attack!")
        return None


@bot.tree.command(name="ping", description="shows the bot's latency in ms.")
async def ping(interaction: discord.Interaction):
    bot_latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! {bot_latency} ms.")


@bot.tree.command(name="shutdown", description="Shuts down the bot (admin only)")
async def shutdown(interaction: discord.Interaction):
    allowed_user_id = 386162509943668758
    if interaction.user.id == allowed_user_id:
        await interaction.response.send_message("Shutting down the bot.")
        await bot.close()
    else:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.")


@bot.tree.command(name="help", description="displays all commands")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="Bot Commands", color=discord.Color.orange())

    for command in bot.commands:
        embed.add_field(name=f"**__{command.name}:__**", value=command.help, inline=False)

    await interaction.response.send_message(embed=embed)


@bot.command()
async def forcestopgame(ctx):
    """
    Forcefully stops a duel (Admin)
    """
    if ctx.author.guild_permissions.administrator:
        global game_phase
        duel_channel = None

        # Find the duel_channel using its name
        for channel in ctx.guild.channels:
            if isinstance(channel, discord.TextChannel) and channel.name == 'duel-room':
                duel_channel = channel
                break

        if duel_channel is not None:
            game_phase = "stopped"
            await duel_channel.delete()
            await ctx.send("The game has been force stopped, and the duel room has been deleted.")
        else:
            await ctx.send("No active duel room found.")
    else:
        await ctx.send("You need to have the administrator role to use this command.")


@bot.command()
async def forfeit(ctx):
    """
    Forfeit the duel (End the game)
    """
    global duel_data
    guild_id = ctx.guild.id

    if guild_id in duel_data:
        player1 = duel_data[guild_id]["player1"]
        player2 = duel_data[guild_id]["player2"]
        duel_channel = duel_data[guild_id]["duel_channel"]

        if ctx.author not in [player1, player2]:
            await ctx.send("You are not a participant in this duel.")
            return

        await ctx.send("Are you sure you want to forfeit? (y/n)")

        def check(message):
            return message.author == ctx.author and message.content.lower() in ['y', 'n']

        try:
            response = await bot.wait_for("message", timeout=30.0, check=check)
            if response.content.lower() == 'y':
                winner = player2 if ctx.author == player1 else player1
                update_ratings(ratings, winner, ctx.author)
                await duel_channel.send(
                    f"{ctx.author.mention} has forfeited the duel. {winner.mention} "
                    f"wins the match! This channel will be deleted shortly.")
                del duel_data[guild_id]
                await asyncio.sleep(15)
                await duel_channel.delete()
            else:
                await ctx.send("You decided not to forfeit.")
        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond. The forfeit prompt has timed out.")
    else:
        await ctx.send("No active duel found for this guild.")


bot.remove_command("help")


@bot.command(name="help")
async def help(ctx):
    """
    Displays all commands
    """
    embed = discord.Embed(title="Bot Commands", color=discord.Color.orange())

    for command in bot.commands:
        command_name = f"**__{command.name}:__**"
        command_description = command.help
        embed.add_field(name=command_name, value=command_description, inline=False)

    await ctx.send(embed=embed)


@bot.command(name="rank")
async def rank(ctx):
    """
    Check your rating and ranking.
    """
    global ratings

    player_id = ctx.author.id
    print(player_id)

    # Load ratings
    ratings = load_ratings()
    print("Ratings loaded:", ratings)

    # checks if the player has a rating
    if player_id not in ratings:
        await ctx.send("You don't have a rating yet.")
        return

    player_rating = round(ratings[player_id])  # Round the player's rating

    # Sort ratings to get the player's rank
    sorted_ratings = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
    player_rank = [player[0] for player in sorted_ratings].index(player_id) + 1

    # Determine ordinal suffix
    suffix = "th" if 10 <= player_rank % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(player_rank % 10, "th")

    embed = discord.Embed(title="Rating and Ranking", color=discord.Color.gold())
    embed.add_field(name="Your Rating", value=f"{player_rating}", inline=False)
    embed.add_field(name="Your Ranking", value=f"{player_rank}{suffix}", inline=False)

    await ctx.send(embed=embed)
