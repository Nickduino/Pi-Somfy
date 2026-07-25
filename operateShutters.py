#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, re, argparse

# ── Platform detection & stubs for Windows development ──────────────────────
WINDOWS = (sys.platform == "win32")

if WINDOWS:
    import types
    # fcntl is Unix-only (used for lock files)
    _fcntl = types.ModuleType("fcntl")
    _fcntl.LOCK_EX = 0
    _fcntl.LOCK_NB = 0
    _fcntl.lockf = lambda *a, **kw: None
    sys.modules["fcntl"] = _fcntl

    # GPIO stubs for Windows development
    _pigpio = types.ModuleType("pigpio")
    _pigpio.OUTPUT = 0
    class _FakePulse:
        def __init__(self, *a, **kw): pass
    _pigpio.pulse = _FakePulse
    class _FakePi:
        connected = True
        def wave_add_new(self): pass
        def set_mode(self, *a): pass
        def wave_add_generic(self, *a): pass
        def wave_create(self): return 0
        def wave_send_once(self, *a): pass
        def wave_tx_busy(self): return False
        def wave_delete(self, *a): pass
        def stop(self): pass
    _pigpio.pi = _FakePi
    sys.modules["pigpio"] = _pigpio

    _lgpio = types.ModuleType("lgpio")
    _lgpio.TX_WAVE = 1
    class _FakeLgPulse:
        def __init__(self, *a, **kw): pass
    _lgpio.pulse = _FakeLgPulse
    _lgpio.gpiochip_open = lambda *a: 0
    _lgpio.gpio_claim_output = lambda *a: 0
    _lgpio.tx_wave = lambda *a: 0
    _lgpio.tx_busy = lambda *a: False
    _lgpio.gpio_free = lambda *a: 0
    _lgpio.gpiochip_close = lambda *a: 0
    sys.modules["lgpio"] = _lgpio

import fcntl
import os
import locale
import time
import datetime
import ephem
import socket

# ── Pi model detection & GPIO library selection ─────────────────────────────
# Pi 5 uses the RP1 southbridge chip which is incompatible with pigpio.
# We use lgpio (which works via /dev/gpiochip*) on Pi 5, and pigpio elsewhere.
# /proc/device-tree/model may not be accessible inside Docker containers;
# fall back to checking for /dev/gpiochip4 (RP1 chip, Pi 5 only) or the
# CPU revision code in /proc/cpuinfo.
IS_PI5 = False
LGPIO_CHIP = 4   # gpiochip number for lgpio (Pi 5): 4 on older kernels, 0 on newer
if not WINDOWS:
    try:
        with open('/proc/device-tree/model', 'r') as f:
            _model = f.read()
        if 'Pi 5' in _model:
            IS_PI5 = True
    except (FileNotFoundError, PermissionError):
        pass
    if not IS_PI5 and os.path.exists('/dev/gpiochip4'):
        IS_PI5 = True
    if not IS_PI5:
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Revision') and any(rev in line for rev in ['c04170', 'd04170', 'c04171', 'd04171']):
                        IS_PI5 = True
                        break
        except (FileNotFoundError, PermissionError):
            pass

if IS_PI5:
    import lgpio
else:
    import pigpio
import signal, atexit, traceback
import logging, logging.handlers
import threading

try:
    from config import MyConfig
    from config import SetupLogger
    from config import MyLog
    from scheduler import Event
    from scheduler import Schedule
    from scheduler import Scheduler
    from webserver import FlaskAppWrapper
    from alexa import Alexa
    from shutil import copyfile
except Exception as e1:
    print("\n\nThis program requires the modules located from the same github repository that are not present.\n")
    print("Error: " + str(e1))
    sys.exit(2)

class Shutter(MyLog):
    #Button values
    buttonUp = 0x2
    buttonStop = 0x1
    buttonDown = 0x4
    buttonProg = 0x8

    class ShutterState: # Definition of one shutter state
        position = None # as percentage: 0 = closed (down), 100 = open (up)
        lastCommandTime = None # get using time.monotonic()
        lastCommandDirection = None # 'up' or 'down' or None

        def __init__(self, initPosition = None):
            self.position = initPosition
            self.lastCommandTime = time.monotonic()

        def registerCommand(self, commandDirection):
            self.lastCommandDirection = commandDirection
            self.lastCommandTime = time.monotonic()

    def __init__(self, log = None, config = None):
        super(Shutter, self).__init__()
        self.lock = threading.Lock()
        self.transmitting = threading.Event()
        if log is not None:
            self.log = log
        if config is not None:
            self.config = config

        if self.config.TXGPIO is not None:
           self.TXGPIO=self.config.TXGPIO # 433.42 MHz emitter
        else:
           self.TXGPIO=4 # 433.42 MHz emitter on GPIO 4
        self.frame = bytearray(7)
        self.callback = []
        self.movementCallback = []
        self.movementStateList = {}
        self.shutterStateList = {}
        self.shutterStateLock = threading.Lock()

        # Seed persisted positions, only for shutters
        # that both still exist in [Shutters] and have a settled position
        # recorded in [ShutterPositions], so getShutterState's lazy-init
        # fallback only ever applies to shutters that have never settled.
        for shutterId, position in self.config.ShutterPositions.items():
            if shutterId in self.config.Shutters:
                self.shutterStateList[shutterId] = self.ShutterState(position)

    def getShutterState(self, shutterId, initialPosition = None):
        with self.shutterStateLock:
            if shutterId not in self.shutterStateList:
                self.shutterStateList[shutterId] = self.ShutterState(initialPosition)
            return self.shutterStateList[shutterId]

    def getPosition(self, shutterId):
        state = self.getShutterState(shutterId, 0)
        return state.position

    # Live-interpolated position while a move is in progress, for UI display
    # only. Mirrors _simulateStop's elapsed-time/direction math (the same
    # "how far did it get" estimate a MY-press stop would compute) but never
    # mutates state or settles a position — internal logic that decides
    # partial-move direction etc. keeps using getPosition()'s last-settled
    # value, since an in-flight estimate isn't precise enough to act on.
    def getDisplayPosition(self, shutterId):
        state = self.getShutterState(shutterId, 0)
        movementState = self.movementStateList.get(shutterId)
        if movementState not in ('opening', 'closing'):
            return state.position

        secondsSinceLastCommand = time.monotonic() - state.lastCommandTime
        if secondsSinceLastCommand <= 0:
            return state.position

        if movementState == 'opening':
            duration = self.config.Shutters[shutterId]['durationUp']
            if duration <= 0 or secondsSinceLastCommand >= duration:
                return 100   # elapsed time already covers the full travel —
                             # report the target, not the stale pre-move
                             # position, even if settling hasn't fired yet
            durationPercentage = secondsSinceLastCommand / duration * 100
            estimated = state.position + durationPercentage if state.position > 0 else durationPercentage
            return min(100, int(round(estimated)))
        else:
            duration = self.config.Shutters[shutterId]['durationDown']
            if duration <= 0 or secondsSinceLastCommand >= duration:
                return 0
            durationPercentage = secondsSinceLastCommand / duration * 100
            estimated = state.position - durationPercentage if state.position < 100 else 100 - durationPercentage
            return max(0, int(round(estimated)))

    def setPosition(self, shutterId, newPosition):
        state = self.getShutterState(shutterId)
        with self.shutterStateLock:
            state.position = newPosition
        # Every call site of setPosition() is already a "position settled"
        # moment (end of waitAndSetFinalPosition, stop()'s immediate branch,
        # the partial-move completions).
        self.config.WriteValue(shutterId, str(newPosition), section="ShutterPositions")
        for function in self.callback:
            function(shutterId, newPosition)

    def waitAndSetFinalPosition(self, shutterId, timeToWait, newPosition):
        state = self.getShutterState(shutterId)
        oldLastCommandTime = state.lastCommandTime

        self.LogDebug("["+self.config.Shutters[shutterId]['name']+"] Waiting for operation to complete for " + str(timeToWait) + " seconds")
        time.sleep(timeToWait)

        # Only set new position if registerCommand has not been called in between
        if state.lastCommandTime == oldLastCommandTime:
            self.LogDebug("["+self.config.Shutters[shutterId]['name']+"] Set new final position: " + str(newPosition))
            # A full/partial move that runs out its timer uninterrupted has
            # genuinely stopped — fire this before setPosition() so, as
            # elsewhere, the position callback's more precise open/closed
            # inference has the last word. Without this, 'opening'/'closing'
            # would stay stuck forever once a move completes naturally,
            # since nothing else clears it for this (non-explicit-stop) path.
            self._fireMovement(shutterId, 'stopped')
            self.setPosition(shutterId, newPosition)
        else:
            self.LogDebug("["+self.config.Shutters[shutterId]['name']+"] Discard final position. Position is now: " + str(state.position))

    def lower(self, shutterId):
        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Going down")
        self.sendCommand(shutterId, self.buttonDown, self.config.SendRepeat)
        self._simulateDown(shutterId)

    # Position-model update for a "down" command, shared by the TX path
    # (lower(), above) and the physical-remote path (recordExternalCommand).
    def _simulateDown(self, shutterId):
        state = self.getShutterState(shutterId, 100)
        state.registerCommand('down')
        self._fireMovement(shutterId, 'closing')

        # wait and set final position only if not interrupted in between
        timeToWait = state.position/100*self.config.Shutters[shutterId]['durationDown']
        t = threading.Thread(target = self.waitAndSetFinalPosition, args = (shutterId, timeToWait, 0))
        t.start()

    def lowerPartial(self, shutterId, percentage):
        state = self.getShutterState(shutterId, 100)

        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Going down") 
        self.sendCommand(shutterId, self.buttonDown, self.config.SendRepeat)
        state.registerCommand('down')
        self._fireMovement(shutterId, 'closing')
        time.sleep((state.position-percentage)/100*self.config.Shutters[shutterId]['durationDown'])
        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Stop at partial position requested")
        self.sendCommand(shutterId, self.buttonStop, self.config.SendRepeat)

        self._fireMovement(shutterId, 'stopped')
        self.setPosition(shutterId, percentage)

    def rise(self, shutterId):
        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Going up")
        self.sendCommand(shutterId, self.buttonUp, self.config.SendRepeat)
        self._simulateUp(shutterId)

    # Position-model update for an "up" command, shared by the TX path
    # (rise(), above) and the physical-remote path (recordExternalCommand).
    def _simulateUp(self, shutterId):
        state = self.getShutterState(shutterId, 0)
        state.registerCommand('up')
        self._fireMovement(shutterId, 'opening')

        # wait and set final position only if not interrupted in between
        timeToWait = (100-state.position)/100*self.config.Shutters[shutterId]['durationUp']
        t = threading.Thread(target = self.waitAndSetFinalPosition, args = (shutterId, timeToWait, 100))
        t.start()

    def risePartial(self, shutterId, percentage):
        state = self.getShutterState(shutterId, 0)

        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Going up")
        self.sendCommand(shutterId, self.buttonUp, self.config.SendRepeat)
        state.registerCommand('up')
        self._fireMovement(shutterId, 'opening')
        time.sleep((percentage-state.position)/100*self.config.Shutters[shutterId]['durationUp'])
        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Stop at partial position requested")
        self.sendCommand(shutterId, self.buttonStop, self.config.SendRepeat)

        self._fireMovement(shutterId, 'stopped')
        self.setPosition(shutterId, percentage)

    def stop(self, shutterId):
        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Stopping")
        self.sendCommand(shutterId, self.buttonStop, self.config.SendRepeat)
        self._simulateStop(shutterId)

    # Position-model update for a "stop"/"my" command, shared by the TX path
    # (stop(), above) and the physical-remote path (recordExternalCommand).
    # Inherits the full MY-button ping-pong the motors implement from the
    # elapsed-time/fallback logic below — no special-casing needed for
    # physical presses.
    def _simulateStop(self, shutterId):
        state = self.getShutterState(shutterId, 50)

        self.LogDebug("["+shutterId+"] Previous position: " + str(state.position))

        # Compute position based on time elapsed since last command & command direction
        setupDurationDown = self.config.Shutters[shutterId]['durationDown']
        setupDurationUp = self.config.Shutters[shutterId]['durationUp']

        # Whether the shutter is genuinely moving right now comes from
        # movementStateList (set by _simulateUp/_simulateDown, and cleared
        # back to 'stopped' the instant ANY move settles — full, partial, or
        # a previous MY-position correction), not from comparing elapsed
        # time against the shutter's *full* 0-100 duration. That old
        # elapsed-time heuristic misclassified a MY press shortly after a
        # completed partial/MY move (which settles in less than the full
        # duration) as "still mid-travel", computing a bogus interrupted
        # position instead of correctly falling through to the MY-position
        # logic below — the shutter was already stationary the whole time.
        movementState = self.movementStateList.get(shutterId)
        self.LogDebug("["+shutterId+"] Movement state: " + str(movementState))

        fallback = False
        if movementState == 'opening':
            secondsSinceLastCommand = time.monotonic() - state.lastCommandTime
            self.LogDebug("["+shutterId+"] Seconds since last command: " + str(round(secondsSinceLastCommand, 2)))
            durationPercentage = int(round(secondsSinceLastCommand/setupDurationUp * 100)) if setupDurationUp > 0 else 100
            self.LogDebug("["+shutterId+"] Up duration percentage: " + str(durationPercentage) + ", State position: "+ str(state.position))
            if state.position > 0: # after rise from previous position
                newPosition = min (100 , state.position + durationPercentage)
            else: # after rise from fully closed
                newPosition = durationPercentage
        elif movementState == 'closing':
            secondsSinceLastCommand = time.monotonic() - state.lastCommandTime
            self.LogDebug("["+shutterId+"] Seconds since last command: " + str(round(secondsSinceLastCommand, 2)))
            durationPercentage = int(round(secondsSinceLastCommand/setupDurationDown * 100)) if setupDurationDown > 0 else 100
            self.LogDebug("["+shutterId+"] Down duration percentage: " + str(durationPercentage) + ", State position: "+ str(state.position))
            if state.position < 100: # after lower from previous position
                newPosition = max (0 , state.position - durationPercentage)
            else: # after down from fully opened
                newPosition = 100 - durationPercentage
        else: # already stopped (fully, partially, or from a previous MY correction)
            self.LogInfo("["+shutterId+"] Stop pressed while stationary.")
            fallback = True

        if fallback == True: # Let's assume it will end on the intermediate position ! If it exists !
            intermediatePosition = self.config.Shutters[shutterId]['intermediatePosition']
            if intermediatePosition is None or intermediatePosition == state.position:
                self.LogInfo("["+shutterId+"] Stay stationary.")
                newPosition = state.position
            else:
                self.LogInfo("["+shutterId+"] Motor expected to move to intermediate position "+str(intermediatePosition))
                if state.position > intermediatePosition:
                    state.registerCommand('down')
                    self._fireMovement(shutterId, 'closing')
                    timeToWait = abs(state.position - intermediatePosition) / 100*self.config.Shutters[shutterId]['durationDown']
                else:
                    state.registerCommand('up')
                    self._fireMovement(shutterId, 'opening')
                    timeToWait = abs(state.position - intermediatePosition) / 100*self.config.Shutters[shutterId]['durationUp']
                # wait and set final intermediate position only if not interrupted in between
                t = threading.Thread(target = self.waitAndSetFinalPosition, args = (shutterId, timeToWait, intermediatePosition))
                t.start()
                return   # genuinely moving again — not a stop; the settled state
                         # reports via setPosition()'s existing position callback
                         # when the thread completes, same as rise()/lower().

        # Fire the movement event before setPosition(): if the computed position
        # lands exactly on 0/100, setPosition()'s existing position callback
        # publishes the more precise open/closed state, and should have the
        # last word on the retained MQTT topic, not this 'stopped' event.
        self._fireMovement(shutterId, 'stopped')

        # Save computed position
        self.setPosition(shutterId, newPosition)

        # Register command at the end to not impact the lastCommand timer
        state.registerCommand(None)

    # Push a set of buttons for a short or long press.
    def pressButtons(self, shutterId, buttons, longPress):
        self.sendCommand(shutterId, buttons, 35 if longPress else 1)

    def program(self, shutterId):
        self.sendCommand(shutterId, self.buttonProg, 1)

    def registerCallBack(self, callbackFunction):
        self.callback.append(callbackFunction)

    # Register for transient movement-state notifications ('opening'/
    # 'closing'/'stopped'), fired identically for the TX/software path and
    # the physical-remote path — complements registerCallBack's position-
    # based open/closed/stopped signal with the "movement in progress"
    # state nothing else reports today.
    def registerMovementCallBack(self, callbackFunction):
        self.movementCallback.append(callbackFunction)

    def _fireMovement(self, shutterId, movementState):
        self.movementStateList[shutterId] = movementState
        for function in self.movementCallback:
            function(shutterId, movementState)

    # Last movement state fired for a shutter ('opening'/'closing'/'stopped'),
    # or None if it's never moved this run — lets a REST poller (getStatus)
    # see the same signal MQTT gets pushed, without needing its own callback.
    def getMovementState(self, shutterId):
        return self.movementStateList.get(shutterId)

    # Update the position model for a button press heard from a physical RTS
    # remote — dispatches to the same _simulate* methods the TX path uses,
    # with no RF transmission.
    def recordExternalCommand(self, shutterId, button):
        name = self.config.Shutters[shutterId]['name']
        if button == self.buttonUp:
            self.LogInfo("["+name+"] Physical remote: UP")
            self._simulateUp(shutterId)
        elif button == self.buttonDown:
            self.LogInfo("["+name+"] Physical remote: DOWN")
            self._simulateDown(shutterId)
        elif button == self.buttonStop:
            self.LogInfo("["+name+"] Physical remote: STOP/MY")
            self._simulateStop(shutterId)
        else:
            self.LogWarn("["+name+"] Physical remote: unhandled button 0x%X" % button)

    def sendCommand(self, shutterId, button, repetition): #Sending a frame
    # Sending more than two repetitions after the original frame means a button kept pressed and moves the blind in steps 
    # to adjust the tilt. Sending the original frame and three repetitions is the smallest adjustment, sending the original
    # frame and more repetitions moves the blinds up/down for a longer time.
    # To activate the program mode (to register or de-register additional remotes) of your Somfy blinds, long press the 
    # prog button (at least thirteen times after the original frame to activate the registration.
       self.LogDebug("sendCommand: Waiting for Lock")
       self.lock.acquire()
       try:
           self.LogDebug("sendCommand: Lock acquired")
           self.transmitting.set()
           checksum = 0

           teleco = int(shutterId, 16)
           code = int(self.config.Shutters[shutterId]['code'])

           # print (codecs.encode(shutterId, 'hex_codec'))
           self.config.setCode(shutterId, code+1)

           self.LogInfo ("Remote  :      " + "0x%0.2X" % teleco + ' (' + self.config.Shutters[shutterId]['name'] + ')')
           self.LogInfo ("Button  :      " + "0x%0.2X" % button)
           self.LogInfo ("Rolling code : " + str(code))
           self.LogInfo ("")

           self.frame[0] = 0xA7;       # Encryption key. Doesn't matter much
           self.frame[1] = button << 4 # Which button did  you press? The 4 LSB will be the checksum
           self.frame[2] = code >> 8               # Rolling code (big endian)
           self.frame[3] = (code & 0xFF)           # Rolling code
           self.frame[4] = teleco >> 16            # Remote address
           self.frame[5] = ((teleco >>  8) & 0xFF) # Remote address
           self.frame[6] = (teleco & 0xFF)         # Remote address

           outstring = "Frame  :    "
           for octet in self.frame:
              outstring = outstring + "0x%0.2X" % octet + ' '
           self.LogInfo (outstring)

           for i in range(0, 7):
              checksum = checksum ^ self.frame[i] ^ (self.frame[i] >> 4)

           checksum &= 0b1111; # We keep the last 4 bits only

           self.frame[1] |= checksum;

           outstring = "With cks  : "
           for octet in self.frame:
              outstring = outstring + "0x%0.2X" % octet + ' '
           self.LogInfo (outstring)

           for i in range(1, 7):
              self.frame[i] ^= self.frame[i-1];

           outstring = "Obfuscated :"
           for octet in self.frame:
              outstring = outstring + "0x%0.2X" % octet + ' '
           self.LogInfo (outstring)

           if IS_PI5:
               self._sendWave_lgpio(repetition)
           else:
               #This is where all the awesomeness is happening. You're telling the daemon what you wanna send
               pi = pigpio.pi() # connect to Pi

               if not pi.connected:
                  exit()

               pi.wave_add_new()
               pi.set_mode(self.TXGPIO, pigpio.OUTPUT)

               wf=[]
               wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 9415)) # wake up pulse
               wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 89565)) # silence
               for i in range(2): # hardware synchronization
                  wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 2560))
                  wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 2560))
               wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 4550)) # software synchronization
               wf.append(pigpio.pulse(0, 1<<self.TXGPIO,  640))

               for i in range (0, 56): # manchester encoding of payload data
                  if ((self.frame[int(i/8)] >> (7 - (i%8))) & 1):
                     wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 640))
                     wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 640))
                  else:
                     wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 640))
                     wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 640))

               wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 30415)) # interframe gap

               for j in range(1,repetition): # repeating frames
                        for i in range(7): # hardware synchronization
                              wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 2560))
                              wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 2560))
                        wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 4550)) # software synchronization
                        wf.append(pigpio.pulse(0, 1<<self.TXGPIO,  640))

                        for i in range (0, 56): # manchester encoding of payload data
                              if ((self.frame[int(i/8)] >> (7 - (i%8))) & 1):
                                 wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 640))
                                 wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 640))
                              else:
                                 wf.append(pigpio.pulse(1<<self.TXGPIO, 0, 640))
                                 wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 640))

                        wf.append(pigpio.pulse(0, 1<<self.TXGPIO, 30415)) # interframe gap

               pi.wave_add_generic(wf)
               wid = pi.wave_create()
               pi.wave_send_once(wid)
               while pi.wave_tx_busy():
                  pass
               pi.wave_delete(wid)

               pi.stop()
       finally:
           self.transmitting.clear()
           self.lock.release()
           self.LogDebug("sendCommand: Lock released")

    def _sendWave_lgpio(self, repetition):
       """Transmit the Somfy RTS frame using lgpio (Pi 5)."""
       h = lgpio.gpiochip_open(LGPIO_CHIP)
       lgpio.gpio_claim_output(h, self.TXGPIO)

       pulses = []
       pulses.append(lgpio.pulse(1, 1, 9415))   # wake up pulse
       pulses.append(lgpio.pulse(0, 1, 89565))  # silence
       for i in range(2): # hardware synchronization
          pulses.append(lgpio.pulse(1, 1, 2560))
          pulses.append(lgpio.pulse(0, 1, 2560))
       pulses.append(lgpio.pulse(1, 1, 4550))   # software synchronization
       pulses.append(lgpio.pulse(0, 1,  640))

       for i in range(0, 56): # manchester encoding of payload data
          if ((self.frame[int(i/8)] >> (7 - (i%8))) & 1):
             pulses.append(lgpio.pulse(0, 1, 640))
             pulses.append(lgpio.pulse(1, 1, 640))
          else:
             pulses.append(lgpio.pulse(1, 1, 640))
             pulses.append(lgpio.pulse(0, 1, 640))

       pulses.append(lgpio.pulse(0, 1, 30415))  # interframe gap

       for j in range(1, repetition): # repeating frames
                for i in range(7): # hardware synchronization
                      pulses.append(lgpio.pulse(1, 1, 2560))
                      pulses.append(lgpio.pulse(0, 1, 2560))
                pulses.append(lgpio.pulse(1, 1, 4550)) # software synchronization
                pulses.append(lgpio.pulse(0, 1,  640))

                for i in range(0, 56): # manchester encoding of payload data
                      if ((self.frame[int(i/8)] >> (7 - (i%8))) & 1):
                         pulses.append(lgpio.pulse(0, 1, 640))
                         pulses.append(lgpio.pulse(1, 1, 640))
                      else:
                         pulses.append(lgpio.pulse(1, 1, 640))
                         pulses.append(lgpio.pulse(0, 1, 640))

                pulses.append(lgpio.pulse(0, 1, 30415)) # interframe gap

       lgpio.tx_wave(h, self.TXGPIO, pulses)
       while lgpio.tx_busy(h, self.TXGPIO, lgpio.TX_WAVE):
          time.sleep(0.001)

       lgpio.gpio_free(h, self.TXGPIO)
       lgpio.gpiochip_close(h)

class operateShutters(MyLog):

    def __init__(self, args = None):
        super(operateShutters, self).__init__()
        self.ProgramName = "operate Somfy Shutters"
        self.Version = "Unknown"
        self.log = None
        self.IsStopping = False
        self.ProgramComplete = False

        if args.ConfigFile is None:
            self.ConfigFile = "/etc/operateShutters.conf"
        else:
            self.ConfigFile = args.ConfigFile

        self.console = SetupLogger("shutters_console", log_file = "", stream = True)

        if not WINDOWS:
            if os.geteuid() != 0:
                self.LogConsole("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'.")
                sys.exit(1)

        if not os.path.isfile(self.ConfigFile):
            self.LogConsole("Creating new config file : " + self.ConfigFile)
            defaultConfigFile = os.path.dirname(os.path.realpath(__file__))+'/defaultConfig.conf'
            print(defaultConfigFile);
            if not os.path.isfile(defaultConfigFile):
                self.LogConsole("Failure to create new config file: "+defaultConfigFile)
                sys.exit(1)
            else: 
                copyfile(defaultConfigFile, self.ConfigFile)

        # read config file
        self.config = MyConfig(filename = self.ConfigFile, log = self.console)
        result = self.config.LoadConfig();
        if not result:
            self.LogConsole("Failure to load configuration parameters")
            sys.exit(1)

        # log errors in this module to a file
        logLocation = self.config.LogLocation
        if WINDOWS and not os.path.isdir(logLocation):
            logLocation = "./"
        self.log = SetupLogger("shutters", logLocation + "operateShutters.log")
        self.config.log = self.log

        if not WINDOWS and self.IsLoaded():
            self.LogWarn("operateShutters.py is already loaded.")
            sys.exit(1)

        if not WINDOWS and not self.startGPIO():
            self.LogConsole("Not able to start GPIO")
            sys.exit(1)

        self.shutter = Shutter(log = self.log, config = self.config)

        self.schedule = Schedule(log = self.log, config = self.config)
        self.scheduler = None
        self.webServer = None
        self.receiver = None

        if (args.echo == True):
            self.alexa = Alexa(kwargs={'log':self.log, 'shutter': self.shutter, 'config': self.config})

        if (args.mqtt == True):
            from mqtt import MQTT
            self.mqtt = MQTT(kwargs={'log':self.log, 'shutter': self.shutter, 'config': self.config})

        # Enabled when RXGPIO is present in [General] — no new CLI flag.
        if not WINDOWS and self.config.RXGPIO is not None:
            from receiver import Receiver
            self.receiver = Receiver(kwargs={'log':self.log, 'shutter': self.shutter, 'config': self.config, 'console': self.console})

        self.ProcessCommand(args);

    #------------------------ operateShutters::IsLoaded -----------------------------
    #return true if program is already loaded
    def IsLoaded(self):

        file_path = '/var/lock/'+os.path.basename(__file__)
        global file_handle

        try:
           file_handle= open(file_path, 'w')
           fcntl.lockf(file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
           return False
        except IOError:
           return True

    #--------------------- operateShutters::startGPIO ---------------------------------
    def startGPIO(self):
       if IS_PI5:
           global LGPIO_CHIP
           # lgpio accesses /dev/gpiochip* directly — no daemon needed
           # Try gpiochip4 first (older Pi 5 kernels), then gpiochip0 (newer kernels)
           for chip in [4, 0]:
               try:
                   h = lgpio.gpiochip_open(chip)
                   lgpio.gpiochip_close(h)
                   LGPIO_CHIP = chip
                   self.LogInfo("lgpio: gpiochip{} opened successfully (Pi 5)".format(chip))
                   return True
               except Exception as e:
                   self.LogInfo("lgpio: could not open gpiochip{}: {}".format(chip, e))
           self.LogError("lgpio: no usable gpiochip found")
           return False

       # pigpio path for Pi 1/2/3/4
       # Deliberately not passing -m (disable alerts): -m silently prevents
       # pi.callback() from ever delivering edge notifications, which the
       # receiver (Receiver, when config.RXGPIO is set) needs.
       # No sudo: __init__ already refused to run unless os.geteuid() == 0,
       # so this process is already root in every deployment (standalone,
       # systemd, or a container) — sudo here would just add a dependency
       # this code doesn't need.
       if sys.version_info[0] < 3:
           import commands
           status, process = commands.getstatusoutput('pidof pigpiod')
           if status:  #  it wasn't running, so start it
               self.LogInfo ("pigpiod was not running")
               commands.getstatusoutput('pigpiod -l')  # try to  start it
               time.sleep(0.5)
               # check it again
               status, process = commands.getstatusoutput('pidof pigpiod')
       else:
           import subprocess
           status, process = subprocess.getstatusoutput('pidof pigpiod')
           if status:  #  it wasn't running, so start it
               self.LogInfo ("pigpiod was not running")
               subprocess.getstatusoutput('pigpiod -l')  # try to  start it
               time.sleep(0.5)
               # check it again
               status, process = subprocess.getstatusoutput('pidof pigpiod')

       if not status:  # if it was started successfully (or was already running)...
           pigpiod_process = process
           self.LogInfo ("pigpiod is running, process ID is {} ".format(pigpiod_process))
           self.LogConsole("pigpiod is running, process ID is {} ".format(pigpiod_process))

           try:
               pi = pigpio.pi()  # local GPIO only
               if not pi.connected:
                   self.LogError("pigpio connection could not be established. Check logs to get more details.")
                   self.LogConsole("pigpio connection could not be established.")
                   return False
               else:
                   self.LogInfo("pigpio's pi instantiated.")
                   self.LogConsole("pigpio's pi instantiated.")
           except Exception as e:
               start_pigpiod_exception = str(e)
               self.LogError("problem instantiating pi: {}".format(start_pigpiod_exception))
               self.LogConsole("problem instantiating pi: {}".format(start_pigpiod_exception))
       else:
           self.LogError("start pigpiod was unsuccessful.")
           self.LogConsole("start pigpiod was unsuccessful (pidof pigpiod status={}).".format(status))
           return False
       return True

    #--------------------- operateShutters::ProcessCommand -----------------------------------------------
    def ProcessCommand(self, args):

       if ((args.long == True) and not (args.press)):
             print("ERROR: The -long option can only be specified with the -press option.\n")
             parser.print_help()
             
       elif ((args.shutterName != "") and (args.down == True)):
             self.shutter.lower(self.config.ShuttersByName[args.shutterName])
       elif ((args.shutterName != "") and (args.up == True)):
             self.shutter.rise(self.config.ShuttersByName[args.shutterName])
       elif ((args.shutterName != "") and (args.stop == True)):
             self.shutter.stop(self.config.ShuttersByName[args.shutterName])
       elif ((args.shutterName != "") and (args.program == True)):
             self.shutter.program(self.config.ShuttersByName[args.shutterName])
       elif ((args.shutterName != "") and (args.demo == True)):
             self.LogInfo ("lowering shutter")
             self.shutter.lowerPartial(self.config.ShuttersByName[args.shutterName], 0)
             time.sleep(7)
             self.LogInfo ("raising shutter")
             self.shutter.risePartial(self.config.ShuttersByName[args.shutterName], 100)
       elif ((args.shutterName != "") and (args.duskdawn is not None)):
             self.schedule.addRepeatEventBySunrise([self.config.ShuttersByName[args.shutterName]], 'up', args.duskdawn[1], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
             self.schedule.addRepeatEventBySunset([self.config.ShuttersByName[args.shutterName]], 'down', args.duskdawn[0], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
             self.scheduler = Scheduler(kwargs={'log':self.log, 'schedule':self.schedule, 'shutter': self.shutter, 'config': self.config})
             self.scheduler.daemon = True
             self.scheduler.start()
             if (args.echo == True):
                 self.alexa.daemon = True
                 self.alexa.start()
             if (args.mqtt == True):
                 self.mqtt.daemon = True
                 self.mqtt.start()
             if self.receiver is not None:
                 self.receiver.daemon = True
                 self.receiver.start()
             self.scheduler.join()
       elif ((args.shutterName != "") and (args.press)):

             buttons = 0

             btnMap = {
               'up': self.shutter.buttonUp,
               'down': self.shutter.buttonDown,
               'stop': self.shutter.buttonStop,
               'my': self.shutter.buttonStop,
               'program': self.shutter.buttonProg
             }
             for btn in args.press:
                 buttons |= btnMap[btn]

             self.shutter.pressButtons(self.config.ShuttersByName[args.shutterName], buttons, args.long)
       elif (args.auto == True):
             self.schedule.loadScheduleFromConfig()
             self.scheduler = Scheduler(kwargs={'log':self.log, 'schedule':self.schedule, 'shutter': self.shutter, 'config': self.config})
             self.scheduler.daemon = True
             self.scheduler.start()
             if (args.echo == True):
                 self.alexa.daemon = True
                 self.alexa.start()
             if (args.mqtt == True):
                 self.mqtt.daemon = True
                 self.mqtt.start()
             if self.receiver is not None:
                 self.receiver.daemon = True
                 self.receiver.start()
             self.webServer = FlaskAppWrapper(name='WebServer', static_url_path=os.path.dirname(os.path.realpath(__file__))+'/html', log = self.log, shutter = self.shutter, schedule = self.schedule, config = self.config, receiver = self.receiver)
             self.webServer.run()
       else:
          parser.print_help()

       if (args.echo == True):
           self.alexa.daemon = True
           self.alexa.start()
       if (args.mqtt == True):
           self.mqtt.daemon = True
           self.mqtt.start()
       if self.receiver is not None:
           self.receiver.daemon = True
           self.receiver.start()

       if (args.echo == True):
           self.alexa.join()
       if (args.mqtt == True):
           self.mqtt.join()
       if self.receiver is not None:
           self.receiver.join()
       self.LogInfo ("Process Command Completed....")
       self.Close();

    #---------------------operateShutters::Close----------------------------------------
    def Close(self, signum = None, frame = None):

        # we dont really care about the errors that may be generated on shutdown
        try:
            self.IsStopping = True
        except Exception as e1:
            self.LogErrorLine("Error Closing Monitor: " + str(e1))

        self.LogError("operateShutters Shutdown")

        try:
            self.ProgramComplete = True
            if self.scheduler is not None:
                self.LogError("Stopping Scheduler. This can take up to 1 second...")
                self.scheduler.shutdown_flag.set()
                self.scheduler.join()
                self.LogError("Scheduler stopped. Now exiting.")
            if self.alexa is not None:
                self.LogError("Stopping Alexa Listener. This can take up to 1 second...")
                self.alexa.shutdown_flag.set()
                self.alexa.join()
                self.LogError("Alexa Listener stopped. Now exiting.")
            if self.mqtt is not None:
                self.LogError("Stopping MQTT Listener. This can take up to 1 second...")
                self.mqtt.shutdown_flag.set()
                self.mqtt.join()
                self.LogError("MQTT Listener stopped. Now exiting.")
            if self.receiver is not None:
                self.LogError("Stopping RTS Receiver. This can take up to 1 second...")
                self.receiver.shutdown_flag.set()
                self.receiver.join()
                self.LogError("RTS Receiver stopped. Now exiting.")
            if self.webServer is not None:
                self.LogError("Stopping WebServer. This can take up to 1 second...")
                self.webServer.shutdown_server()
                self.LogError("WebServer stopped. Now exiting.")
            sys.exit(0)
        except:
            pass

#------------------- Command-line interface for monitor ------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='operate Somfy Shutters.')
    parser.add_argument('shutterName', nargs='?', help='Name of the Shutter')
    parser.add_argument('-config', '-c', dest='ConfigFile', default=os.getcwd()+'/operateShutters.conf', help='Name of the Config File (incl full Path)')
    parser.add_argument('-up', '-u', help='Raise the Shutter', action='store_true')
    parser.add_argument('-down', '-d', help='lower the Shutter', action='store_true')
    parser.add_argument('-stop', '-s', help='stop the Shutter', action='store_true')
    parser.add_argument('-program', '-p', help='program a new Shutter', action='store_true')
    parser.add_argument('-press', help='Simulate a press of the specified remote buttons (\'up\', \'down\', \'stop\'/\'my\', and \'program\'). You can specify multiple buttons to activate setup operations. This does not update the known state of the blinds, so should not be used for ordinary raise and lower operations.', metavar='BTN', nargs='+', type=str)
    parser.add_argument('-long', help='When used with the -press option, simulates a long press, instead of a short press.', action='store_true')
    parser.add_argument('-demo', help='lower the Shutter, Stop after 7 second, then raise the Shutter', action='store_true')
    parser.add_argument('-duskdawn', '-dd', type=int, nargs=2, help='Automatically lower the shutter at sunset and rise the shutter at sunrise, provide the evening delay and morning delay in minutes each')
    parser.add_argument('-auto', '-a', help='Run schedule based on config. Also will start up the web-server which can be used to setup the schedule. Try: https://'+socket.gethostname(), action='store_true')
    parser.add_argument('-echo', '-e', help='Enable Amazon Alexa (Echo) integration', action='store_true')
    parser.add_argument('-mqtt', '-m', help='Enable MQTT integration', action='store_true')
    args = parser.parse_args()

    #Start things up
    MyShutter = operateShutters(args = args)

    try:
        while not MyShutter.ProgramComplete:
            time.sleep(0.01)
        sys.exit(0)
    except:
        sys.exit(1)
