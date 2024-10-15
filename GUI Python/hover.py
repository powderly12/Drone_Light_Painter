"""
This script does a scripted flight path using the MotionCommander class.
The path is shaped as a Christmas tree.

Connects to the crazyflie at `URI` and runs a
sequence. Change the URI variable to your Crazyflie configuration.
"""
import logging
import time

import cflib.crtp
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander

URI = 'radio://0/19/2M/EE5C21CF18'

# Only output errors from the logging framework
logging.basicConfig(level=logging.ERROR)




if __name__ == '__main__':
    # Initialize the low-level drivers (don't list the debug drivers)
    cflib.crtp.init_drivers(enable_debug_driver=False)

    with SyncCrazyflie(URI) as scf:
        # We take off when the commander is created

        #scf.cf.param.set_value('ring.effect', "7")
        #ringOff(scf)
        mc = MotionCommander(scf)
        mc.take_off(0.2, 40)
        time.sleep(0.5)
        mc.up(0.3)
        time.sleep(0.5)
        mc.land(0.5)