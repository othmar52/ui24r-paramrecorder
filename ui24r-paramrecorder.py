#!/bin/env python3

# pip install websocket-client

import websocket
import re
from pathlib import Path
try:
    import thread
except ImportError:
    import _thread as thread
import time

dataContainer = {}
armed = False
recDir = None
recStartTime = 0
recStateRemote = 0
sessionName = ""

def on_message(ws, message):
    for line in message.split('\n'):
        if line == "2::":
            continue
        if line[:4] == "3:::":
            # remove line prefix
            line = line[4:]

        if line[:4] == "RTA^" or line[:4] == "VU2^" or line[:4] == "VUA^":
            continue

        match = re.match('^SET([DS])\^([^\^]*)\^(.*)$', line)
        if not match:
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



def recStart():
    global armed

    #Path(os.path.dirname(os.path.abspath(__file__)))


    armed = True
    print("recStart")

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
        #for i in range(3):
        #    time.sleep(1)
        #    ws.send("3:::ALIVE")
        while True:
            ws.send("3:::ALIVE")
            time.sleep(1)
            #print ( dataContainer )
        #time.sleep(1)
        #ws.close()
        print("thread terminating...")
    thread.start_new_thread(run, ())


if __name__ == "__main__":
    #websocket.enableTrace(True)
    ws = websocket.WebSocketApp("ws://10.0.1.124/socket.io/1/websocket",
                              on_message = on_message,
                              on_error = on_error,
                              on_close = on_close)
    ws.on_open = on_open
    ws.run_forever()