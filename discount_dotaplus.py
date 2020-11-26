#!/usr/bin/python3.7
# Change the variables in config.py, and run this file The summary will be
# generated as soon as a game starts.
import time
import os
import re
import subprocess
from multiprocessing import Pool

import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pynput import keyboard

from config import SERVER_FILE_PATH, TOGGLE_KEY

DZEN_PROCESS = None
DZEN_MSG = None

MATCHES_URL = 'https://api.opendota.com/api/players/%s/matches?date=30&game_mode=22'
PLAYER_URL = 'https://api.opendota.com/api/players/%s'

GLOBAL_HEROES = {
    hero['id']: hero['localized_name']
    for hero in requests.get('https://api.opendota.com/api/heroes').json()
}


def generate_player_summary(player):
    try:
        player_info = requests.get(PLAYER_URL % player).json()
        matches = requests.get(MATCHES_URL % player).json()
        hero_wins = {}
        for match in matches:
            hero_id = match['hero_id']
            if hero_id not in hero_wins:
                hero_wins[hero_id] = [0, 0]
            win = ((match['player_slot'] < 128) == match['radiant_win'])
            if win:
                hero_wins[hero_id][0] += 1
            else:
                hero_wins[hero_id][1] += 1
        summary = []
        for hero_id in hero_wins:
            summary.append((GLOBAL_HEROES[hero_id], hero_wins[hero_id][0], hero_wins[hero_id][1]))
        summary.sort(key=lambda x:-(x[1]+x[2]))
        player_name_builder = player_info['profile']['personaname']
        player_name_builder = f"^fg(red){player_info['profile']['personaname']}^fg() ({player_info['rank_tier']})"
        player_name_builder = f"^ca(1,xdg-open https://www.opendota.com/players/{player}){player_name_builder}^ca()"
        return player_name_builder, summary
    except:
        return '^fg(red)N/A^fg()', []


def generate_team_summary(team):
    pool = Pool(10)
    output_lines = ["Opendota+"]
    for name, summary in pool.map(generate_player_summary, team):
        output_lines.append(name + ' :')
        for hero, w, l in summary[:5]:
            output_lines.append(' - %s (%d-%d)' % (hero, w, l))
        output_lines.append('')
        output_lines.append('-----------------')

    pool.close()
    pool.join()
    return '\n'.join(output_lines).encode('utf-8')


def process_line(line):
    print(line)
    players = []
    for term in line.split(' '):
        m = re.match(r'^[0-9]:\[U:1:([0-9]+)\]\)?$', term)
        if m:
            players.append(m.group(1))
    msg = generate_team_summary(players)

    global DZEN_MSG
    DZEN_MSG  = msg
    dzen_on()



def dzen_on():
    global DZEN_PROCESS
    dzen_off()
    if DZEN_MSG is not None:
        DZEN_PROCESS = subprocess.Popen('dzen2 -w 300 -p -l 70 -e "onstart=uncollapse,unhide,scrollhome;button4=scrollup;button5=scrolldown"', shell=True, stdin=subprocess.PIPE)
        DZEN_PROCESS.stdin.write(DZEN_MSG)
        DZEN_PROCESS.stdin.flush()

def dzen_off():
    global DZEN_PROCESS
    if DZEN_PROCESS is not None:
        DZEN_PROCESS.kill()
        DZEN_PROCESS = None

def toggle_dzen():
    if DZEN_PROCESS is None:
        dzen_on()
    else:
        dzen_off()


class MyHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if os.path.basename(event.src_path) == 'server_log.txt':
            with open(event.src_path, 'r') as f:
                for line in reversed(f.readlines()):
                    line = line.strip()
                    if 'loopback' not in line:
                        process_line(line)
                    break


def for_canonical(f):
    return lambda k: f(keyboard_listener.canonical(k))

if __name__ == '__main__':
    hotkey = keyboard.HotKey(
        keyboard.HotKey.parse(TOGGLE_KEY),
        toggle_dzen
    )
    keyboard_listener = keyboard.Listener(
        on_press=for_canonical(hotkey.press),
        on_release=for_canonical(hotkey.release)
    )
    keyboard_listener.start()

    observer = Observer()
    observer.schedule(MyHandler(), path=SERVER_FILE_PATH, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        keyboard_listener.stop()
    observer.join()
    keyboard_listener.join()
