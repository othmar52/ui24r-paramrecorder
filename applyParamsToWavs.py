#!/bin/env python3
# -*- coding: utf-8 -*-


import logging
import os
import re
import time
import glob
import math
import json
import subprocess
from shutil import copyfile, copytree
from pathlib import Path



# the directory with all textfile-recordings generated by `ui24r-paramrecorder.py`
paramRecordingsDir = None

# the storage that was attached to the Ui24r during recording. usually `<storage-path>/Multitrack`
audioRecordingsDir = None

# the directory where the post processed audio files gets written to
outputRootDir = None

# the directory for the track within the outputRootDir
outputDir = None

# combine stereoLinked channels to a stereo file? (Ui24R ignores stereoLink when creating audio recorings)
convertMonoToStereo = True




paramRecFile = None
applyFilterFile = None
allParams = []



class Param(object):
    def __init__(self, paramList):
        self.time = float(paramList[0])
        self.name = str(paramList[1])
        self.value = paramList[2]



def runStuff():
    global recPath, allParams, paramRecordingsDir, audioRecordingsDir, outputRootDir, applyFilterFile

    paramRecordingsDir = Path(
        "%s/recordings" % os.path.dirname(os.path.abspath(__file__))
    )
    audioRecordingsDir = Path(
        "%s/recordings" % os.path.dirname(os.path.abspath(__file__))
    )
    outputRootDir = Path(
        "%s/processedAudio" % os.path.dirname(os.path.abspath(__file__))
    )

    applyFilterFile = Path(
        "%s/recordings/tmp_applyFilter.txt" % os.path.dirname(os.path.abspath(__file__))
    )

    findAndProcessInputPairs()

    print("Done! hopefully...")




'''
    marry audio recording directory with paramsRecordings file
'''
def findAndProcessInputPairs():
    global allParams, paramRecordingsDir, audioRecordingsDir, paramRecFile, applyFilterFile, outputRootDir, outputDir


    allRecoringDirectories = [f.path for f in os.scandir(str(audioRecordingsDir)) if f.is_dir()]

    for trackDir in allRecoringDirectories:
        sessionName = Path(trackDir).stem
        trackConfigFile = Path("%s/.uirecsession" % trackDir)
        
        outputDir = Path("%s/%s-processed" % (str(outputRootDir), sessionName))
        outputDir.mkdir(parents=True, exist_ok=True)
        if not trackConfigFile.is_file():
            print("WARNING: cant find .uirecsession file for session dir")
            print("  TODO: does it make sense to simply copy the directory to target?")
            continue

        copyfile(str(trackConfigFile), ('%s/.uirecsession'% str(outputDir)))

        trackConfigJson = json.loads(getFileContent( str(trackConfigFile) ) )

        for key, channelString in enumerate(trackConfigJson["mapping"]):
            channelIndex = int(re.sub("[^0-9]", "", channelString))
            audioFileName = trackConfigJson["files"][key] + trackConfigJson["ext"]
            paramRecordingFile = searchParamRecordingsFileNameForSession(sessionName)

            if not paramRecordingFile:
                print("WARNING: cant find params recordings file for audio track")
                print("  TODO: does it make sense to simply copy the audio file to target?")
                continue

            paramRecFile = Path(paramRecordingFile)
            allParams = getFileContent(str(paramRecFile)).split('\n')

            audioInputFile = str(Path(trackDir + '/' + audioFileName))
            audioOutputFile = Path("%s/%s" % (str(outputDir), audioFileName))

            filteredParams = grabVolumeParametersForInput(channelIndex)

            filterLines = convertVolumeParamsToFilterArguments(filteredParams, channelIndex)

            applyFilterFile.write_text(',\n'.join(filterLines))

            applyFilter(audioInputFile, applyFilterFile, audioOutputFile)




def searchParamRecordingsFileNameForSession(sessionKey):
    global paramRecordingsDir
    return guessBestParamRecordingsFile(
        glob.glob(
            "%s/*-recsession-%s.txt" % (
                str(paramRecordingsDir),
                sessionKey
            )
        )
    )


def guessBestParamRecordingsFile(foundFiles):

    if len(foundFiles) == 0:
        return None

    if len(foundFiles) == 1:
        #nothing to guess 
        return foundFiles.pop()

    # TODO: theoretically we can have multiple paramRecordings with this key as its a number between 0000 and 9999
    #   we are able to compare fileName with "i.<index>.name" and/or audio file duration with paramRecording duration
    #   probably the very last file is the latest and most relevant file?
    # but for now give a shit on this edge case and return the last found file ( TODO: is sorting correct?)
    return foundFiles.pop()


'''
    convertVolumeParamsToFilterArguments()
    based on volume relevant parameters we have to build audio filter settings for ffmpeg

    @param list filteredParams: a list with paramater instances. already filtered for a single input channel
    @param int currentInputIndex: the inputIndex of the current channel
    @return list the list with the actual audio filter syntax for ffmpeg
'''
def convertVolumeParamsToFilterArguments(filteredParams, currentInputIndex):

    # the list that gets returned by this method
    filterLines = []

    # helper var to maybe ignore volume changes
    currentlyMuted = "0"

    # helper vars to track whats already persisted as a filter argument
    lastPersistedEndtime = 0
    lastPersistedVolume = 0

    # actual volume may gets overriden because of mute
    volumeToCheck = 0
    lastCheckedVolume = 0

    # after unmuting we have to apply the last tracked volume again
    lastTrackedVolume = 0

     # loop over all params and apply the volume value as soon as it changes
    for param in filteredParams:

        if param.name == "i.%i.mix" % currentInputIndex:
            volumeToCheck = param.value
            lastTrackedVolume = param.value

        if param.name == "i.%i.mute" % currentInputIndex:
            currentlyMuted = param.value
            if param.value == '0':
                volumeToCheck = lastTrackedVolume

        if currentlyMuted == '1':
            volumeToCheck = 0

        if lastPersistedVolume != volumeToCheck and param.time > 0:
            filterLines.append(
                "volume=enable='between(t,%s,%s)':volume='%s':eval=frame" % (
                    lastPersistedEndtime,
                    param.time,
                    lastCheckedVolume # float2Db(lastCheckedVolume)
                )
            )
            lastPersistedEndtime = param.time
            lastPersistedVolume = volumeToCheck

        lastCheckedVolume = volumeToCheck

    # apply the very last line until end position of the audio file.
    # as endtime we use an hopefully out-of-range value of 100000 seconds
    # in case this gets changed/invalid in ffmpeg in future we have to
    # determine the actual end position/duration of the audio file
    #duration = detectDuration(inputFile)
    # alternatively we can rely on .uirecsession:lengthSeconds
    duration = 100000
    filterLines.append(
        "volume=enable='between(t,%s,%s)':volume='%s':eval=frame" % (
            lastPersistedEndtime,
            duration,
            lastCheckedVolume # float2Db(lastCheckedVolume)
        )
    )
    return filterLines

'''
    currently not used
    @see comment above regarding out-of-range duration
'''
def detectDuration(filePath):
    cmd = [
        'ffprobe', '-i', str(filePath),
        '-show_entries', 'format=duration',
        '-v', 'quiet', '-of', 'csv=p=0'
    ]
    processStdOut = generalCmd(cmd, 'detect duration')
    return float(processStdOut.strip())




'''
    filterParamsForInput()
    pick only the params that are relevant for the single audio file to process
    defined by the index of the input
    currently only "i.<inputIndex>.mix" and "i.<inputIndex>.mute" gets processed
    @TODO: we should also take a look onto "i.<all-other-inputs>.solo" because this will cause silence for this track as well

    @param int inputIndex the index of the audio input [0-22]
    @return list a list of Parameter instances
'''
def grabVolumeParametersForInput(inputIndex):
    global allParams

    paramsForInput = []

    # define all params that affects our audio processing for this single input
    paramNameWhitelist = [
        "i.%i.mix" % inputIndex,
        "i.%i.mute" % inputIndex
    ]
    for paramLine in allParams:
        paramList = paramLine.split(' ' ,2)
        if len(paramList) != 3 or paramList[1] not in paramNameWhitelist:
            continue
        paramsForInput.append(Param(paramList))
    return paramsForInput


def getFileContent(pathAndFileName):
    with open(pathAndFileName, 'r') as theFile:
        data = theFile.read()
        return data


def float2Db(inputValue):
    return math.log1p(float(inputValue))

def generalCmd(cmdArgsList, description, readStdError = False):
    logging.info("starting %s" % description)
    logging.debug(' '.join(cmdArgsList))
    startTime = time.time()
    if readStdError:
        process = subprocess.Popen(cmdArgsList, stderr=subprocess.PIPE)
        processStdOut = process.stderr.read()
    else:
        process = subprocess.Popen(cmdArgsList, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        processStdOut = process.stdout.read()
    retcode = process.wait()
    if retcode != 0:
        print ( "ERROR: %s did not complete successfully (error code is %s)" % (description, retcode) )

    logging.info("finished %s in %s seconds" % ( description, '{0:.3g}'.format(time.time() - startTime) ) )
    return processStdOut.decode('utf-8')




# thanks to: https://stackoverflow.com/questions/38085408/complex-audio-volume-changes-with-ffmpeg
def applyFilter(inputPath, filterParamsPath, outputPath):
    cmd = [
        'ffmpeg', '-hide_banner', '-v', 'quiet', '-stats', '-y',
        '-i', str(inputPath), '-filter_complex_script', str(filterParamsPath),
        str(outputPath)
    ]
    generalCmd(cmd, 'apply filter', True)


if __name__ == "__main__":
    runStuff()