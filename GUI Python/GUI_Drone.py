import PySimpleGUI as sg
import logging
import sys
import time
from threading import Event

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander
from cflib.utils import uri_helper


def simple_connect():
    print("Yeah, I'm connected! :D")
    time.sleep(3)
    print("Now I will disconnect :'(")


deck_attached_event = Event()

COLORS = ['Red', 'Green', 'Blue']
DEFAULT_HEIGHT = 0.5
position_estimate =[0,0,0]
#we draw on the xz plane
#Different colour move back in the y axis
def log_pos_callback(timestamp, data, logconf):
    print(data)
    position_estimate[0] = data['stateEstimate.x']
    position_estimate[1] = data['stateEstimate.y']
    position_estimate[2] = data['stateEstimate.z']

def param_deck_flow(_, value_str):
    value = int(value_str)
    print(value)
    if value:
        deck_attached_event.set()
        print('Deck is attached!')
    else:
        print('Deck is NOT attached!')

def moveY(mc, y):
    mc.move_distance(0, y, 0, velocity=0.2)
    time.sleep(0.5)

    
def moveXZ(mc, x, z, velocity=0.3):
    scale_x = 5
    scale_z = 1.5
    mc.move_distance(x * scale_x, 0.0, z * scale_z, velocity)
    time.sleep(0.5)

def take_off_simple(scf):
    with MotionCommander(scf, default_height=DEFAULT_HEIGHT) as mc:
        time.sleep(3)
        mc.stop()

def draw_lines(lines, scf):
    """
    Trace lines
    """
    #check if the drone has red lines
    # A circle creates 425 samples we should down sample this to 10 points per layer
    with MotionCommander(scf, default_height=DEFAULT_HEIGHT) as mc:
        time.sleep(0.5)
        #set origin point based on loggeing data...
        samplingFactor= 10
        if lines[0]:
            moveY(mc,-0.1)
            time.sleep(0.5)
            numberOfPoints = len(lines[0])
            redWaypoints = lines[0][0::round(numberOfPoints/samplingFactor)]
            moveXZ(redWaypoints)
        if lines[1]:
            moveY(mc,0.1)
            time.sleep(0.5)
            numberOfPoints = len(lines[1])
            GreenWaypoints = lines[1][0::round(numberOfPoints/samplingFactor)]
            moveXZ(mc,GreenWaypoints)
        if lines[2]:
            moveY(mc,0.1)
            time.sleep(0.5)
            numberOfPoints = len(lines[2])
            GreenWaypoints = lines[2][0::round(numberOfPoints/samplingFactor)]
            moveXZ(mc,GreenWaypoints)

        mc.land()


def submit_drawing(lines,dronechannel):
    """
    This takes the line coordinated drawn by the user and converts them into 
    Movement instruction for the drone
    will have to address gap in drawings
    """
    #Connect to drone and start logging
    cflib.crtp.init_drivers()

    with SyncCrazyflie(dronechannel, cf=Crazyflie(rw_cache='./cache')) as scf:

        scf.cf.param.add_update_callback(group='deck', name='bcFlow2',
                                         cb=param_deck_flow)
        time.sleep(1)

        logconf = LogConfig(name='Position', period_in_ms=10)
        logconf.add_variable('stateEstimate.x', 'float')
        logconf.add_variable('stateEstimate.y', 'float')
        logconf.add_variable('stateEstimate.z', 'float')
        scf.cf.log.add_config(logconf)
        logconf.data_received_cb.add_callback(log_pos_callback)

        if not deck_attached_event.wait(timeout=5):
            print('No flow deck detected!')
            sys.exit(1)

        logconf.start()
        take_off_simple(scf)
        return
    
    #return

DRONE_CHANNEL =['radio://0/19/2M/EE5C21CF18','Radio://0/26/2M/EE5C21CF28']




def main():



    #GUI Initialisation
    rightColumn = [[sg.T('Controls:', enable_events=True)],
                   [sg.Text('Choose Drone Channel:'), sg.Combo(DRONE_CHANNEL, default_value='radio://0/26/2M/EE5C21CF25', key='-CHANNEL-')],
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
                drag_submits=True) ],
                [sg.Text(key='info', size=(40, 1))]]
    
    layout = [
        [
        sg.Column(leftColumn),
        sg.VSeperator(),
        sg.Column(rightColumn),]
        ]
    window = sg.Window("Drone Painter", layout, keep_on_top=True, finalize=True)

    #get the graph element for ease of use later
    graph = window["-GRAPH-"]  # type: sg.Graph
    current_color = 'Red'
    dronechannel = DRONE_CHANNEL[0]

    dragging = False
    start_point = end_point = prior_rect = None
    graph.bind('<Button-3>', '+RIGHT+')
    lines = [[],[],[]]
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break 
        if event in ('-MOVE-', '-MOVEALL-'):
            # graph.Widget.config(cursor='fleur')
            graph.set_cursor(cursor='fleur')          # not yet released method... coming soon!
        elif not event.startswith('-GRAPH-'):
            graph.set_cursor(cursor='left_ptr')       # not yet released method... coming soon!
            # graph.Widget.config(cursor='left_ptr')

        if event == "-GRAPH-":  # if there's a "Graph" event, then it's a mouse
            x, y = values["-GRAPH-"]
            if not dragging:
                start_point = (x, y)
                dragging = True
                lastxy = x, y
            else:
                end_point = (x, y)
            #if prior_rect:
                #graph.delete_figure(prior_rect)
            lastxy = x,y
            if None not in (start_point, end_point):
                current_color = values['-COLOR-']
                if values['-LINE-']== True:
                    graph.draw_point(lastxy, size=15, color=current_color)
                    lines[COLORS.index(current_color)].append(lastxy)
        elif event.endswith('+UP'):  
            info = window["info"]
            info.update(value=f"grabbed rectangle from {start_point} to {end_point}")
            start_point, end_point = None, None  
            dragging = False
        elif event == '-CHANNEL-':
            dronechannel = values['-CHANNEL-']
        elif event == '-DRAWING-':
               
                submit_drawing(lines,dronechannel)

    window.close()

main()

