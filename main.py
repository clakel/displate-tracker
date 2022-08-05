import requests
import json
from datetime import datetime, timezone
import pytz
import csv
from pathlib import Path
from mail_fetcher import get_limited_edition_id
from apscheduler.schedulers.background import BackgroundScheduler, BlockingScheduler

general_api_url = "https://sapi.displate.com/artworks/limited"

upcoming_le_id = None
previous_number_of_upcoming_les = 0
previous_active_displates = []


def check_weekday(weekday=2):
    # weekday 2 -> Wednesday, 3 -> Thursday
    time = get_cet_time()
    return time.weekday() == weekday, time


def read_local_data() -> dict:
    try:
        with open(Path(__file__).parent / 'local_backup.json') as json_file:
            data = json.load(json_file)
    except FileNotFoundError as err:
        data = {}
    return data


def store_local_data(data):
    with open(Path(__file__).parent / 'local_backup.json', 'w+') as outfile:
        json.dump(data, outfile, indent=4)


def get_cet_time():
    utc_dt = datetime.now(timezone.utc)
    CET = pytz.timezone('CET')
    return utc_dt.astimezone(CET)


def store_metadata(data):
    filepath = Path(Path(__file__).parent, f"data/{data['title']}/metadata.json")
    if not filepath.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
        from copy import deepcopy
        temp_data = deepcopy(data)
        with open(filepath, 'w+') as file:
            temp_data["edition"].pop("status", None)
            temp_data["edition"].pop("available", None)
            json.dump(temp_data, file, indent=4)


def store_stock_change(id, time: datetime, stock):
    filepath = Path(Path(__file__).parent, f"data/{id}/stockchanges.csv")
    if not filepath.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w+') as file:
            writer = csv.writer(file)
            writer.writerow(["datetime", "available_stock"])
            writer.writerow([time.timestamp(), stock])
    else:
        with open(filepath, 'a+') as file:
            writer = csv.writer(file)
            writer.writerow([time.timestamp(), stock])


def manually_check_displate(id):
    return requests.get(f"{general_api_url}/{id}").json()


def create_new_directory(title):
    filepath = Path(Path(__file__).parent, f"data/{title}/")
    if not filepath.exists():
        filepath.mkdir(parents=True, exist_ok=True)


def main():
    output = {"stock": {},
              "alert": {"ea_over": {},
                        "back": {},
                        "sold_out": {},
                        "stock_level": {}},
              "next_upcoming_LE": {}}

    local_data = read_local_data()
    is_wednesday, time = check_weekday(2)
    manual_fetch_required = False
    if local_data.get("upcoming_le_id", None) is None and is_wednesday:
        local_data["upcoming_le_id"] = get_limited_edition_id()
    elif not is_wednesday:
        pass
        # local_data.pop('upcoming_le_stock', None)
        # local_data["upcoming_le_id"] = None
    try:
        response = requests.get(general_api_url)
        out = response.json()

        active_displates = [d for d in out["data"] if d['edition']['status'] == 'active']
        upcoming_displates = [d for d in out["data"] if d['edition']['status'] == 'upcoming']

        if local_data.get("upcoming_le_id", None) is not None:
            if local_data.get("upcoming_le_status", "upcoming") == "upcoming":
                all_active_ids = [d["itemCollectionId"] for d in active_displates]
                if local_data.get("upcoming_le_id", None) not in all_active_ids:
                    manual_fetch_required = True

        # if not len(local_data.get("previous_active_displates", [])) == 0:

        previous_le_ids = [d["itemCollectionId"] for d in local_data.get("previous_active_displates", [])]
        processed_le_ids = []
        for displate in active_displates:
            current_stock = displate['edition']['available']
            store_metadata(data=displate)
            output["stock"][displate["title"]] = current_stock
            if displate["itemCollectionId"] not in previous_le_ids:
                if displate["itemCollectionId"] == local_data.get("upcoming_le_id", None):
                    # if check_weekday(3):
                    print("Early Access Phase over!")
                    output["alert"]["ea_over"][displate["title"]] = current_stock
                    local_data["upcoming_le_id"] = None
                    local_data["upcoming_le_stock"] = None
                    local_data["upcoming_le_status"] = None
                else:
                    print(f"Limited Edition '{displate['title']}' is available again!")
                    output["alert"]["back"][displate["title"]] = current_stock
                store_stock_change(id=displate["title"],
                                   time=get_cet_time(),
                                   stock=current_stock)
            else:
                index = previous_le_ids.index(displate["itemCollectionId"])
                prev_stock = local_data["previous_active_displates"][index]["edition"]["available"]
                if current_stock != prev_stock:
                    print(f"Available stock for '{displate['title']}' changed to {current_stock} from {prev_stock}")
                    store_stock_change(id=displate["title"],
                                       time=get_cet_time(),
                                       stock=current_stock)
                    if current_stock < 100:
                        alert_sent = check_alert(title=displate["title"], stocklevel=100)
                        if not alert_sent:
                            output["alert"]["stock_level"][displate["title"]] = 100
                            save_alert(title=displate["title"], stocklevel=100)
                # # even if the stock was not updated, remove the displate from the previous list,
                # # so that only sold_out displates remain
                # previous_le_ids.remove(displate["itemCollectionId"])
            processed_le_ids.append(displate["itemCollectionId"])
        for previous_le in previous_le_ids:
            if previous_le not in processed_le_ids:
                title = manually_check_displate(previous_le)["data"]["title"]
                store_stock_change(id=title,
                                   time=get_cet_time(),
                                   stock=0)
                print(f"Limited Edition '{title}' sold out!")
                output["alert"]["sold_out"][title] = 0
        # END OF# if not len(local_data.get("previous_active_displates", [])) == 0:
        if is_wednesday or manual_fetch_required:
            if not local_data.get("upcoming_le_id", None) is None:
                ea_le = manually_check_displate(local_data["upcoming_le_id"])["data"]
                store_metadata(data=ea_le)
                stock = ea_le["edition"]["available"]
                local_data["upcoming_le_status"] = ea_le["edition"]["status"]
                was_sold_out = local_data.get("upcoming_le_stock", ea_le["edition"]["size"]) == 0
                is_sold_out = stock == 0
                if not is_sold_out:
                    output["stock"][ea_le["title"]] = stock
                if not was_sold_out and is_sold_out:
                    print(f"Limited Edition '{ea_le['title']}' sold out!")
                    output["alert"]["sold_out"][ea_le["title"]] = stock
                    local_data["upcoming_le_stock"] = ea_le["edition"]["available"]
                if was_sold_out and not is_sold_out:
                    print(f"Limited Edition '{ea_le['title']}' is available again!")
                    output["alert"]["back"][ea_le["title"]] = stock
                if stock != local_data.get("upcoming_le_stock", ea_le["edition"]["size"]):
                    print(f"Available stock for '{ea_le['title']}' changed to {stock}")
                    store_stock_change(id=ea_le["title"],
                                       time=get_cet_time(),
                                       stock=stock)
                    local_data["upcoming_le_stock"] = ea_le["edition"]["available"]
                # if local_data.get("upcoming_le_status", "available") != ea_le["edition"]["available"]:
                #     local_data["upcoming_le_status"] = ea_le["edition"]["status"]
        local_data["previous_active_displates"] = active_displates
        if not len(local_data.get("previous_upcoming_displates", [])) == 0:
            previous_le_names = [d["title"] for d in local_data.get("previous_upcoming_displates", [])]
            for displate in upcoming_displates:
                title = displate["title"]
                if title not in previous_le_names:
                    print(f"Next upcoming Limited edition: {title}")
                    output["next_upcoming_LE"] = {"title": title,
                                                  "startDate": displate["edition"]["startDate"],
                                                  "image": displate["images"]["main"]["url"]}
                    create_new_directory(title)
        local_data["previous_upcoming_displates"] = upcoming_displates
        store_local_data(data=local_data)
    except Exception as error:
        print(f"{time=}")
        print(error)
    return output, time

    # print(json.dumps(active_displates, indent=4))

    # print(json.dumps(upcoming_displates, indent=4))


def get_abbreviations():
    filepath = Path(Path(__file__).parent, f"data/abbreviations.csv")
    if not filepath.exists():
        return {}
    else:
        with open(filepath) as json_file:
            data = json.load(json_file)
        return data


def add_abbreviations(abbreviation, title):
    abbreviations = get_abbreviations()
    # check if title is valid:
    if Path(Path(__file__).parent, f"data/{title}/").exists():
        abbreviations[abbreviation.lower()] = title
        filepath = Path(Path(__file__).parent, f"data/abbreviations.csv")
        if not filepath.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w+") as json_file:
            json.dump(abbreviations, json_file, indent=4)
        return True
    else:
        return False


def check_alert(title, stocklevel):
    data = read_alert(title)
    return data.get(str(stocklevel), False) is True


def read_alert(title):
    try:
        with open(Path(__file__).parent / f"data/{title}/alerts.json") as json_file:
            data = json.load(json_file)
    except Exception as err:
        print("Error in read_alert:", err)
        data = {}
    return data


def save_alert(title, stocklevel):
    data = read_alert(title=title)
    data[str(stocklevel)] = True
    filepath = Path(__file__).parent / f"data/{title}/alerts.json"
    if not filepath.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w+') as json_file:
        json.dump(data, json_file, indent=4)


if __name__ == '__main__':
    # scheduler = BackgroundScheduler()

    scheduler = BlockingScheduler()
    job = scheduler.add_job(main, 'interval', minutes=1)
    main()
    scheduler.start()

    # print(main())

    # sec_version()
