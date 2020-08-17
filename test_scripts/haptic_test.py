from dataglove import *
from time import *

"""This script allows for testing the 6 haptic actuators within the gloves (using only one glove for simplicity's sake)

actuatorIDs: 0 = thumb, 1 = index, 2 = middle, 3 = ring, 4 = pinky, 5 = palm

The actuators contain 16 wav slots, numbered 0-15 with various sounds pre-loaded.
The final three slots are single-cycle waveforms---triangle, sawtooth, and sinusoid.

amplitude = waveform amplitude (float ranging from 0.0 to 1.0)
note = playback speed (int ranging from 0 to 127)"""

rightHand = Forte_CreateDataGloveIO(0, "") # 0 for right-hand, 1 for left-hand

note = 50
amplitude = 1

try:

    while True:
    
        try:

            print("Sending haptic pulse...")

            for x in range(6):
                Forte_SelectHapticWave(rightHand, x, 15)
                Forte_SendHaptic(rightHand, x, note, amplitude)

            sleep(0.1)
            Forte_SilenceHaptics(rightHand)
            sleep(1)


        except(GloveDisconnectedException):
            print("Glove is Disconnected")
            sleep(1)
            pass

except(KeyboardInterrupt):
    Forte_DestroyDataGloveIO(rightHand)
    exit()

