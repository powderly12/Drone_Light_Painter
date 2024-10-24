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
from cflib.positioning.position_hl_commander import PositionHlCommander


def simple_connect():
    print("Yeah, I'm connected! :D")
    time.sleep(3)
    print("Now I will disconnect :'(")


deck_attached_event = Event()

COLORS = ['Red', 'Green', 'Blue']
DEFAULT_HEIGHT = 0.6
BOX_LIMIT = 1
position_estimate =[0,0,0]
origin =[0,0,0]
#we draw on the xz plane
#Different colour move back in the y axis
def ringOff(scf):
    scf.cf.param.set_value('ring.solidRed', "0")
    scf.cf.param.set_value('ring.solidGreen', "0")
    scf.cf.param.set_value('ring.solidBlue', "0")

def ringRed(scf):
    scf.cf.param.set_value('ring.solidRed', "255")
    scf.cf.param.set_value('ring.solidGreen', "0")
    scf.cf.param.set_value('ring.solidBlue', "0")

def ringBlue(scf):
    scf.cf.param.set_value('ring.solidRed', "0")
    scf.cf.param.set_value('ring.solidGreen', "0")
    scf.cf.param.set_value('ring.solidBlue', "255")

def ringGreen(scf):
    scf.cf.param.set_value('ring.solidRed', "0")
    scf.cf.param.set_value('ring.solidGreen', "255")
    scf.cf.param.set_value('ring.solidBlue', "0")


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

def moveX(pc, x):
    pc.go_to(x, 0, 0, velocity=0.2)
    

    
def moveXZ(line, XOffset, pc, velocity=0.2):
    
    for i in range(0,len(line)):# THIS SHOULD WORK BUT DOESN'T INCLUDE LOGGING SO SOMETHING IS MISSING
            
            if i == 0:
                pc.go_to(0, 0, line[i][1], velocity)
                time.sleep(0.2)
                pc.go_to(XOffset, 0, line[i][1], velocity)
                time.sleep(0.2)
                pc.go_to(XOffset, line[i][0], line[i][1], velocity)
                time.sleep(0.2)
            pc.go_to(XOffset, line[i][0], line[i][1], velocity)
            time.sleep(0.2) 

           #if ((position_estimate[0] + (position_estimate[0] - line[i][0])) <= BOX_LIMIT) and ((position_estimate[2] + (position_estimate[2] - line[i][1])) <= BOX_LIMIT):
            #    newX = position_estimate[0] - line[i][0]
            #    newZ = position_estimate[2] - line[i][1]
            #    mc.move_distance(newX, 0.0, newZ, velocity)
            #else:
            #    x=0
                #newX = [0] - line[i][0]
                #newZ = currentPosition[2] - line[i][1]
                #mc.move_distance(BOX_LIMIT - currentPosition[0], 0.0, BOX_LIMIT - currentPosition[2], velocity)
                #currentPosition[0] = currentPosition[0] + newX
                #currentPosition[2] = currentPosition[2] + newZ
                #time.sleep(0.1)
    return 0



def normalising_corridinates(line):
    for i in range(0,len(line)):
        for j in range(0,len(line[0])):
            if line[i][j] < 0:
                line[i][j] = 0
            if line[i][j] > 800:
                line[i][j] = 800
            #normalise to be corrdinates between 1 and 0
            line[i][j] = line[i][j]/800
            if j ==0:#shift 
                line[i][j] =line[i][j] - 0.5
            else:
                line[i][j] =line[i][j] + 0.2
    return line
        

def draw_lines(lines, scf):
    """
    Trace lines
    """
    #check if the d rone has red lines
    # A circle creates 425 samples we should down sample this to 10 points per layer
    scf.cf.param.set_value('ring.effect', "7")
    ringOff(scf)
    with PositionHlCommander(scf, controller=PositionHlCommander.CONTROLLER_PID) as pc:
        samplingFactor= 8
        if lines[0]:
            
            ringRed(scf)
            time.sleep(0.5)
            numberOfPoints = len(lines[0])
            redWaypoints = lines[0][0::round(numberOfPoints/samplingFactor)]
            redline = normalising_corridinates(redWaypoints)
            moveXZ(redline, -0.1, pc)
            ringOff(scf)

        #if lines[1]:
            #moveY(mc,0.1)
            #time.sleep(0.5)
            #numberOfPoints = len(lines[1])
            #GreenWaypoints = lines[1][0::round(numberOfPoints/samplingFactor)]
            #moveXZ(mc,GreenWaypoints)
        #if lines[2]:
            #moveY(mc,0.1)
            #time.sleep(0.5)
            #numberOfPoints = len(lines[2])
            #GreenWaypoints = lines[2][0::round(numberOfPoints/samplingFactor)]
            #moveXZ(mc,GreenWaypoints)

        pc.land()


def submit_drawing(lines,dronechannel):
    """
    This takes the line coordinated drawn by the user and converts them into 
    Movement instruction for the drone
    will have to address gap in drawings
    """
    #Connect to drone and start logging

    
    cflib.crtp.init_drivers()

    with SyncCrazyflie(dronechannel, cf=Crazyflie(rw_cache='./cache')) as scf:
        

        #scf.cf.param.add_update_callback(group='deck', name='bcFlow2',
         #                                cb=param_deck_flow)
        #time.sleep(1)

        logconf = LogConfig(name='Position', period_in_ms=10)
        logconf.add_variable('stateEstimate.x', 'float')
        logconf.add_variable('stateEstimate.y', 'float')
        logconf.add_variable('stateEstimate.z', 'float')
        scf.cf.log.add_config(logconf)
        logconf.data_received_cb.add_callback(log_pos_callback)

        #if not deck_attached_event.wait(timeout=5):
        #    print('No flow deck detected!')
        #    sys.exit(1)

        logconf.start()
        draw_lines(lines,scf)
        return
    
    #return

DRONE_CHANNEL =['radio://0/19/2M/EE5C21CF18','Radio://0/26/2M/EE5C21CF25']




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

        if event == "-GRAPH-":  # if there's a " event, then it's a mouse
            x, y = values["-GRAPH-"]
            if not dragging:
                start_point = (x, y)
                dragging = True
                lastxy = x, y
            else:
                end_point = (x, y)
            #if prior_rect:
                #graph.delete_figure(prior_rect)
            lastxy = [x,y]
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

