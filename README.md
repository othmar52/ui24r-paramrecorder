# ui24r-paramrecorder
persist timestamped fader movements/parameter changes of the "Soundcraft Ui24R" digital mixing console in filesystem


## who is it for?
Owners of the **Soundcraft Ui24R** digital mixing console who makes use of the **multitrack** recording functionality may find this useful  
[YOUTUBE: Soundcraft Ui24R Recording to USB stick](https://www.youtube.com/watch?v=VvjQg027TaE)

## why?
The hardware built-in multitrack recording feature does not apply any of the thousands possible mixer parameters.  
for example: muted channels that does not end up in the master mix does not represent silence in the recorded file of the specific channel  
actually in **multitrack** recording every audio signal on each input gets recorded as is - without any modification  
in case you want a recording that sounds like your audience you are doomed to use the **2-track recording**


## how?
The script `ui24r-paramrecorder.py` is a quick & dirty approach to
  * connect to the mixer's websocket
  * grab all parameters that exists as an initial state
  * as soon as multitrack recording is started write every parameter change to a textfile
  * as soon as the multitrack recording stops also stop to persist incoming websocket messages


**example of the text based recording**  
`recordings/2020.03.02--14.56.11-recsession-0142.txt`  
`milisecond` `paramName` `paramValue`
```
0 i.0.fx.1.mute 0
...
  about 6700 initial mixer parameters with milisecond 0
...
0 i.15.aux.2.value 0
1.851 var.mtk.rec.session 0141
1.852 var.mtk.rec.busy 0
10.936 i.0.mute 1
16.946 i.2.mix 0.7623529412
48.759 i.0.mute 0
```

based on this textfile it's possible to apply some post processing (especially muting and volume changes) of the audiofiles to achieve a better representation of what was going on in the sound system during recording  
a partly working approach without any error handling already exists in `applyParamsToWav.py`

