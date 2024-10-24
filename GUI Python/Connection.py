import cflib.crtp
import time 
import logging
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils import uri_helper

def simple_connect():
            print("Yeah, I'm connected! :D")
            time.sleep(3)
            print("Now I will disconnect :'(")

# URI to the Crazyflie to connect to
uri = uri_helper.uri_from_env(default='radio://0/26/2M/EE5C21CF25')
    # Initialize the low-level drivers
cflib.crtp.init_drivers()

with SyncCrazyflie(uri, cf=Crazyflie(rw_cache='./cache')) as scf:
    simple_connect()


