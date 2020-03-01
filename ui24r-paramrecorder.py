#!/bin/env python3

# pip install websocket-client

import websocket
import re
import os
from pathlib import Path
try:
    import thread
except ImportError:
    import _thread as thread
import time
from datetime import datetime

ipAdress = "10.0.1.124"
dataContainer = {}
armed = False
outputDir = None
recFile = None
recStartTime = 0
recStateRemote = 0
sessionName = ""

def on_message(ws, message):
    # we often get multiline messages. process each line separately
    for line in message.split('\n'):
        if line == "2::":
            # skip useless messages
            continue

        if line[:4] == "3:::":
            # remove unneeded prefix of each websocket message in case it exists
            line = line[4:]

        if line[:4] == "RTA^" or line[:4] == "VU2^" or line[:4] == "VUA^":
            # skip all those realtime data thats only needed for visualizing audio
            continue


        match = re.match('^SET([DS])\^([^\^]*)\^(.*)$', line)
        if not match:
            # @TODO: do we need some other stuff that gets dropped here?
            continue

        handleParam(match.group(2), castValue( match.group(1),  match.group(3) ))


def castValue(valueType, value):
    if valueType == "S":
        return value
    if value == "0" or value == "1":
        return int(value)
    return float(value)


# we need 3 parameters to be able to persist recording:
#  *) recStateRemote: the record status of the ui24r
#  *) the current time of ui24r's recording
#  *) the session name to be able to create a directory for persisting in filesystem
#
# only when we have all of these we can start the recording
# but we have to apply an offset (timestamp correction) of x seconds int the past as soon as we have everything we need for recording



def handleParam(paramName, paramValue):
    global armed, sessionName, recStateRemote, recStartTime, dataContainer
    dataContainer[ paramName ] = paramValue

    #if paramName in [ "var.mtk.rec.currentState", "var.mtk.rec.time", "var.mtk.rec.session"]:
    #    print("               %i %s %s" % (int(round(time.time() * 1000)), paramName, paramValue))

    if paramName == "var.mtk.rec.currentState":
        recStateRemote = paramValue
        print( "SET recStateRemote to %i " % recStateRemote)
        if recStateRemote == 1:
            recStartTime = 0
            print( "SET recStartTime to %i " % recStartTime )

    if paramName == "var.mtk.rec.session":
        sessionName = paramValue
        print( "SET sessionName to %s " % sessionName)

    # too bad we do not have a session name after first second of recording
    # so apply the offset into the past
    if paramName == "var.mtk.rec.time" and recStartTime == 0:
        if recStateRemote == 1:
            recStartTime = int(round(time.time() * 1000)) - (1000 * paramValue)
            print( "SET recStartTime to %i " % recStartTime )


    if armed == False and sessionName != "" and recStateRemote == 1 and recStartTime > 0:
        recStart()

    if armed == True and recStateRemote == 0:
        recStop()

    if armed == True:
        recordParamChange(paramName, paramValue)



def recStart():
    global armed, sessionName, recFile

    

    # include current second in recording to avoid conflicts
    recFile = Path(
        "%s/recordings/%s-recsession-%s.txt" % (
            os.path.dirname(os.path.abspath(__file__)),
            datetime.today().strftime('%Y.%m.%d--%H.%M.%S'),
            sessionName
        )
    )
    # dump all data to have initial param values
    dumpAllToFile()
    print("recStart")
    armed = True


def dumpAllToFile():
    global dataContainer, recFile

    f = recFile.open("a")
    for key, value in dataContainer.items():
        f.write("0 %s %s\n" % (key, value))

    f.close()

def recordParamChange(paramName, paramValue):
    global recFile
    if isBlacklisted(paramName):
        return
    with recFile.open("a") as f:
        f.write("%s %s %s\n" % (getRelativeTime(), paramName, paramValue))

def isBlacklisted(paramName):
    blackList = [
        "var.mtk.bufferfill",
        "var.mtk.freespace",
        "var.mtk.rec.time"
    ]
    return paramName in blackList

def getRelativeTime():
    global recStartTime
    return (float(round(time.time() * 1000)) - recStartTime) / 1000


def recStop():
    global armed, recStartTime
    armed = False
    recStartTime = 0
    print("recStop")

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("### closed ###")

def on_open(ws):
    def run(*args):
        while True:
            ws.send("3:::ALIVE")
            time.sleep(1)

        print("thread terminating...")
    thread.start_new_thread(run, ())


if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        "ws://%s/socket.io/1/websocket" % ipAdress,
        on_message = on_message,
        on_error = on_error,
        on_close = on_close
    )
    ws.on_open = on_open
    ws.run_forever()