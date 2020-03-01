# ui24r-paramrecorder
persist timestamped fader movements/parameter changes of the "Soundcraft Ui24R" digital mixing console in filesystem


## who is it for?
Owners of the **Soundcraft Ui24R** digital mixing console who makes use of the **multitrack** recording functionality may find this useful

## why?
The hardware built-in multitrack recording feature does not apply any of the thousands possible mixer parameters.  
for example: muted channels thet does not end up in the master mix does not represent silence in the recorded file of the specific channel  
actually every audio signal on each input gets recorded as is - without any modification  


This script is an approach to
  * connect to the mixer's websocket
  * grab all parameters that exists as an initial state
  * as soon as multitrack recording is started write every parameter change to a textfile
  * as soon as the multitrack recording stops also stop to persist incoming websocket messages

based on this textfile it's possible to apply some post processing (especially muting and volume changes) of the audiofiles to achieve a better representation of what was going on in the sound system during recording  

