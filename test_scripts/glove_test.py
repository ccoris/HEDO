from dataglove import *
from time import *
import threading

# This script utilizes multiple threads in order to interact with both gloves independently of each other.

leftHand = Forte_CreateDataGloveIO(1, "")  # 1 for left-handed glove
rightHand = Forte_CreateDataGloveIO(0, "")  # 0 for right-handed glove

#adjust this value to control haptic playback speed (int ranging from 0 to 127)
note = 50

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
                    print("CALIBRATION SUCCESSFUL!")

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
                    sleep(0.4)
                    Forte_SilenceHaptics(leftHand)
                    Forte_SilenceHaptics(rightHand)
                    sleep(4)

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
                """print("fingers:", Lthumb, Lindex, Lmiddle, Lring, Lpinky)
                print("IMU:", XL, YL, ZL)
                sleep(1)"""

                # LEFT HAND GESTURES
                # THUMBS-UP
                if (
                        Lindex - Lthumb >= 0.243 and Lmiddle - Lthumb >= 0.243 and Lring - Lthumb >= 0.243 and Lpinky - Lthumb >= 0.243 and YL >= 60):
                    print("L: THUMBS UP")

                    Forte_SendHaptic(leftHand, 0, note, amplitude)
                    Forte_SendHaptic(leftHand, 5, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)
                    sleep(2)

                # PEACE SIGN
                elif (Lring - Lmiddle >= 0.243 and Lpinky - Lindex >= 0.243 and Lthumb >= 0.04049):
                    print("L: PEACE")

                    Forte_SendHaptic(leftHand, 1, note, amplitude)
                    Forte_SendHaptic(leftHand, 2, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)
                    sleep(2)

                # GO BULLS (PALM POINTING AWAY FROM YOU)
                elif (
                        Lmiddle - Lindex >= 0.243 and Lring - Lpinky >= 0.243 and Lindex <= 0.243 and Lpinky <= 0.243 and (
                        0 >= XL >= -120) and (25 >= YL >= -25)):
                    print("L: GO BULLS")

                    Forte_SendHaptic(leftHand, 1, note, amplitude)
                    Forte_SendHaptic(leftHand, 4, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)
                    sleep(2)

                # RAISED FIST ('HALT')
                elif (Lthumb >= 0.12146 and Lindex >= 0.243 and Lmiddle >= 0.243 and Lhand >= 2.22672 and (
                        0 >= XL >= -120) and (25 >= YL >= -25)):
                    print("L: HALT")

                    Forte_SendHaptic(leftHand, 5, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)
                    sleep(2)

                # FLAT PALM WITH FINGERS EXTENDED ('LAND')
                elif (Lthumb <= 0.080972 and Lindex <= 0.080972 and Lmiddle <= 0.080972 and Lring <= 0.080972 and Lpinky <= 0.080972 and (-25 <= XL <= 25) and (-25 <= YL <= 25)):
                    print("L: LAND")

                    for i in range(6):
                        Forte_SendHaptic(leftHand, i, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(leftHand)
                    sleep(2)


            except(GloveDisconnectedException):
                print("Gloves are disconnected...")
                sleep(1)
                pass
    except(KeyboardInterrupt):
        Forte_DestroyDataGloveIO(leftHand)
        exit()


def right_hand():

   #function to receive input from the right hand

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
                """print("fingers:", Rthumb, Rindex, Rmiddle, Rring, Rpinky)
                print("IMU:", XR, YR, ZR)
                sleep(1)"""

                # RIGHT HAND GESTURES
                # THUMBS-UP
                if (
                        Rindex - Rthumb >= 0.243 and Rmiddle - Rthumb >= 0.243 and Rring - Rthumb >= 0.243 and Rpinky - Rthumb >= 0.243 and YR <= -60):
                    print("R: THUMBS UP")

                    Forte_SendHaptic(rightHand, 0, note, amplitude)
                    Forte_SendHaptic(rightHand, 5, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)
                    sleep(2)

                # PEACE SIGN
                elif (Rring - Rmiddle >= 0.243 and Rpinky - Rindex >= 0.243 and Rthumb >= 0.04049):
                    print("R: PEACE")

                    Forte_SendHaptic(rightHand, 1, note, amplitude)
                    Forte_SendHaptic(rightHand, 2, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)
                    sleep(2)

                # GO BULLS (PALM POINTING AWAY FROM YOU)
                elif (Rmiddle - Rindex >= 0.243 and Rring - Rpinky >= 0.243 and Rindex <= 0.243 and Rpinky <= 0.243 and (0 >= XR >= -120) and (25 >= YR >= -25)):
                    print("R: GO BULLS")

                    Forte_SendHaptic(rightHand, 1, note, amplitude)
                    Forte_SendHaptic(rightHand, 4, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)
                    sleep(2)

                # RAISED FIST ('HALT')
                elif (Rthumb >= 0.12146 and Rindex >= 0.243 and Rmiddle >= 0.243 and Rhand >= 2.22672 and (0 >= XR >= -120) and (25 >= YR >= -25)):
                    print("R: HALT")

                    Forte_SendHaptic(rightHand, 5, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)
                    sleep(2)

                # FLAT PALM WITH FINGERS EXTENDED ('LAND')
                elif (Rthumb <= 0.080972 and Rindex <= 0.080972 and Rmiddle <= 0.080972 and Rring <= 0.080972 and Rpinky <= 0.080972 and (-25 <= XR <= 25) and (-15 <= YR <= 25)):
                    print("R: LAND")

                    for i in range(6):
                        Forte_SendHaptic(rightHand, i, note, amplitude)
                    sleep(0.1)
                    Forte_SilenceHaptics(rightHand)
                    sleep(2)

            except(GloveDisconnectedException):
                print("Gloves are disconnected...")
                sleep(1)
                pass
    except(KeyboardInterrupt):
        Forte_DestroyDataGloveIO(rightHand)
        exit()


if __name__ == "__main__":

    # creating bootup thread to calibrate both gloves
    t0 = threading.Thread(target=calibrate)

    #starting bootup calibration procedure:
    t0.start()

    #pause once calibration is successful, then move onto the two main threads
    t0.join()
    sleep(3)

    #creating threads for left and right hands to run simultaneously
    left = threading.Thread(target=left_hand)
    right = threading.Thread(target=right_hand)

    # starting thread 1
    left.start()
    # starting thread 2
    right.start()

    #in case threads are ever completely executed
    left.join()
    right.join()

