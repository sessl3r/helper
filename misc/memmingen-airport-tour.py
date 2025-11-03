#!/usr/bin/env python3
"""

MIT License

Copyright (c) 2025 Tobias Binkowski

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""

import argparse
import time
import requests
import json
import logging

from subprocess import Popen, PIPE
from email.mime.text import MIMEText

# Get Dates/Times: curl -X POST -d 'formId=10' 'https://tour.memmingen-airport.de/index.php?task=getTimes&option=com_rsform'
# Get Tickets for Date/Time: curl -X POST -d 'formId=10' -d 'formId=10&ArrivalDate=05%2F21%2F2025&ArrivalTime=15%3A15' 'https://tour.memmingen-airport.de/index.php?task=checktickets&option=com_rsform'

parser = argparse.ArgumentParser()
parser.add_argument('--formid', default=10, type=int)
parser.add_argument('--collected',
        default='memmingen-airport-tour.collected', type=str)
parser.add_argument('--mail', nargs='*', default=None)
args = parser.parse_args()

BASE_URL = "https://tour.memmingen-airport.de/index.php"
TASK_TIMES = "getTimes"
TASK_TICKETS = "checktickets"


def get_times():
    x = requests.post(BASE_URL,
            params = {
                "task": TASK_TIMES,
                "option": "com_rsform"
            },
            data = {
                "formId": args.formid
            })
    return x.json()


def get_tickets(date, time):
    x = requests.post(BASE_URL,
            params = {
                "task": TASK_TICKETS,
                "option": "com_rsform"
            },
            data = {
                "formId": args.formid,
                "ArrivalDate": date,
                "ArrivalTime": time
            })
    res = int(x.text)
    # copied from https://tour.memmingen-airport.de/kids-tour javascript line
    # 195 in document.ready function
    if (res > 0):
        if (25-res) < 1:
            return 0
        else:
            return 25-res
    else:
        return res


def filtered_list():
    ret = []
    for entry in get_times():
        date = entry['date']
        date_split = date.split('/')
        date_str = f"{date_split[2]}-{date_split[0]}-{date_split[1]}"
        for time in entry['time']:
            tickets = get_tickets(date, time)
            if tickets > 0:
                ret.append({
                    'datetime': f"{date_str} {time}",
                    'date': date,
                    'time': time,
                    'tickets': tickets
                })
    return ret


def send_mail(entries : list, adresses : list):
    tour = "-Kids"
    if args.formid == 8:
        tour = ""
    msg = f"""

    Memmingen Airport{tour} Tour hat heute die folgenden freien Termine:

    <ul>
    """
    for entry in entries:
        msg += f"<li>{entry['datetime']} : {entry['tickets']} Plätze frei</li>"
    msg += "</ul>"

    msg = MIMEText(msg, 'html')
    msg["To"] = ','.join(adresses)
    msg["Subject"] = f"Memmingen Airport{tour} Tour - freie Plätze"
    p = Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
    p.communicate(msg.as_bytes())
    logging.info(f"Sent mail out to {msg['To']}")


def remember_known_datetimes(entries: list):
    known = []
    try:
        with open(args.collected) as f:
            known = [line.rstrip() for line in f]
    except Exception as e:
        logging.warning(f"No collected file found, creating a new one (e: {e})")
        known = []
    logging.debug(f"Already known entries: {known}")
    old_known = known.copy()

    for entry in entries:
        if not entry['datetime'] in known:
            known.append(entry['datetime'])

    with open(args.collected, 'w') as f:
        f.write("\n".join(known))

    return old_known

if __name__ == '__main__':
    # get list of dates on which tickets available
    logging.basicConfig(level=logging.INFO)
    ret = filtered_list()
    if len(ret) > 0:
        # check and update datetimes into file which already were there last
        # times
        logging.info(f"Found some entries: {ret}")
        old_known = remember_known_datetimes(ret)
        for entry in ret:
            if entry['datetime'] not in old_known:
                # only send mail once if new tickets available
                if args.mail is not None:
                    send_mail(ret, args.mail)
                else:
                    logging.warning(f"Found current tickets, but no mail given: {ret}")
                break
    else:
        logging.info(f"No entries currently available, but would have sent to {args.mail}")
