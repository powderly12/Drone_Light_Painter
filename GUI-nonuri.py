import PySimpleGUI as sg

import logging
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.position_hl_commander import PositionHlCommander
from cflib.utils import uri_helper

import numpy as np
import atexit

# Initialize drone channels
DRONE_CHANNEL = ['radio://0/26/2M/EE5C21CF25', 'radio://0/26/2M/EE5C21CF28']


# Setup for logging and drone initialization
LOG_CHECK_IN_MS = 50
FLYING_HEIGHT = 0.16  # In meters
DEFAULT_VELOCITY = 0.2  # In m/s
TOLERANCE_RADIUS = 0.02
ACCEL_TOL = 0.04


# Connect to the Crazyflie
def connect_to_drone(dronechannel):
    global uri, _scf, _pc
    uri = uri_helper.uri_from_env(default=dronechannel)
    cflib.crtp.init_drivers()

    _scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache='./cache'))
    _scf.open_link()

    _pc = PositionHlCommander(_scf, controller=PositionHlCommander.CONTROLLER_PID)
    _pc.set_default_height(FLYING_HEIGHT)
    _pc.set_default_velocity(DEFAULT_VELOCITY)
    print("Connected to drone on channel:", dronechannel)


# Move drone to a specific coordinate
def move_drone(x, y):
    global _pc
    if _pc:
        _pc.go_to(x, y)
        print(f"Drone moved to: ({x}, {y})")


# Submit drawing coordinates as drone movements
def submit_drawing(lines):
    """
    This function will take the line coordinates and translate them to drone movements.
    Each color will be translated into a series of movement commands.
    """
    print("Submitting drawing for drone movement.")
    for i, color in enumerate(lines):
        print(f"Processing color {color}: {len(lines[i])} points")
        for point in lines[i]:
            x, y = point
            move_drone(x / 500, y / 500)  # Convert from pixels to meters[1000-500]


# GUI layout
COLORS = ['Red', 'Green', 'Blue']


def main():
    rightColumn = [[sg.T('Controls:', enable_events=True)],
                   [sg.Text('Choose Drone Channel:'),
                    sg.Combo(DRONE_CHANNEL, default_value='radio://0/26/2M/EE5C21CF25', key='-CHANNEL-')],
                   [sg.B('Connect to Drone', key='-DRONE-')],
                   [sg.R('Draw Line', 1, key='-LINE-', enable_events=True)],
                   [sg.Text('Choose Color:'), sg.Combo(COLORS, default_value='Red', key='-COLOR-')],
                   [sg.B('Submit Drawing', key='-DRAWING-')]]

    leftColumn = [[sg.Graph(
        canvas_size=(400, 400),
        graph_bottom_left=(0, 0),
        graph_top_right=(800, 800),
        key="-GRAPH-",
        enable_events=True,
        background_color='white',
        drag_submits=True)],
        [sg.Text(key='info', size=(40, 1))]]

    layout = [
        [
            sg.Column(leftColumn),
            sg.VSeperator(),
            sg.Column(rightColumn), ]
    ]

    window = sg.Window("Drone Painter", layout, keep_on_top=True, finalize=True)

    # Initialize graph and drawing parameters
    graph = window["-GRAPH-"]  # type: sg.Graph
    current_color = 'Red'
    dronechannel = DRONE_CHANNEL[0]
    dragging = False
    start_point = end_point = None
    lines = [[], [], []]  # Red, Green, Blue lines

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break

        # Handle graph events
        if event == "-GRAPH-":
            x, y = values["-GRAPH-"]
            if not dragging:
                start_point = (x, y)
                dragging = True
            else:
                end_point = (x, y)

            if None not in (start_point, end_point):
                current_color = values['-COLOR-']
                if values['-LINE-']:
                    graph.draw_point((x, y), size=15, color=current_color)
                    lines[COLORS.index(current_color)].append((x, y))

        # Stop dragging
        elif event.endswith('+UP'):
            start_point, end_point = None, None
            dragging = False

        # Handle connection to drone
        elif event == '-CHANNEL-':
            dronechannel = values['-CHANNEL-']
        elif event == '-DRONE-':
            connect_to_drone(dronechannel)

        # Handle submission of drawing
        elif event == '-DRAWING-':
            submit_drawing(lines)

    window.close()


main()
