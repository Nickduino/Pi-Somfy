#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, re, argparse
import fcntl
import os
import locale
import time
import datetime
import ephem
import pigpio
import socket
import signal, atexit, traceback
import logging, logging.handlers
import threading
import getpass


try:
    from myconfig import MyConfig
    from mylog import SetupLogger
    from mylog import MyLog
    from myscheduler import Event
    from myscheduler import Schedule
    from myscheduler import Scheduler
    from mywebserver import FlaskAppWrapper
    from myalexa import Alexa
    from mymqtt import MQTT
    from shutil import copyfile
    from somfyRfm69Transmitter import SomfyRfm69Tx
    from somfyRtsWaveForm import createWaveForm
    from time import sleep

except Exception as e1:
    print("\n\nThis program requires the modules located from the same github repository that are not present.\n")
    print("Error: " + str(e1))
    sys.exit(2)

if sys.version_info[0] < 3:
    import commands as processcommands
else:
    import subprocess as processcommands

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
        if log != None:
            self.log = log
        if config != None:
            self.config = config

        if self.config.TXGPIO != None:
            self.TXGPIO=self.config.TXGPIO # 433.42 MHz emitter
        else:
            self.TXGPIO=4 # 433.42 MHz emitter on GPIO 4

        self.callback = []
        self.shutterStateList = {}
        self.sutterStateLock = threading.Lock()

    def getShutterState(self, shutterId, initialPosition = None):
        with self.sutterStateLock:
            if shutterId not in self.shutterStateList:
                self.shutterStateList[shutterId] = self.ShutterState(initialPosition)
            return self.shutterStateList[shutterId]

    def getPosition(self, shutterId):
        state = self.getShutterState(shutterId, 0)
        return state.position

    def setPosition(self, shutterId, newPosition):
        state = self.getShutterState(shutterId)
        with self.sutterStateLock:
            state.position = newPosition
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
            self.setPosition(shutterId, newPosition)
        else:
            self.LogDebug("["+self.config.Shutters[shutterId]['name']+"] Discard final position. Position is now: " + str(state.position))

    def lower(self, shutterId):
        state = self.getShutterState(shutterId, 100)

        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Going down")
        self.sendCommand(shutterId, self.buttonDown, self.config.SendRepeat)
        state.registerCommand('down')

        # wait and set final position only if not interrupted in between
        timeToWait = state.position/100*self.config.Shutters[shutterId]['durationDown']
        t = threading.Thread(target = self.waitAndSetFinalPosition, args = (shutterId, timeToWait, 0))
        t.start()

    def lowerPartial(self, shutterId, percentage):
        state = self.getShutterState(shutterId, 100)

        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Going down") 
        self.sendCommand(shutterId, self.buttonDown, self.config.SendRepeat)
        state.registerCommand('down')
        time.sleep((state.position-percentage)/100*self.config.Shutters[shutterId]['durationDown'])
        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Stop at partial position requested")
        self.sendCommand(shutterId, self.buttonStop, self.config.SendRepeat)

        self.setPosition(shutterId, percentage)

    def rise(self, shutterId):
        state = self.getShutterState(shutterId, 0)

        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Going up")
        self.sendCommand(shutterId, self.buttonUp, self.config.SendRepeat)
        state.registerCommand('up')

        # wait and set final position only if not interrupted in between
        timeToWait = (100-state.position)/100*self.config.Shutters[shutterId]['durationUp']
        t = threading.Thread(target = self.waitAndSetFinalPosition, args = (shutterId, timeToWait, 100))
        t.start()

    def risePartial(self, shutterId, percentage):
        state = self.getShutterState(shutterId, 0)

        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Going up")
        self.sendCommand(shutterId, self.buttonUp, self.config.SendRepeat)
        state.registerCommand('up')
        time.sleep((percentage-state.position)/100*self.config.Shutters[shutterId]['durationUp'])
        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Stop at partial position requested")
        self.sendCommand(shutterId, self.buttonStop, self.config.SendRepeat)

        self.setPosition(shutterId, percentage)

    def stop(self, shutterId):
        state = self.getShutterState(shutterId, 50)

        self.LogInfo("["+self.config.Shutters[shutterId]['name']+"] Stopping")
        self.sendCommand(shutterId, self.buttonStop, self.config.SendRepeat)

        self.LogDebug("["+shutterId+"] Previous position: " + str(state.position))
        secondsSinceLastCommand = int(round(time.monotonic() - state.lastCommandTime))
        self.LogDebug("["+shutterId+"] Seconds since last command: " + str(secondsSinceLastCommand))

        # Compute position based on time elapsed since last command & command direction
        setupDurationDown = self.config.Shutters[shutterId]['durationDown']
        setupDurationUp = self.config.Shutters[shutterId]['durationUp']

        fallback = False
        if state.lastCommandDirection == 'up':
            if secondsSinceLastCommand > 0 and secondsSinceLastCommand < setupDurationUp:
                durationPercentage = int(round(secondsSinceLastCommand/setupDurationUp * 100))
                self.LogDebug("["+shutterId+"] Up duration percentage: " + str(durationPercentage) + ", State position: "+ str(state.position))
                if state.position > 0: # after rise from previous position
                    newPosition = min (100 , state.position + durationPercentage)
                else: # after rise from fully closed
                    newPosition = durationPercentage
            else:  #fallback
                self.LogWarn("["+shutterId+"] Too much time since up command.")
                fallback = True
        elif state.lastCommandDirection == 'down':
            if secondsSinceLastCommand > 0 and secondsSinceLastCommand < setupDurationDown:
                durationPercentage = int(round(secondsSinceLastCommand/setupDurationDown * 100))
                self.LogDebug("["+shutterId+"] Down duration percentage: " + str(durationPercentage) + ", State position: "+ str(state.position))
                if state.position < 100: # after lower from previous position
                    newPosition = max (0 , state.position - durationPercentage)
                else: # after down from fully opened
                    newPosition = 100 - durationPercentage
            else:  #fallback
                self.LogWarn("["+shutterId+"] Too much time since down command.")
                fallback = True
        else: # consecutive stops
            self.LogWarn("["+shutterId+"] Stop pressed while stationary.")
            fallback = True

        if fallback == True: # Let's assume it will end on the intermediate position ! If it exists !
            intermediatePosition = self.config.Shutters[shutterId]['intermediatePosition']
            if (intermediatePosition == None) or (intermediatePosition == state.position):
                self.LogInfo("["+shutterId+"] Stay stationary.")
                newPosition = state.position
            else:
                self.LogInfo("["+shutterId+"] Motor expected to move to intermediate position "+str(intermediatePosition))
                if state.position > intermediatePosition:
                    state.registerCommand('down')
                    timeToWait = abs(state.position - intermediatePosition) / 100*self.config.Shutters[shutterId]['durationDown']
                else:
                    state.registerCommand('up')
                    timeToWait = abs(state.position - intermediatePosition) / 100*self.config.Shutters[shutterId]['durationUp']
                # wait and set final intermediate position only if not interrupted in between
                t = threading.Thread(target = self.waitAndSetFinalPosition, args = (shutterId, timeToWait, intermediatePosition))
                t.start()
                return

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

    def sendCommand(self, shutterId, button, repetition): #Sending a frame
    # Sending more than two repetitions after the original frame means a button kept pressed and moves the blind in steps 
    # to adjust the tilt. Sending the original frame and three repetitions is the smallest adjustment, sending the original
    # frame and more repetitions moves the blinds up/down for a longer time.
    # To activate the program mode (to register or de-register additional remotes) of your Somfy blinds, long press the 
    # prog button (at least thirteen times after the original frame to activate the registration.
        self.LogDebug("sendCommand: Waiting for Lock")
        self.lock.acquire()
        try:
            
            self.LogDebug("sendCommand: Lock aquired")
            checksum = 0

            teleco = int(shutterId, 16)
            code = int(self.config.Shutters[shutterId]['code'])

            # print (codecs.encode(shutterId, 'hex_codec'))
            self.config.setCode(shutterId, code+1)

            self.LogInfo ("Remote  :		" + "0x%0.2X" % teleco + ' (' + self.config.Shutters[shutterId]['name'] + ')')
            self.LogInfo ("Button  :		" + "0x%0.2X" % button)
            self.LogInfo ("Rolling code : " + str(code))
            self.LogInfo ("")

            wf = createWaveForm(self.TXGPIO, teleco, button, code, repetition, self.log)

            if not (self.config.Rfm69Enabled):

                pi = pigpio.pi(host=self.config.PIGPIOHost, port=self.config.PIGPIOPort) 

                if not pi.connected:
                    exit()

                pi.wave_add_new()
                pi.set_mode(self.TXGPIO, pigpio.OUTPUT)

                pi.wave_add_generic(wf)
                wid = pi.wave_create()
        
                pi.wave_send_once(wid)

                while pi.wave_tx_busy():
                    sleep(0.1)

                pi.wave_delete(wid)

                pi.stop()
            else:
                with SomfyRfm69Tx(self.config.Rfm69ResetGPIO, self.TXGPIO, spichannel=self.config.Rfm69SPIChannel, pigpiohost=self.config.PIGPIOHost, pigpioport=self.config.PIGPIOPort) as s69Tx:

                    s69Tx.sendWaveForm(wf)


        finally:
            self.lock.release()
            self.LogDebug("sendCommand: Lock released")

    


class operateShutters(MyLog):

    def __init__(self, args = None):
        super(operateShutters, self).__init__()
        self.ProgramName = "operate Somfy Shutters"
        self.Version = "Unknown"
        self.log = None
        self.IsStopping = False
        self.ProgramComplete = False

        if args.ConfigFile == None:
            self.ConfigFile = "/etc/operateShutters.conf"
        else:
            self.ConfigFile = args.ConfigFile

        self.console = SetupLogger("shutters_console", log_file = "", stream = True)

        if os.geteuid() != 0:
            self.LogConsole("You are not running as sudo, you will need to ensure you have appropriate permissions for your config (i.e. ports less than 1024) or run this script as sudo")

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
        self.log = SetupLogger("shutters", self.config.LogLocation + "operateShutters-" + getpass.getuser() + ".log", stream=self.config.LogToConsole)
        self.config.log = self.log

        if self.IsLoaded():
            self.LogWarn("operateShutters.py is already loaded.")
            sys.exit(1)

        if self.config.PIGPIOHost == "localhost" and not self.startPIGPIO():
            self.LogConsole("Not able to start PIGPIO")
            sys.exit(1)

        self.shutter = Shutter(log = self.log, config = self.config)

        # atexit.register(self.Close)
        # signal.signal(signal.SIGTERM, self.Close)
        # signal.signal(signal.SIGINT, self.Close)

        self.schedule = Schedule(log = self.log, config = self.config)
        self.scheduler = None
        self.webServer = None

        if (args.echo == True):
            self.alexa = Alexa(kwargs={'log':self.log, 'shutter': self.shutter, 'config': self.config})

        if (args.mqtt == True):
            self.mqtt = MQTT(kwargs={'log':self.log, 'shutter': self.shutter, 'config': self.config})

        self.ProcessCommand(args);

    #------------------------ operateShutters::IsLoaded -----------------------------
    #return true if program is already loaded
    def IsLoaded(self):

        file_path = '/var/lock/'+os.path.basename(__file__).replace('.','') + ".lock"
        global file_handle

        create_file = not os.path.exists(file_path)
        try:
            file_handle = open(file_path, 'w' if create_file else 'r')
            if create_file:
                # Define the new file permissions
                new_permissions = 0o644
                # Change the file permissions
                os.chmod(file_path, new_permissions)
            fcntl.flock(file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except IOError as err:
            return True

    #--------------------- operateShutters::startPIGPIO ------------------------------

    def startPIGPIO(self):
        
        status, process = processcommands.getstatusoutput('pidof pigpiod')
        if status:  #  it wasn't running, so start it
            
            if os.geteuid() == 0:
                self.LogInfo ("pigpiod was not running, trying to start it")
                processcommands.getstatusoutput('sudo pigpiod -l -m')  # try to  start it
                time.sleep(0.5)
                # check it again
                status, process = processcommands.getstatusoutput('pidof pigpiod')
            else:
                self.LogInfo ("pigpiod was not running and you are not running as sudo, try to start it from a command prompt with the following command: sudo pigpiod -l -m")

        if not status:  # if it was started successfully (or was already running)...
            pigpiod_process = process
            self.LogInfo ("pigpiod is running, process ID is {} ".format(pigpiod_process))

            try:
                pi = pigpio.pi()  # local GPIO only
                if not pi.connected:
                    self.LogError("pigpio connection could not be established. Check logs to get more details.")
                    return False
                else:
                    self.LogInfo("pigpio's pi instantiated.")
            except Exception as e:
                start_pigpiod_exception = str(e)
                self.LogError("problem instantiating pi: {}".format(start_pigpiod_exception))
        else:
            self.LogError("start pigpiod was unsuccessful.")
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
            self.LogInfo ("lowering shutter for 7 seconds")
            self.shutter.lowerPartial(self.config.ShuttersByName[args.shutterName], 7)
            time.sleep(7)
            self.LogInfo ("rise shutter for 7 seconds")
            self.shutter.risePartial(self.config.ShuttersByName[args.shutterName], 7)
        elif ((args.shutterName != "") and (args.duskdawn is not None)):
            self.schedule.addRepeatEventBySunrise([self.config.ShuttersByName[args.shutterName]], 'up', args.duskdawn[1], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
            self.schedule.addRepeatEventBySunset([self.config.ShuttersByName[args.shutterName]], 'down', args.duskdawn[0], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
            self.scheduler = Scheduler(kwargs={'log':self.log, 'schedule':self.schedule, 'shutter': self.shutter, 'config': self.config})
            self.scheduler.setDaemon(True)
            self.scheduler.start()
            if (args.echo == True):
                self.alexa.setDaemon(True)
                self.alexa.start()
            if (args.mqtt == True):
                self.mqtt.setDaemon(True)
                self.mqtt.start()
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
            self.schedule.loadScheudleFromConfig()
            self.scheduler = Scheduler(kwargs={'log':self.log, 'schedule':self.schedule, 'shutter': self.shutter, 'config': self.config})
            self.scheduler.setDaemon(True)
            self.scheduler.start()
            if (args.echo == True):
                self.alexa.setDaemon(True)
                self.alexa.start()
            if (args.mqtt == True):
                self.mqtt.setDaemon(True)
                self.mqtt.start()
            self.webServer = FlaskAppWrapper(name='WebServer', static_url_path=os.path.dirname(os.path.realpath(__file__))+'/html', log = self.log, shutter = self.shutter, schedule = self.schedule, config = self.config)
            self.webServer.run()
        else:
            parser.print_help()

        if (args.echo == True):
            self.alexa.setDaemon(True)
            self.alexa.start()
        if (args.mqtt == True):
            self.mqtt.setDaemon(True)
            self.mqtt.start()

        if (args.echo == True):
            self.alexa.join()
        if (args.mqtt == True):
            self.mqtt.join()
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
            if (not self.scheduler == None):
                self.LogError("Stopping Scheduler. This can take up to 1 second...")
                self.scheduler.shutdown_flag.set()
                self.scheduler.join()
                self.LogError("Scheduler stopped. Now exiting.")
            if (not self.alexa == None):
                self.LogError("Stopping Alexa Listener. This can take up to 1 second...")
                self.alexa.shutdown_flag.set()
                self.alexa.join()
                self.LogError("Alexa Listener stopped. Now exiting.")
            if (not self.mqtt == None):
                self.LogError("Stopping MQTT Listener. This can take up to 1 second...")
                self.mqtt.shutdown_flag.set()
                self.mqtt.join()
                self.LogError("MQTT Listener stopped. Now exiting.")
            if (not self.webServer == None):
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
    except:
        sys.exit(1)
    
    sys.exit(0)
