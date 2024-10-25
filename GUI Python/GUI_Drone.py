from __future__ import annotations
import PySimpleGUI as sg
import logging
import sys
import time
from threading import Event
import pickle


import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander
from cflib.utils import uri_helper
from cflib.positioning.position_hl_commander import PositionHlCommander
#Calibration
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.mem.lighthouse_memory import LighthouseBsGeometry
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.localization.lighthouse_bs_vector import LighthouseBsVectors
from cflib.localization.lighthouse_config_manager import LighthouseConfigWriter
from cflib.localization.lighthouse_geometry_solver import LighthouseGeometrySolver
from cflib.localization.lighthouse_initial_estimator import LighthouseInitialEstimator
from cflib.localization.lighthouse_sample_matcher import LighthouseSampleMatcher
from cflib.localization.lighthouse_sweep_angle_reader import LighthouseSweepAngleAverageReader
from cflib.localization.lighthouse_sweep_angle_reader import LighthouseSweepAngleReader
from cflib.localization.lighthouse_system_aligner import LighthouseSystemAligner
from cflib.localization.lighthouse_system_scaler import LighthouseSystemScaler
from cflib.localization.lighthouse_types import LhCfPoseSample
from cflib.localization.lighthouse_types import LhDeck4SensorPositions
from cflib.localization.lighthouse_types import LhMeasurement
from cflib.localization.lighthouse_types import Pose
import numpy as np



deck_attached_event = Event()

COLORS = ['Red', 'Green', 'Blue']
DEFAULT_HEIGHT = 0.6
REFERENCE_DIST = 1.0

BOX_LIMIT = 1
position_estimate =[0,0,0]
origin =[0,0,0]
#we draw on the xz plane

#Calibration Code






REFERENCE_DIST = 1.0


def record_angles_average(scf: SyncCrazyflie, timeout: float = 5.0) -> LhCfPoseSample:
    """Record angles and average over the samples to reduce noise"""
    recorded_angles = None

    is_ready = Event()

    def ready_cb(averages):
        nonlocal recorded_angles
        recorded_angles = averages
        is_ready.set()

    reader = LighthouseSweepAngleAverageReader(scf.cf, ready_cb)
    reader.start_angle_collection()

    if not is_ready.wait(timeout):
        print('Recording timed out.')
        return None

    angles_calibrated = {}
    for bs_id, data in recorded_angles.items():
        angles_calibrated[bs_id] = data[1]

    result = LhCfPoseSample(angles_calibrated=angles_calibrated)

    visible = ', '.join(map(lambda x: str(x + 1), recorded_angles.keys()))
    print(f'  Position recorded, base station ids visible: {visible}')

    if len(recorded_angles.keys()) < 2:
        print('Received too few base stations, we need at least two. Please try again!')
        result = None

    return result


def record_angles_sequence(scf: SyncCrazyflie, recording_time_s: float) -> list[LhCfPoseSample]:
    """Record angles and return a list of the samples"""
    result: list[LhCfPoseSample] = []

    bs_seen = set()

    def ready_cb(bs_id: int, angles: LighthouseBsVectors):
        now = time.time()
        measurement = LhMeasurement(timestamp=now, base_station_id=bs_id, angles=angles)
        result.append(measurement)
        bs_seen.add(str(bs_id + 1))

    reader = LighthouseSweepAngleReader(scf.cf, ready_cb)
    reader.start()
    end_time = time.time() + recording_time_s

    while time.time() < end_time:
        time_left = int(end_time - time.time())
        visible = ', '.join(sorted(bs_seen))
        print(f'{time_left}s, bs visible: {visible}')
        bs_seen = set()
        time.sleep(0.5)

    reader.stop()

    return result


def parse_recording_time(recording_time: str, default: int) -> int:
    """Interpret recording time input by user"""
    try:
        return int(recording_time)
    except ValueError:
        return default


def print_base_stations_poses(base_stations: dict[int, Pose]):
    """Pretty print of base stations pose"""
    for bs_id, pose in sorted(base_stations.items()):
        pos = pose.translation
        print(f'    {bs_id + 1}: ({pos[0]}, {pos[1]}, {pos[2]})')


def set_axes_equal(ax):
    '''Make axes of 3D plot have equal scale so that spheres appear as spheres,
    cubes as cubes, etc..  This is one possible solution to Matplotlib's
    ax.set_aspect('equal') and ax.axis('equal') not working for 3D.

    Input
    ax: a matplotlib axis, e.g., as output from plt.gca().
    '''

    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_range = abs(x_limits[1] - x_limits[0])
    x_middle = np.mean(x_limits)
    y_range = abs(y_limits[1] - y_limits[0])
    y_middle = np.mean(y_limits)
    z_range = abs(z_limits[1] - z_limits[0])
    z_middle = np.mean(z_limits)

    # The plot bounding box is a sphere in the sense of the infinity
    # norm, hence I call half the max range the plot radius.
    plot_radius = 0.5*max([x_range, y_range, z_range])

    ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
    ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
    ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])


def visualize(cf_poses: list[Pose], bs_poses: list[Pose]):
    """Visualize positions of base stations and Crazyflie positions"""
    # Set to True to visualize positions
    # Requires PyPlot
    visualize_positions = False
    if visualize_positions:
        import matplotlib.pyplot as plt

        positions = np.array(list(map(lambda x: x.translation, cf_poses)))

        fig = plt.figure()
        ax = fig.add_subplot(projection='3d')

        x_cf = positions[:, 0]
        y_cf = positions[:, 1]
        z_cf = positions[:, 2]

        ax.scatter(x_cf, y_cf, z_cf)

        positions = np.array(list(map(lambda x: x.translation, bs_poses)))

        x_bs = positions[:, 0]
        y_bs = positions[:, 1]
        z_bs = positions[:, 2]

        ax.scatter(x_bs, y_bs, z_bs, c='red')

        set_axes_equal(ax)
        print('Close graph window to continue')
        plt.show()


def write_to_file(name: str,
                  origin: LhCfPoseSample,
                  x_axis: list[LhCfPoseSample],
                  xy_plane: list[LhCfPoseSample],
                  samples: list[LhCfPoseSample]):
    with open(name, 'wb') as handle:
        data = (origin, x_axis, xy_plane, samples)
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_from_file(name: str):
    with open(name, 'rb') as handle:
        return pickle.load(handle)


def estimate_geometry(origin: LhCfPoseSample,
                      x_axis: list[LhCfPoseSample],
                      xy_plane: list[LhCfPoseSample],
                      samples: list[LhCfPoseSample]) -> dict[int, Pose]:
    """Estimate the geometry of the system based on samples recorded by a Crazyflie"""
    matched_samples = [origin] + x_axis + xy_plane + LighthouseSampleMatcher.match(samples, min_nr_of_bs_in_match=2)
    initial_guess, cleaned_matched_samples = LighthouseInitialEstimator.estimate(
        matched_samples, LhDeck4SensorPositions.positions)

    print('Initial guess base stations at:')
    print_base_stations_poses(initial_guess.bs_poses)

    print(f'{len(cleaned_matched_samples)} samples will be used')
    visualize(initial_guess.cf_poses, initial_guess.bs_poses.values())

    solution = LighthouseGeometrySolver.solve(initial_guess, cleaned_matched_samples, LhDeck4SensorPositions.positions)
    if not solution.success:
        print('Solution did not converge, it might not be good!')

    start_x_axis = 1
    start_xy_plane = 1 + len(x_axis)
    origin_pos = solution.cf_poses[0].translation
    x_axis_poses = solution.cf_poses[start_x_axis:start_x_axis + len(x_axis)]
    x_axis_pos = list(map(lambda x: x.translation, x_axis_poses))
    xy_plane_poses = solution.cf_poses[start_xy_plane:start_xy_plane + len(xy_plane)]
    xy_plane_pos = list(map(lambda x: x.translation, xy_plane_poses))

    print('Raw solution:')
    print('  Base stations at:')
    print_base_stations_poses(solution.bs_poses)
    print('  Solution match per base station:')
    for bs_id, value in solution.error_info['bs'].items():
        print(f'    {bs_id + 1}: {value}')

    # Align the solution
    bs_aligned_poses, transformation = LighthouseSystemAligner.align(
        origin_pos, x_axis_pos, xy_plane_pos, solution.bs_poses)

    cf_aligned_poses = list(map(transformation.rotate_translate_pose, solution.cf_poses))

    # Scale the solution
    bs_scaled_poses, cf_scaled_poses, scale = LighthouseSystemScaler.scale_fixed_point(bs_aligned_poses,
                                                                                       cf_aligned_poses,
                                                                                       [REFERENCE_DIST, 0, 0],
                                                                                       cf_aligned_poses[1])

    print()
    print('Final solution:')
    print('  Base stations at:')
    print_base_stations_poses(bs_scaled_poses)

    visualize(cf_scaled_poses, bs_scaled_poses.values())

    return bs_scaled_poses


def upload_geometry(scf: SyncCrazyflie, bs_poses: dict[int, Pose]):
    """Upload the geometry to the Crazyflie"""
    geo_dict = {}
    for bs_id, pose in bs_poses.items():
        geo = LighthouseBsGeometry()
        geo.origin = pose.translation.tolist()
        geo.rotation_matrix = pose.rot_matrix.tolist()
        geo.valid = True
        geo_dict[bs_id] = geo

    event = Event()

    def data_written(_):
        event.set()

    helper = LighthouseConfigWriter(scf.cf)
    helper.write_and_store_config(data_written, geos=geo_dict)
    event.wait()


def estimate_from_file(file_name: str):
    origin, x_axis, xy_plane, samples = load_from_file(file_name)
    estimate_geometry(origin, x_axis, xy_plane, samples)


def get_recording(scf: SyncCrazyflie):
    data = None
    while True:  # Infinite loop, will break on valid measurement
        input('Press return when ready. ')
        print('  Recording...')
        measurement = record_angles_average(scf)
        if measurement is not None:
            data = measurement
            break  # Exit the loop if a valid measurement is obtained
        else:
            time.sleep(1)
            print('Invalid measurement, please try again.')
    return data


def get_multiple_recordings(scf: SyncCrazyflie):
    data = []
    first_attempt = True

    while True:
        if first_attempt:
            user_input = input('Press return to record a measurement: ').lower()
            first_attempt = False
        else:
            user_input = input('Press return to record another measurement, or "q" to continue: ').lower()

        if user_input == 'q' and data:
            break
        elif user_input == 'q' and not data:
            print('You must record at least one measurement.')
            continue

        print('  Recording...')
        measurement = record_angles_average(scf)
        if measurement is not None:
            data.append(measurement)
        else:
            time.sleep(1)
            print('Invalid measurement, please try again.')

    return data


def connect_and_estimate(uri: str, file_name: str | None = None):
    """Connect to a Crazyflie, collect data and estimate the geometry of the system"""
    print(f'Step 1. Connecting to the Crazyflie on uri {uri}...')
    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache='./cache')) as scf:
        print('  Connected')
        print('')
        print('In the 3 following steps we will define the coordinate system.')

        print('Step 2. Put the Crazyflie where you want the origin of your coordinate system.')

        origin = get_recording(scf)

        print(f'Step 3. Put the Crazyflie on the positive X-axis, exactly {REFERENCE_DIST} meters from the origin. ' +
              'This position defines the direction of the X-axis, but it is also used for scaling of the system.')
        x_axis = [get_recording(scf)]

        print('Step 4. Put the Crazyflie somehere in the XY-plane, but not on the X-axis.')
        print('Multiple samples can be recorded if you want to.')
        xy_plane = get_multiple_recordings(scf)

        print()
        print('Step 5. We will now record data from the space you plan to fly in and optimize the base station ' +
              'geometry based on this data. Move the Crazyflie around, try to cover all of the space, make sure ' +
              'all the base stations are received and do not move too fast.')
        default_time = 20
        recording_time = input(f'Enter the number of seconds you want to record ({default_time} by default), ' +
                               'recording starts when you hit enter. ')
        recording_time_s = parse_recording_time(recording_time, default_time)
        print('  Recording started...')
        samples = record_angles_sequence(scf, recording_time_s)
        print('  Recording ended')

        if file_name:
            write_to_file(file_name, origin, x_axis, xy_plane, samples)
            print(f'Wrote data to file {file_name}')

        print('Step 6. Estimating geometry...')
        bs_poses = estimate_geometry(origin, x_axis, xy_plane, samples)
        print('  Geometry estimated')

        print('Step 7. Upload geometry to the Crazyflie')
        input('Press enter to upload geometry. ')
        upload_geometry(scf, bs_poses)
        print('Geometry uploaded')






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
    with PositionHlCommander(scf, controller=PositionHlCommander.CONTROLLER_PID, default_height=0.5) as pc:
        samplingFactor= 10
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
    # Set a file name to write the measurement data to file. Useful for debugging
    file_name = None
    # file_name = 'lh_geo_estimate_data.pickle'

    connect_and_estimate(dronechannel, file_name=file_name)

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

DRONE_CHANNEL =['radio://0/19/2M/EE5C21CF18','radio://0/26/2M/EE5C21CF25']




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

