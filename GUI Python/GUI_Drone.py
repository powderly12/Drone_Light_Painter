import PySimpleGUI as sg
import logging
import time
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils import uri_helper


def simple_connect():
    print("Yeah, I'm connected! :D")
    time.sleep(3)
    print("Now I will disconnect :'(")



COLORS = ['Red', 'Green', 'Blue']

#we draw on the xz plane
#Different colour move back in the y axis

def moveY(mc, scf, y, velocity=0.3):
    mc.move_distance(0, y, 0, velocity=0.2)
    time.sleep(0.5)

    
def moveXZ(mc, scf, x, z, velocity=0.3):
    scale_x = 5
    scale_z = 1.5
    mc.move_distance(x * scale_x, 0.0, z * scale_x, velocity)
    time.sleep(0.5)

def connect_to_drone(dronechannel):
    """
    Connects to the desired drone choosen by the user in the GUI, Returns drone status (connected or not connected),
    Positions drone in starting positions for drawing and turns on LED
    """
    # URI to the Crazyflie to connect to
    uri = uri_helper.uri_from_env(default=dronechannel)
    # Initialize the low-level drivers
    cflib.crtp.init_drivers()

    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache='./cache')) as scf:
        simple_connect()

def submit_drawing(lines,mc,scf):
    """
    This takes the line coordinated drawn by the user and converts them into 
    Movement instruction for the drone
    will have to address gap in drawings
    """
    #check if the drone has red lines
    # A circle creates 425 samples we should down sample this to 10 points per layer
    mc.take_off(0.2, 0.3)

    time.sleep(0.5)
    samplingFactor= 10
    if lines[0]:
        moveY(mc,scf,-0.1)
        time.sleep(0.5)
        #numberOfPoints = len(lines[0])
        #redWaypoints = lines[0][0::round(numberOfPoints/samplingFactor)]
        #moveXZ(redWaypoints)
    if lines[1]:
        moveY(mc,scf,0.1)
        time.sleep(0.5)

    if lines[2]:
        moveY(mc,scf,0.1)
        time.sleep(0.5)

    mc.land()
    return

DRONE_CHANNEL =['radio://0/26/2M/EE5C21CF25','Radio://0/26/2M/EE5C21CF28']




def main():

    #GUI Initialisation
    rightColumn = [[sg.T('Controls:', enable_events=True)],
                   [sg.Text('Choose Drone Channel:'), sg.Combo(DRONE_CHANNEL, default_value='radio://0/26/2M/EE5C21CF25', key='-CHANNEL-')],
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
        elif event == '-DRONE-':
            connect_to_drone(dronechannel)
        elif event == '-DRAWING-':
        
            with SyncCrazyflie(dronechannel) as scf:

                mc = MotionCommander(scf)
                submit_drawing(lines,mc,scf)

    window.close()

main()

