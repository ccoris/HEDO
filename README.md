# Hyper-Enabled Drone Operator

This project serves as a proof-of-concept system to fly a Skydio drone using a set of Bebop Forte Data-Gloves.  Several test scripts for the data-gloves are also included to make development easier.

## Installation

Use pip package manager to install the dataglove Python library, as well as any other libraries you might be missing.

```bash
pip install dataglove
```

## Run

1. Conect to the Skydio Drone via WiFi (192.168.10.1).
2. Make sure to turn on Bluetooth on your computer, and turn on data-gloves but DO NOT pair them to your device (this will interfere with the connection process).
3. Run HEDO.py (make sure to follow the calibration procedure upon boot-up to ensure proper function).

## Commands

1. Thumbs-Up: Take Off
2. Flat Hand (palm downward): Land
3. 'Go Bulls': unassigned
4. Peace Sign: unassigned
5. Raised Fist 'Halt': unassigned

## Dataglove Library

All functions for Bebop's Data-Glove library can be found [HERE](https://pypi.org/project/dataglove/)

An older version of this project can be found [HERE](https://github.com/sofwerx/dataglove)


