# Displate-Tracker
Track and visualise the stock of Displate Limited Editions, comes with an optional discord bot


### Setting up the Python Evironment

Using Python 3.9 is recommended as it is also used during development.
The usage of a virtual environment (venv) or Anaconda environment is recommended as well.  
To create a new Anaconda environment, use `conda create -n displate-tracker python=3.9`.  
To activate it, use `conda activate displate-tracker`.  
To install all required packages, simple run `pip install -r requirements.txt` inside the activated environment.

### Running only the tracker
To run the tracker itself, the main.py by using `python main.py` inside the activated environment.
By default, an interval of 1 minute is used between requesting new data from Displate itself.

### Running the tracker wrapped in a discord bot
Before the discord bot can be used, you have to manually create one and add its token to the [bot_config.json](bot_config.json) file. To create a discord bot and getting the token and inviting the bot to a server, just follow the guide from the [disnake documentation](https://docs.disnake.dev/en/stable/discord.html).  
After the bot is configured, simply run the discord.py file by using `python discord.py`.
Again, an interval of 1 minute is used between requesting new data from Displate itself.


### Plotting the data
To plot the stock evolution for one Displate, just run `python plot.py TITLE` with TITLE being the title of a Limited Edition for which data has been collected.
For **Ragnarok is coming** the command looks like this: `python plot.py "Ragnarok is coming"`.  
To compare multiple Limited Editions, just provide more than one title. The command should then be structured like this: `python plot.py TITLE_1 TITLE_2`, with TITLE_1 and TITLE_2 being the distinct titles of the Limited Edition which should be compared.
