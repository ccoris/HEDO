#!/usr/bin/env python
# pylint: skip-file
"""
Skydio HTTP Client
v0.2
Communicate with a vehicle using HTTP apis.
"""

"""NOTE (8/17/2020): Many parts of this code (like the SecurityBot or Panorama commands) are dependent on the Skydio 
SDK, which is no longer supported. However, this script will allow you to takeoff and land, and will utilize the 
drone's object avoidance capabilities if anything gets too close. 

To connect the Bebop datagloves, you need Windows 10. Make sure both gloves are turned on but NOT PAIRED to the 
computer, then run the script (pairing the gloves interferes with the connection procedure). """

# Prep for python3
from __future__ import absolute_import
from __future__ import print_function

import base64
import json
import os
import requests
import sys
import threading
import time
import serial
import numpy as np
from uuid import uuid4

from dataglove import *
from time import *

try:
    # Python 3
    from urllib.parse import urlparse
except ImportError:
    # Python 2
    from urlparse import urlparse


def fmt_out(fmt, *args, **kwargs):
    """ Helper for printing formatted text to stdout. """
    sys.stdout.write(fmt.format(*args, **kwargs))
    sys.stdout.flush()


def fmt_err(fmt, *args, **kwargs):
    """ Helper for printing formatted text to stderr. """
    sys.stderr.write(fmt.format(*args, **kwargs))
    sys.stderr.flush()


# Gstreamer pipeline description for the vehicle to produce an MJPEG stream over RTP.
JPEG_RTP = """
videoscale ! video/x-raw, width=360, height=240 ! videoconvert ! video/x-raw, format=YUY2
! jpegenc ! rtpjpegpay ! udpsink host={} port={} sync=false
""".replace('\n', ' ')


class HTTPClient(object):
    """
    HTTP client for communicating with a Skydio drone.
    Use this to connect a laptop over Wifi or an onboard computer over ethernet.
    Args:
        baseurl (str): The url of the vehicle.
            If you're directly connecting to a real R1 via WiFi, use 192.168.10.1
            If you're connected to a simulator over the Internet, use https://sim####.sim.skydio.com
        client_id (str): A unique id for this remote user. Used to identify the same device
            accross different runs or different connection methods. Defaults to a new uuid.
        pilot (bool): Set to True in order to directly control the drone. Disables phone access.
        token_file (str): Path to a file that contains the auth token for simulator access.
        stream_settings (dict): Configuration for receiving an RTP video stream.
            This feature is coming soon to R1 and will not work in the simulator.
    """

    def __init__(self, baseurl, client_id=None, pilot=False, token_file=None, stream_settings=None):
        self.client_id = client_id or str(uuid4())
        self.baseurl = baseurl
        self.access_token = None
        self.session_id = None
        self.access_level = None
        self.stream_settings = stream_settings
        self._authenticate(pilot, token_file)

    def _authenticate(self, pilot=False, token_file=None):
        """ Request an access token from the vehicle. If using a sim, a token_file is required. """
        request = {
            'client_id': self.client_id,
            'requested_level': (8 if pilot else 4),
            'commandeer': True,
        }

        if token_file:
            if not os.path.exists(token_file):
                fmt_err("Token file does not exist: {}\n", token_file)
                sys.exit(1)

            with open(token_file, 'r') as tokenf:
                token = tokenf.read()
                request['credentials'] = token.strip()

        response = self.request_json('authentication', request)
        self.access_level = response.get('accessLevel')
        if pilot and self.access_level != 'PILOT':
            fmt_err("Did not successfully auth as pilot\n")
            sys.exit(1)
        self.access_token = response.get('accessToken')
        fmt_out("Received access token:\n{}\n", self.access_token)

    def update_skillsets(self, user_email, api_url=None):
        """
        Update the skillsets available on the vehicle without needing a Skydio Mobile App to do so.
        If this is the first time running this function on this computer an interactive prompt
        will be shown to get the login_code sent to the user_email. Subsequent requests should not.
        Be sure that the user has uploaded a skillset to the Developer Console with the com_link
        skill available. Based on the skillset name you use you will need to provide
        --skill-key <skillset_name>.com_link.ComLink to actually use the skill delivered
        by this function.
        Args:
            user_email (str): The user to download skillsets for, this should match the email
                    used on the Developer Console and on Mobile Apps
            api_url (str): [optional] Override the Skydio Cloud API url to use
        """
        from skydio.cloud.update_util import update_cloud_config_on_vehicle

        return update_cloud_config_on_vehicle(user_email=user_email,
                                              vehicle_url=self.baseurl,
                                              vehicle_access_token=self.access_token,
                                              cloud_url=api_url)

    def request_json(self, endpoint, json_data=None, timeout=20):
        """ Send a GET or POST request to the vehicle and get a parsed JSON response.
        Args:
            endpoint (str): the path to request.
            json_data (dict): an optional JSON dictionary to send.
            timeout (int): number of seconds to wait for a response.
        Raises:
            HTTPError: if the server responds with 4XX or 5XX status code
            IOError: if the response body cannot be read.
            RuntimeError: if the response is poorly formatted.
        Returns:
            dict: the servers JSON response
        """
        url = '{}/api/{}'.format(self.baseurl, endpoint)
        headers = {'Accept': 'application/json'}
        if self.access_token:
            headers['Authorization'] = 'Bearer {}'.format(self.access_token)
        if json_data is not None:
            headers['Content-Type'] = 'application/json'
            res = requests.post(url, json=json_data, headers=headers)
        else:
            res = requests.get(url, headers=headers)

        try:
            res.raise_for_status()
        except requests.HTTPError as err:
            #print(err.message)
            raise

        if res.headers['Content-Type'] == 'application/json':
            try:
                reply = res.json()
            except ValueError as err:
                print('unable to decode json')
                raise
            return reply['data']
        return res

    def send_custom_comms(self, skill_key, data, no_response=False):
        """
        Send custom bytes to the vehicle and optionally return a response
        Args:
            skill_key (str): The identifer for the Skill you want to receive this message.
            data (bytes): The payload to send.
            no_response (bool): Set this to True if you don't want a response.
        Returns:
            dict: a dict with metadata for the response and a 'data' field, encoded by the Skill.
        """

        rpc_request = {
            'data': base64.b64encode(data),
            'skill_key': skill_key,
            'no_response': no_response,  # this key is option and defaults to False
        }

        # Post rpc to the server as json.
        try:
            rpc_response = self.request_json('custom_comms', rpc_request)
        except Exception as error:  # pylint: disable=broad-except
            fmt_err('Comms Error: {}\n', error)
            return None

        # Parse and return the rpc.
        if rpc_response:
            if 'data' in rpc_response:
                rpc_response['data'] = base64.b64decode(rpc_response['data'])
        return rpc_response

    def update_pilot_status(self):
        """ Ping the vehicle to keep session alive and get status back.
        The session will expire after 10 seconds of inactivity from the pilot.
        If the session expires, the video stream will stop.
        """
        args = {
            'inForeground': True,
            'mediaMode': 'FLIGHT_CONTROL',
            'recordingMode': 'VIDEO_4K_30FPS',
            'takeoffType': 'GROUND_TAKEOFF',
            'wouldAcceptPilot': True,
        }
        if self.session_id:
            args['sessionId'] = self.session_id
        if self.stream_settings:
            args['streamSettings'] = self.stream_settings
        response = self.request_json('status', args)
        self.session_id = response['sessionId']
        return response

    def takeoff(self):
        """ Request takeoff. Blocks until flying. """
        if self.access_level != 'PILOT':
            fmt_err('Cannot takeoff: not pilot\n')
            return

        self.update_pilot_status()
        self.disable_faults()

        while True:
            sleep(2)  # downsample to prevent spamming the endpoint
            phase = self.update_pilot_status().get('flightPhase')
            if not phase:
                continue
            # fmt_out('flight phase = {}\n', phase)
            if phase == 'READY_FOR_GROUND_TAKEOFF':
                fmt_out('Publishing ground takeoff\n')
                self.request_json('async_command', {'command': 'ground_takeoff'})
            elif phase == 'FLYING':
                fmt_out('Flying.\n')
                return
            elif phase == 'REST':
                fmt_out('on standby\n')
            elif phase == 'FLIGHT_PROCESSES_CHECK':
                fmt_out('Pre-Flight Check in progress\n')
            elif phase == 'PREP':
                fmt_out('Calibrating Cameras\n')
            elif phase == 'LOGGING_START':
                fmt_out('Initializing flight logs\n')

            else:
                # print the active faults, remove after debug
                fmt_out('Faults = {}\n', ','.join(self.get_blocking_faults()))

    def land(self):
        """ Land the vehicle. Blocks until on the ground. """
        if self.access_level != 'PILOT':
            fmt_err('Cannot land: not pilot\n')
            return

        phase = 'FLYING'
        while phase == 'FLYING':
            fmt_out('Sending LAND\n')
            self.request_json('async_command', {'command': 'land'})
            sleep(1)
            new_phase = self.update_pilot_status().get('flightPhase')
            if not new_phase:
                continue
            phase = new_phase

    def set_skill(self, skill_key):
        """ Request a specific skill to be active. """
        if self.access_level != 'PILOT':
            fmt_err('Cannot switch skills: not pilot\n')
            return
        fmt_out("Requesting {} skill\n", skill_key)
        endpoint = 'set_skill/{}'.format(skill_key)
        self.request_json(endpoint, {'args': {}})

    def get_blocking_faults(self):
        faults = self.request_json('active_faults').get('faults', {})
        return [f['name'] for f in faults.values() if f['relevant']]

    def disable_faults(self):
        """ Tell the vehicle to ignore missing phone info. """
        faults = {
            # These faults occur if phone isn't connected via UDP
            'LOST_PHONE_COMMS_SHORT': 2,
            'LOST_PHONE_COMMS_LONG': 3,
        }
        for _, fault_id in faults.items():
            self.request_json('set_fault_override/{}'.format(fault_id),
                              {'override_on': True, 'fault_active': False})

    def check_min_api_version(self, major=18.0, minor=5.0):
        info = self.request_json('status')['config']['deployInfo']
        return info.get('api_version_major') >= major and info.get('api_version_minor') >= minor

    def get_udp_link_address(self):
        """ Get the dynamic port and hostname for the udp link. """
        resp = self.request_json('status')['config']
        udp_hostname = resp.get('lcmProxyUdpHostname')
        if not udp_hostname:
            udp_hostname = urlparse(self.baseurl).netloc.split(':')[0]
        udp_port = resp.get('lcmProxyUdpPort')
        return (udp_hostname, udp_port)

    def save_image(self, filename):
        """
        Fetch raw image data from the vehicle and and save it as png, using opencv.
        If you need to continuously fetch images from the vehicle, consider using RTP instead.
        """
        import cv2
        import numpy

        t1 = time.time()
        # Fetch the image metadata for the latest color image.
        data = self.request_json('channel/SUBJECT_CAMERA_RIG_NATIVE')
        t2 = time.time()
        fmt_out('Got metadata in {}ms\n', int(1000 * (t2 - t1)))
        images = data['json']['images']
        if not images:
            return

        # Download the raw pixel data from the vehicle's shared memory.
        # Note that this is not a high-speed image api, as it uses uncompressed
        # image data over HTTP.
        image = images[0]
        image_path = image['data']
        url = '{}/shm{}'.format(self.baseurl, image_path)
        try:
            res = requests.get(url)
            image_data = res.content
        except requests.HTTPError as err:
            fmt_err('Got error for url {} {}\n', image_path, err)
            return
        t3 = time.time()
        fmt_out('Got image data in {}ms\n', int(1000 * (t3 - t2)))

        # Convert and save as a PNG
        pixfmt = image['pixelformat']
        PIXELFORMAT_YUV = 1009
        PIXELFORMAT_RGB = 1002
        if pixfmt == PIXELFORMAT_YUV:
            bytes_per_pixel = 2
            conversion_format = cv2.COLOR_YUV2BGR_UYVY
        elif pixfmt == PIXELFORMAT_RGB:
            bytes_per_pixel = 3
            conversion_format = cv2.COLOR_RGB2BGR
        else:
            fmt_err('Unsupported pixelformat {}\n', pixfmt)
            return
        width = image['width']
        height = image['height']
        num_bytes = width * height * bytes_per_pixel
        input_array = numpy.array([numpy.uint8(ord(c)) for c in image_data[:num_bytes]])
        input_array.shape = (height, width, bytes_per_pixel)
        bgr_array = cv2.cvtColor(input_array, conversion_format)
        cv2.imwrite(filename, bgr_array)
        t4 = time.time()
        fmt_out('Saved image in {}ms\n', int(1000 * (t4 - t3)))

        return filename

    def set_run_mode(self, mode_name, set_default=False):
        if set_default:
            action = 'SET_DEFAULT'
        else:
            action = 'TERMINATE_AND_START'
        resp = self.request_json('runmode', {
            'run_mode_name': mode_name,
            'action': action,
        })
        print(resp)

# Setup
stream_settings = {'source': 'NATIVE', 'port': 55004}

# Create Client
try:
    client = HTTPClient('http://192.168.10.1',
                        pilot=True,
                        token_file=0,
                        stream_settings=stream_settings)
except(OSError):
    print("Failed to connect to drone! Exiting...")
    exit()


# Periodically poll the status endpoint to keep ourselves the active pilot.
def update_loop():
    while True:
        client.update_pilot_status()
        sleep(2)


status_thread = threading.Thread(target=update_loop)
status_thread.setDaemon(True)
status_thread.start()

# This script utilizes multiple threads in order to interact with both gloves independently of each other.

leftHand = Forte_CreateDataGloveIO(1, "")  # 1 for left-handed glove
rightHand = Forte_CreateDataGloveIO(0, "")  # 0 for right-handed glove

#adjust this value to control haptic playback speed (int ranging from 0 to 127)
note = 60

#adjust this value to control haptic amplitude (float ranging from 0.0 to 1.0)
amplitude = 1

def calibrate():
    neutralL = 0
    neutralR = 0
    initial = 0
    x = 0

    try:

        while (neutralL == 0 and neutralR == 0):
            try:
                if(initial == 0):

                    # prevents the glove from calibrating before the user is ready
                    previousXL = 1000
                    previousYL = 1000
                    previousZL = 1000

                    previousXR = 1000
                    previousYR = 1000
                    previousZR = 1000

                    #pause to allow gloves to to finish connecting, so PRINT commands don't get buried
                    sleep(5)

                    for i in range(6):
                        Forte_SelectHapticWave(leftHand, i, 15)
                        Forte_SelectHapticWave(rightHand, i, 15)

                        Forte_SendHaptic(leftHand, i, note, amplitude)
                        Forte_SendHaptic(rightHand, i, note, amplitude)

                    print("Please hold both hands flat with fingers extended and palms towards the ground for calibration:")


                    sleep(0.75)
                    Forte_SilenceHaptics(leftHand)
                    Forte_SilenceHaptics(rightHand)
                    initial = 1

                sleep(1)
                print("Calibrating...")

                Forte_SendHaptic(leftHand, 5, note, amplitude)
                Forte_SendHaptic(rightHand, 5, note, amplitude)
                sleep(0.1)
                Forte_SilenceHaptics(leftHand)
                Forte_SilenceHaptics(rightHand)


                leftIMU = Forte_GetEulerAngles(leftHand)
                XL = leftIMU[2]
                ZL = leftIMU[1]
                YL = leftIMU[0]

                rightIMU = Forte_GetEulerAngles(rightHand)
                XR = rightIMU[2]
                ZR = rightIMU[1]
                YR = rightIMU[0]

                if (-10 <= XL - previousXL <= 10 and -10 <= YL - previousYL <= 10 and -10 <= ZL - previousZL <= 10 and -10 <= XR - previousXR <= 10 and -10 <= YR - previousYR <= 10 and -10 <= ZR - previousZR <= 10):

                    # set current position of finger sensors to 0, and set IMU home-point
                    Forte_CalibrateFlat(leftHand)
                    Forte_HomeIMU(leftHand)

                    Forte_CalibrateFlat(rightHand)
                    Forte_HomeIMU(rightHand)
                    print("CALIBRATION SUCCESSFUL!  Commands can now be sent.")

                    # Send 2 quick haptic pulses to all actuators to signal that the gloves are calibrated.
                    for i in range(6):
                        Forte_SelectHapticWave(leftHand, i, 15)
                        Forte_SelectHapticWave(rightHand, i, 15)

                        Forte_SendHaptic(leftHand, i, note, amplitude)
                        Forte_SendHaptic(rightHand, i, note, amplitude)

                    sleep(0.3)
                    Forte_SilenceHaptics(leftHand)
                    Forte_SilenceHaptics(rightHand)
                    for i in range(6):
                        Forte_SelectHapticWave(leftHand, i, 15)
                        Forte_SelectHapticWave(rightHand, i, 15)

                        Forte_SendHaptic(leftHand, i, note, amplitude)
                        Forte_SendHaptic(rightHand, i, note, amplitude)
                    sleep(0.5)
                    Forte_SilenceHaptics(leftHand)
                    Forte_SilenceHaptics(rightHand)
                    sleep(2)

                    # prevent the calibration procedure from being reentered
                    neutralL = 1
                    neutralR = 1

                # saves the previous hand data to track motion
                previousXL = XL
                previousYL = YL
                previousZL = ZL

                previousXR = XR
                previousYR = YR
                previousZR = ZR


            except(GloveDisconnectedException):
                print("Disconnected...")
                sleep(1)
                pass

    except(KeyboardInterrupt):
        Forte_DestroyDataGloveIO(leftHand)
        Forte_DestroyDataGloveIO(rightHand)
        exit()

def left_hand():

   #function to receive input from the left hand

    try:
        while True:
            try:

                #LEFT HAND SETUP

                for i in range(6):
                    Forte_SelectHapticWave(leftHand, i, 15)

                leftfingers = Forte_GetFingersNormalized(leftHand)
                Lthumb = round(leftfingers[0], 4)
                Lindex = round(leftfingers[1], 4)
                Lmiddle = round(leftfingers[2], 4)
                Lring = round(leftfingers[3], 4)
                Lpinky = round(leftfingers[4], 4)

                Lhand = Lthumb + Lindex + Lmiddle + Lring + Lpinky

                leftIMU = Forte_GetEulerAngles(leftHand)
                XL = leftIMU[2]
                ZL = leftIMU[1]
                YL = leftIMU[0]

                # Remove quotations to view data output from left-hand glove
                """print("L:", Lthumb, Lindex, Lmiddle, Lring, Lpinky)
                print("L:", XL, YL, ZL)
                sleep(1)"""

                # LEFT HAND GESTURES
                # THUMBS-UP
                if (
                        Lindex - Lthumb >= 0.243 and Lmiddle - Lthumb >= 0.243 and Lring - Lthumb >= 0.243 and Lpinky - Lthumb >= 0.243 and YL >= 60):
                    print("THUMBS UP")

                    Forte_SendHaptic(leftHand, 0, note, amplitude)
                    Forte_SendHaptic(leftHand, 5, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)

                    droneidle = False
                    """print("TAKING OFF")
                    client.takeoff()"""
                    sleep(2)

                # PEACE SIGN
                elif (Lring - Lmiddle >= 0.243 and Lpinky - Lindex >= 0.243 and Lthumb >= 0.04049):
                    print("PEACE")

                    Forte_SendHaptic(leftHand, 1, note, amplitude)
                    Forte_SendHaptic(leftHand, 2, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)

                    droneidle = False
                    print("Sentry Mode Active")
                    #client.set_skill("security_bot")
                    sleep(2)

                # GO BULLS (PALM POINTING AWAY FROM YOU)
                elif (
                        Lmiddle - Lindex >= 0.243 and Lring - Lpinky >= 0.243 and Lindex <= 0.243 and Lpinky <= 0.243 and (
                        0 >= XL >= -120) and (25 >= YL >= -25)):
                    print("GO BULLS")

                    Forte_SendHaptic(leftHand, 1, note, amplitude)
                    Forte_SendHaptic(leftHand, 4, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)

                    droneidle = False
                    #print("SCANNING AREA")
                    #client.set_skill("pano")
                    sleep(2)

                # RAISED FIST ('HALT')
                elif (Lthumb >= 0.12146 and Lindex >= 0.243 and Lmiddle >= 0.243 and Lhand >= 2.22672 and (
                        0 >= XL >= -120) and (25 >= YL >= -25)):
                    print("HALT")

                    Forte_SendHaptic(leftHand, 5, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)

                    droneidle = False
                    # skill to be inserted here
                    sleep(2)

                # FLAT PALM WITH FINGERS EXTENDED ('LAND')
                elif (Lthumb <= 0.080972 and Lindex <= 0.080972 and Lmiddle <= 0.080972 and Lring <= 0.080972 and Lpinky <= 0.080972 and (-25 <= XL <= 25) and (-25 <= YL <= 25)):
                    print("LAND")

                    for i in range(6):
                        Forte_SendHaptic(leftHand, i, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)

                    droneidle = False
                    print("LANDING")
                    client.land()
                    sleep(2)


            except(GloveDisconnectedException):
                print("Gloves are disconnected...")
                sleep(1)

                # Fail-safe to land the drone if connection is lost.  Otherwise it would continue to fly
                # until receiving a new signal.
                client.land()
                pass

    except(KeyboardInterrupt):
        Forte_DestroyDataGloveIO(leftHand)
        exit()


def right_hand():
   # Function to receive input from the right hand

    try:
        while True:
            try:

                #RIGHT HAND SETUP

                for i in range(6):
                    Forte_SelectHapticWave(rightHand, i, 15)

                rightfingers = Forte_GetFingersNormalized(rightHand)
                Rthumb = round(rightfingers[0], 4)
                Rindex = round(rightfingers[1], 4)
                Rmiddle = round(rightfingers[2], 4)
                Rring = round(rightfingers[3], 4)
                Rpinky = round(rightfingers[4], 4)

                Rhand = Rthumb + Rindex + Rmiddle + Rring + Rpinky

                rightIMU = Forte_GetEulerAngles(rightHand)
                XR = rightIMU[2]
                ZR = rightIMU[1]
                YR = rightIMU[0]

                # Remove quotations to view data output from right-hand glove
                """print("R:", Rthumb, Rindex, Rmiddle, Rring, Rpinky)
                print("R:", XR, YR, ZR)
                sleep(1)"""

                # RIGHT HAND GESTURES
                # THUMBS-UP
                if (
                        Rindex - Rthumb >= 0.243 and Rmiddle - Rthumb >= 0.243 and Rring - Rthumb >= 0.243 and Rpinky - Rthumb >= 0.243 and YR <= -60):
                    print("THUMBS UP")

                    Forte_SendHaptic(rightHand, 0, note, amplitude)
                    Forte_SendHaptic(rightHand, 5, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)

                    droneidle = False
                    print("TAKING OFF")
                    client.takeoff()
                    sleep(2)

                # PEACE SIGN
                elif (Rring - Rmiddle >= 0.243 and Rpinky - Rindex >= 0.243 and Rthumb >= 0.04049):
                    print("PEACE")

                    Forte_SendHaptic(rightHand, 1, note, amplitude)
                    Forte_SendHaptic(rightHand, 2, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)

                    droneidle = False
                    print("Sentry Mode Active")
                    #client.set_skill("security_bot")
                    sleep(2)

                # GO BULLS (PALM POINTING AWAY FROM YOU)
                elif (Rmiddle - Rindex >= 0.243 and Rring - Rpinky >= 0.243 and Rindex <= 0.243 and Rpinky <= 0.243 and (0 >= XR >= -120) and (25 >= YR >= -25)):
                    print("GO BULLS")

                    Forte_SendHaptic(rightHand, 1, note, amplitude)
                    Forte_SendHaptic(rightHand, 4, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)

                    droneidle = False
                    #print("SCANNING AREA")
                    #client.set_skill("pano")
                    sleep(2)

                # RAISED FIST ('HALT')
                elif (Rthumb >= 0.12146 and Rindex >= 0.243 and Rmiddle >= 0.243 and Rhand >= 2.22672 and (0 >= XR >= -120) and (25 >= YR >= -25)):
                    print("HALT")

                    Forte_SendHaptic(rightHand, 5, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)

                    droneidle = False
                    # skill to be inserted here
                    sleep(2)

                # FLAT PALM WITH FINGERS EXTENDED ('LAND')
                elif (Rthumb <= 0.080972 and Rindex <= 0.080972 and Rmiddle <= 0.080972 and Rring <= 0.080972 and Rpinky <= 0.080972 and (-25 <= XR <= 25) and (-15 <= YR <= 25)):
                    print("LAND")

                    for i in range(6):
                        Forte_SendHaptic(rightHand, i, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)

                    droneidle = False
                    print("LANDING")
                    client.land()
                    sleep(2)

            except(GloveDisconnectedException):
                print("Gloves are disconnected...")
                sleep(1)

                # Fail-safe to land the drone if connection is lost.  Otherwise it would continue to fly
                # until receiving a new signal.
                client.land()
                pass

    except(KeyboardInterrupt):
        Forte_DestroyDataGloveIO(rightHand)
        exit()

if __name__ == "__main__":

    # Creating bootup thread to calibrate both gloves
    t0 = threading.Thread(target=calibrate)

    # Starting calibration procedure threaad:
    t0.start()

    # Pause once calibration is successful, then move onto the two main threads
    t0.join()
    sleep(3)

    # Creating threads for left and right hands to run simultaneously
    left = threading.Thread(target=left_hand)
    right = threading.Thread(target=right_hand)

    # Starting thread 1
    left.start()
    # Starting thread 2
    right.start()

    # Thread closing
    left.join()
    right.join()
