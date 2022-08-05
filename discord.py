from typing import Union

import disnake
from disnake.ext import tasks, commands
from disnake.ext.commands import Bot
from pathlib import Path
import json
from main import main as track_stock, get_abbreviations as get_abbr, add_abbreviations as add_abbr

config_path = Path(__file__).parent / "bot_config.json"
if config_path.exists():
    with open(config_path) as file:
        config = json.load(file)
else:
    raise Exception(f"Config is not available at {config_path=}")

intents = disnake.Intents(message_content=True, messages=True)

stock_data = {"time": None, "stock": {}}

bot = Bot(command_prefix=commands.when_mentioned_or(config["prefix"]), intents=intents)

weekday_id = {0: "monday",
              1: "tuesday",
              2: "wednesday",
              3: "thursday",
              4: "friday",
              5: "saturday",
              6: "sunday"}


@bot.event
async def on_ready() -> None:
    """
    The code in this even is executed when the bot is ready
    """
    print(f"Logged in as {bot.user.name}")
    print(f"disnake API version: {disnake.__version__}")
    print("-------------------")
    for server in bot.guilds:
        if server.id not in config["valid_servers"]:
            await server.leave()
    if not tracking_task.is_running():
        tracking_task.start()


@bot.event
async def on_server_join(server):
    if server.id not in config["valid_servers"]:
        await server.leave()


@tasks.loop(minutes=1.0)
async def tracking_task():
    try:
        await bot.wait_until_ready()
        response, time = track_stock()
        print(f"{str(time)}, {response}")
        # print(response)

        alert_channel = await bot.fetch_channel(config["channels"]["test"]["alert"])
        # print(f"{alert_channel=}")
        stock_channel = await bot.fetch_channel(config["channels"]["test"]["stock_update"])
        # print(f"{stock_channel=}")
        reveal_channel = await bot.fetch_channel(config["channels"]["test"]["reveal"])
        # print(f"{reveal_channel=}")

        alerts = response.get("alert", {})
        stock = response.get("stock", {})
        next_le = response.get("next_upcoming_LE", {})

        global stock_data
        stock_data = {"time": time, "stock": stock}

        if len(alerts) != 0:
            early_access_over = alerts.get("ea_over", {})
            available_again = alerts.get("back", {})
            sold_out = alerts.get("sold_out", {})
            stock_level = alerts.get("stock_level", {})

            message = empty_message = ""

            if len(early_access_over) != 0:
                for title in early_access_over:
                    message += f"Early Access Phase of **{title}** is over, remaining stock: {early_access_over[title]}\n"

            if len(available_again) != 0:
                for title in available_again:
                    message += f"**{title}** is available again, with a stock of {available_again[title]}\n"

            if len(sold_out) != 0:
                for title in sold_out:
                    message += f"**{title}** sold out!\n"

            if len(stock_level) != 0:
                for title in stock_level:
                    message += f"Stock of **{title}** went below {stock_level[title]}, grab it while you can!\n"

            if message != empty_message:
                await alert_channel.send(message)

        if len(stock) != 0:
            time_for_regular_alert = check_time_for_regular_alert(current_time=time)
            if time_for_regular_alert:
                embed = disnake.Embed(
                    title=f"**Regular Stock Update for {time.strftime('%B %d %H:%M')} CET**",
                    colour=0xF0C43F,
                )
                # message = empty_message = ""
                data_available = False
                for title in stock:
                    embed.add_field(name=f'{title}',
                                    value=f'> Stock: {stock[title]}',
                                    inline=False)
                    data_available = True
                    # message += f"current stock for '{title}':  {stock[title]}\n"
                if data_available:
                    embed.timestamp = time
                    await stock_channel.send(embed=embed)
                    store_last_alert(timestamp=time.timestamp())

        if len(next_le) != 0:
            import requests
            from io import BytesIO
            title = next_le["title"]
            start_date = next_le["startDate"]
            image_url = next_le["image"]
            # await reveal_channel.send(content=title)
            # await reveal_channel.send(content=title, file=disnake.File(image_url))

            # message = f"{title}\n{image_url}"
            # await reveal_channel.send(message)
            date = start_date.split()[0].split("-")
            image_data = BytesIO(requests.get(image_url).content)
            image_file = disnake.File(image_data, filename="reveal.jpg")
            await reveal_channel.send(content=f"{date[1]}/{date[2]}/{date[0]} - {title}", file=image_file)
    except Exception as error:
        print(error)


def get_general_alert_config() -> dict:
    try:
        with open(Path(__file__).parent / "data/general_alerts.json") as json_file:
            data = json.load(json_file)
    except Exception as err:
        print("Error in get_general_alert_config:", err)
        data = {}
    return data


def store_last_alert(timestamp):
    data = get_general_alert_config()
    filepath = Path(__file__).parent / "data/general_alerts.json"
    if not filepath.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w+') as json_file:
        data["last_timestamp"] = timestamp
        json.dump(data, json_file, indent=4)


def check_time_for_regular_alert(current_time) -> bool:
    general_alert = get_general_alert_config()
    deltas = general_alert.get("delta", {})
    relevant_deltas = deltas.get("everyday", [])
    midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    # include the day specific alerts
    relevant_deltas.extend(deltas.get(weekday_id[current_time.weekday()], []))
    if len(relevant_deltas) <= 0:
        return False
    else:
        import datetime
        last_alert = general_alert.get("last_timestamp", None)
        last_alert_delta = None
        if last_alert is not None:
            import pytz
            # convert the total seconds to a timedelta object
            last_alert = datetime.datetime.fromtimestamp(last_alert, tz=pytz.timezone('CET'))
            last_alert_delta = last_alert - midnight
        relevant_deltas = sorted(relevant_deltas)
        relevant_deltas = [datetime.timedelta(seconds=total_seconds) for total_seconds in relevant_deltas]
        current_delta = current_time - midnight
        for alert_delta in relevant_deltas:
            if current_delta >= alert_delta:
                if last_alert_delta is None or last_alert_delta < alert_delta:
                    return True
        return False


@bot.slash_command(description="Returns the current cache of the stock level")
async def stock(inter):
    if not inter.guild:
        if inter.author.id not in config["owners"]:
            return
    await inter.response.defer()
    try:
        embed = disnake.Embed(
            title="**Stock Report**",
            colour=0xF0C43F,
        )
        if len(stock_data["stock"]) != 0:
            for title in stock_data["stock"]:
                embed.add_field(name=f'{title}',
                                value=f'> Stock: {stock_data["stock"][title]}',
                                inline=False)
            embed.timestamp = stock_data["time"]
        else:
            embed.description = "sorry, no stock data available"
        await inter.edit_original_message(embed=embed)
    except Exception as ignore:
        await inter.edit_original_message("Sorry, an error occurred during processing")


@tracking_task.before_loop  # it's called before the actual task runs
async def before_tracking_task():
    await bot.wait_until_ready()


@bot.slash_command(description="Plot the stock evolution for one Displate Limited-Edition")
async def plot(inter, displate_name: str):
    if not inter.guild:
        if inter.author.id not in config["owners"]:
            return
    await inter.response.defer()
    try:
        from plot import plot_stock_history
        try:
            image = plot_stock_history(name=displate_name, style="seaborn-dark", print_to_console=False)
            await inter.edit_original_message(file=disnake.File(image, "image.png"))
            # await inter.response.send_message(file=disnake.File(image, "image.png"))
        except FileNotFoundError as error:
            await inter.edit_original_message("Sorry, I do not have the data for this displate")
            # await inter.response.send_message("Sorry, I do not have the data for this displate")
    except Exception as ignore:
        await inter.edit_original_message("Sorry, an error occurred during processing")
        # await inter.response.send_message("Sorry, an error occurred during processing")


@bot.slash_command(description="Plot and compare the stock evolution for two Displate Limited-Editions")
async def compare(inter,
                  displate_1: str,
                  displate_2: str,
                  # displate_3: Union[str, None] = None,
                  # displate_4: Union[str, None] = None,
                  # displate_5: Union[str, None] = None,
                  # displate_6: Union[str, None] = None,
                  # displate_7: Union[str, None] = None,
                  # displate_8: Union[str, None] = None,
                  # displate_9: Union[str, None] = None,
                  ):
    if not inter.guild:
        if inter.author.id not in config["owners"]:
            return
    await inter.response.defer()
    try:
        names = [displate_1, displate_2]
        print(f"{names=}")
        from plot import plot_compare
        try:
            image = plot_compare(names=names, style="seaborn-dark")
            await inter.edit_original_message(file=disnake.File(image, "image.png"))
        except FileNotFoundError as error:
            await inter.edit_original_message("Sorry, I do not have the data to compare these displates")
    except Exception as ignore:
        await inter.edit_original_message("Sorry, an error occurred during processing")


@bot.slash_command(description="get all abbreviations used by the Discord Tracker.")
async def get_abbreviations(inter, title: Union[str, None] = None):
    if not inter.guild:
        if inter.author.id not in config["owners"]:
            return
    await inter.response.defer()
    abbreviations = get_abbr()
    try:
        embed = disnake.Embed(
            # title="**Stock Report**",
            colour=0xF0C43F,
        )
        if len(abbreviations) != 0:
            for key in abbreviations:
                if title is None or title == abbreviations[key]:
                    embed.add_field(name=f'{abbreviations[key]}',
                                    value=f'> abbreviation: {key}',
                                    inline=False)
        else:
            embed.description = "sorry, no abbreviations available"
        await inter.edit_original_message(embed=embed)
    except Exception as ignore:
        await inter.edit_original_message("Sorry, an error occurred during processing")


@bot.slash_command(description="Plot and compare the stock evolution for two Displate Limited-Editions")
async def add_abbreviation(inter, abbreviation, full_name):
    if not inter.guild:
        if inter.author.id not in config["owners"]:
            return
    await inter.response.defer()
    success = add_abbr(abbreviation=abbreviation, title=full_name)
    if success:
        await inter.edit_original_message(f"I have added the abbreviation '{abbreviation}' for the title '{full_name}'")
    else:
        await inter.edit_original_message(f"I have **not** added the abbreviation '{abbreviation}'"
                                          f" for the title '{full_name}'. \n"
                                          f"Probably the given title is not included in the available data.")

    pass


bot.run(config["token"])
