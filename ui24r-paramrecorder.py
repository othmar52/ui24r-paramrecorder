#!/bin/env python3

# pip install websocket-client

import websocket
import logging
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
recFile = None
recStartTime = 0
recStateRemote = 0
sessionName = ""

def main():
    logging.basicConfig(level=logging.INFO)
    createWebSocket(ipAdress)

def onSocketMessage(ws, message):
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
    global sessionName, recStateRemote, recStartTime, dataContainer
    dataContainer[ paramName ] = paramValue

    if paramName == "var.mtk.rec.currentState":
        recStateRemote = paramValue
        if recStateRemote == 1:
            recStartTime = 0

    if paramName == "var.mtk.rec.session":
        sessionName = paramValue

    # too bad we do not have a session name after first second of recording
    # so apply the offset into the past
    if paramName == "var.mtk.rec.time" and recStartTime == 0:
        if recStateRemote == 1:
            recStartTime = int(round(time.time() * 1000)) - (1000 * paramValue)

    if armed == False and sessionName != "" and recStateRemote == 1 and recStartTime > 0:
        recStart()

    if armed == True:
        recordParamChange(paramName, paramValue)
        if recStateRemote == 0:
            recStop()



def recStart():
    global armed, recFile

    # include current second in filename to avoid conflicts
    recFile = Path(
        "%s/recordings/%s-recsession-%s.uiparamrecording.txt" % (
            os.path.dirname(os.path.abspath(__file__)),
            datetime.today().strftime('%Y.%m.%d--%H.%M.%S'),
            sessionName
        )
    )
    # dump all data to have initial param values
    dumpAllToFile()
    logging.info("started recording to file:\n %s" % str(recFile))

    # theoretically we have had an untracked param change during the last few miliseconds
    # @TODO: is it necessary to collect those and append?
    armed = True


def dumpAllToFile():
    global recFile

    f = recFile.open("a")
    for key, value in dataContainer.items():
        f.write("0 %s %s\n" % (key, value))

    f.close()

def recordParamChange(paramName, paramValue):
    global recFile
    if isBlacklisted(paramName):
        return

    logging.debug("recording param: %s -> %s" % (paramName, paramValue))
    with recFile.open("a") as f:
        f.write("%s %s %s\n" % (getRelativeTime(), paramName, paramValue))

def isBlacklisted(paramName):
    blackList = [
        "var.mtk.bufferfill",
        "var.mtk.freespace"
    ]
    return paramName in blackList

def getRelativeTime():
    return (float(round(time.time() * 1000)) - recStartTime) / 1000


def recStop():
    global armed, recStartTime
    armed = False
    recStartTime = 0
    logging.info("recording stopped")

def onSocketError(ws, error):
    logging.critical("socket error %s" % error)

def onSocketClose(ws):
    print("### closed ###")

def onSocketOpen(ws):
    logging.info("connecting to %s" % ws.url)
    def run(*args):
        logging.info("connection established")
        while True:
            ws.send("3:::ALIVE")
            time.sleep(1)

        print("thread terminating...")
    thread.start_new_thread(run, ())


# @TODO: handle connect error
def createWebSocket(ip):
    ws = websocket.WebSocketApp(
        "ws://%s/socket.io/1/websocket" % ip,
        on_message = onSocketMessage,
        on_error = onSocketError,
        on_close = onSocketClose
    )
    ws.on_open = onSocketOpen
    ws.run_forever()

if __name__ == "__main__":
    main()