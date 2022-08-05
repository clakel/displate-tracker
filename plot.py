import csv
import datetime
import json
import io

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import sys


# import numpy as np

def process_file(filepath):
    data = {}
    with open(filepath) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        first_row = True
        for row in csv_reader:
            if not first_row:
                data["time"].append(datetime.datetime.fromtimestamp(float(row[0])))
                data["stock"].append(int(row[1]))
            else:
                data["time"] = []
                data["stock"] = []
                first_row = False
    return data["time"], data["stock"]


def get_metdata(name):
    filepath = Path(__file__).parent / f"data/{name}/metadata.json"
    if filepath.exists():
        with open(filepath) as json_file:
            data = json.load(json_file)
    else:
        data = {}
        print("No data available")
    return data


def get_name_from_abbreviation(title):
    from main import get_abbreviations
    return get_abbreviations().get(title.lower(), None)


def plot_stock_history(name=None,
                       id=None, use_markers=False,
                       first_sold_out_only=True,
                       style="seaborn-dark", use_file=False, print_to_console=True):
    assert name is None or id is None
    if name is None:
        from main import manually_check_displate
        name = manually_check_displate(id=id)["data"]["title"]
    filepath = Path(Path(__file__).parent, f"data/{name}/stockchanges.csv")
    if not filepath.exists():
        name = get_name_from_abbreviation(title=name)
        filepath = Path(Path(__file__).parent, f"data/{name}/stockchanges.csv")
    time, stock = process_file(filepath=filepath)
    # fig, ax = plt.subplots()

    if style == "dracula":
        import matplotx
        plt.style.use(matplotx.styles.dracula)
    elif style == "default":
        pass
    else:
        plt.style.use(style=style)

    ax = plt.gca()
    plt.grid(visible=True)

    # time = data["time"]
    # stock = data["stock"]
    if first_sold_out_only:
        time, stock = crop_data(time, stock)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=10)
    # locator.intervald["YEARLY"] = [0]
    # locator.intervald["MONTHLY"] = [0]
    formatter = mdates.ConciseDateFormatter(locator)

    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    if use_markers:
        ax.plot(time, stock, marker='x', markersize=3)
    else:
        ax.plot(time, stock)

    # ax.set_xlim(lims[nn])
    ax.set_title(name)
    if print_to_console:
        print(f"last timestamp: {time[-1]} \nlast stock value: {stock[-1]}")

    if use_file:
        plt.savefig(Path(__file__).parent / f"{name}.png", dpi=300)
        plt.clf()
        return None
    else:
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=300)
        buf.seek(0)
        plt.clf()
        return buf


def crop_data(time, stock):
    index_first_sold_out = -1
    try:
        # get the index where the stock value is 0
        # increase by one to include it when slicing the list
        index_first_sold_out = stock.index(0) + 1
        time = time[0:index_first_sold_out]
        stock = stock[0:index_first_sold_out]
    except ValueError as err:
        print("Unable to find stock value of 0.")
    return time, stock


def plot_single_entry_to_compare(name, ax=None):
    filepath = Path(Path(__file__).parent, f"data/{name}/stockchanges.csv")
    if not filepath.exists():
        name = get_name_from_abbreviation(title=name)
        filepath = Path(Path(__file__).parent, f"data/{name}/stockchanges.csv")
    time, stock = process_file(filepath=filepath)
    metadata = get_metdata(name=name)
    # fig, ax = plt.subplots()
    if ax is None:
        ax = plt.gca()
    plt.grid(visible=True)

    time, stock = crop_data(time, stock)
    base = datetime.datetime(2022, 1, 2)
    start_date = datetime.datetime.strptime(metadata["edition"]["startDate"], '%Y-%m-%d %H:%M:%S')
    time = [base + (timestamp - start_date) for timestamp in time]

    locator = mdates.AutoDateLocator(minticks=4, maxticks=10)
    formatter = mdates.ConciseDateFormatter(locator)
    formatter.formats = ['', '', '%d', '%H:%M', '%H:%M', '%S.%f']
    formatter.zero_formats = ['', '', '', '%d', '%H:%M', '%H:%M']
    formatter.offset_formats = ['', '', '', '%d', '%d', '%d %H:%M']
    # formatter.show_offset = False

    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    plot = ax.plot(time, stock, label=name)

    # ax.set_xlim(lims[nn])
    # ax.set_title(name)
    print(f"last timestamp: {time[-1]} \nlast stock value: {stock[-1]}")
    return plot, name


def plot_compare(names, style="seaborn-dark", use_file=False):
    if style == "dracula":
        import matplotx
        plt.style.use(matplotx.styles.dracula)
    elif style == "default":
        pass
    else:
        plt.style.use(style=style)
    fig, ax = plt.subplots()
    plots = []
    titles = []
    for name in names:
        plot, title = plot_single_entry_to_compare(name=name, ax=ax)
        plots.append(plot[0])
        titles.append(title)
    ax.legend(plots, titles)
    plt.grid(visible=True)
    if use_file:
        plt.savefig(Path(__file__).parent / f"comparison.png", dpi=300)
        plt.clf()
        return None
    else:
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=300)
        buf.seek(0)
        plt.clf()
        return buf


def plot_and_save(name, style="seaborn-dark", dpi=300):
    plot_stock_history(name=name, style=style, use_file=True)
    plt.clf()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        names = []
        if len(sys.argv) == 2:
            name = sys.argv[1]
            print(f"{name=}")
            plot_and_save(name=name)
        else:
            names = []
            for enum, name in enumerate(sys.argv):
                if enum != 0:
                    names.append(name)

            print(f"{names=}")
            plot_compare(names=names, use_file=True)
    else:
        print("no names provided")
