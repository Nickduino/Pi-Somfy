#!/usr/bin/python3
import logging
try:
    from flask import Flask, render_template, request, Response, jsonify, json
except Exception as e1:
    print("\n\nThis program requires the Flask library. Please see the project documentation at https://github.com/Nickduino/Pi-Somfy.\n")
    print("Error: " + str(e1))
    sys.exit(2)

import sys, signal, os, socket, atexit, time, subprocess, threading, errno, collections

try:
    from config import MyLog
    from receiver import button_name
except Exception as e1:
    print("\n\nThis program requires the modules located from the same github repository that are not present.\n")
    print("Error: " + str(e1))
    sys.exit(2)


class FlaskAppWrapper(MyLog):
    app = None

    def __init__(self, name = __name__, static_url_path = '', log = None, shutter = None, schedule = None, config = None, receiver = None):
        if log != None:
            self.log = log
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

        self.shutter = shutter
        self.schedule = schedule
        self.config = config
        self.receiver = receiver
        
        self.app = Flask(import_name=name, static_url_path="", static_folder=static_url_path)
        self.app.after_request(self.add_header)
        self.app.add_url_rule('/', 'main', self.requestMain)
        self.app.add_url_rule('/shutdown', 'shutdown', self.shutdown_server)
        self.app.add_url_rule('/cmd/<command>', 'cmd', self.processCommand, methods=['GET', 'POST'])
        
    def isfloat(self, value):
        try:
            float(value)
            return True
        except ValueError:
            return False
        
    def add_header(self, r):
        r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
        r.headers["Pragma"] = "no-cache"
        r.headers["Expires"] = "0"

        return r

    def requestMain(self):
        if not self.validatePassword(header=False):
            return self.app.send_static_file("error.html")
        self.LogDebug(request.url)
        return self.app.send_static_file('index.html')
        
    def processCommand(self, command):
        self.LogDebug(request.url + " ( "+ request.method + " ): command=" + command)
        try:
            if command in ["up", "down", "stop", "program", "press", "getConfig", "getStatus", "setPosition", "addSchedule", "editSchedule", "deleteSchedule", "addShutter", "editShutter", "deleteShutter", "setLocation", "getUnheardRemotes", "assignRemote", "unassignRemote", "setIntermediatePosition" ]:
                self.LogInfo("processing Command \"" + command + "\" with parameters: "+str(request.values))
                result = getattr(self, command)(request.values)
                return Response(json.dumps(result), status=200)
            else:
                self.LogWarn("UNKNOWN COMMAND " + command)
                return Response("Error: Unknown Command: " + command, status=400)
        except Exception as e1:
            self.LogErrorLine("Error in Process Command: " + command + ": " + str(e1))
            return Response("Error: Exception occurred", status=400)

    def validatePassword(self, header=True):
        # If no password configured, it's OK
        if self.config.Password == "":
            return True

        if header:
            # Support password from 'Password' header
            password = request.headers.get("Password")
        else:
            # Support password from 'Password' url param
            password = request.args.get("Password")

        if password != self.config.Password:
            self.LogDebug("received invalid password")
            self.LogDebug(password)
            return False
        return True

    def shutdown_server(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()
        return Response("Shutting Down", status=400)

    def _shutter_action(self, params, method, log_verb):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        shutter = params.get('shutter', 0, type=str)
        self.LogDebug(log_verb + " shutter \"" + shutter + "\"")
        if shutter not in self.config.Shutters:
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        getattr(self.shutter, method)(shutter)
        return {'status': 'OK'}

    def up(self, params):
        return self._shutter_action(params, 'rise', 'rise')

    def down(self, params):
        return self._shutter_action(params, 'lower', 'lower')

    def stop(self, params):
        return self._shutter_action(params, 'stop', 'stop')

    def program(self, params):
        shutter=params.get('shutter', 0, type=str)
        self.LogDebug("program shutter \""+shutter+"\"")
        if (not shutter in self.config.Shutters):
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        self.shutter.program(shutter)
        return {'status': 'OK'}

    def press(self, params):
        shutter=params.get('shutter', 0, type=str)
        buttons = params.get('buttons', 0, type=int)
        longPress = params.get('longPress', 0, type=str) == "true"
        self.LogDebug(("long" if longPress else "short") +" press buttons: \"" +str(buttons)+ "\" shutter \""+shutter+"\"")
        if (not shutter in self.config.Shutters):
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        self.shutter.pressButtons(shutter, buttons, longPress)
        return {'status': 'OK'}

    def setLocation(self, params):
        self.LogDebug("set Location: "+params.get('lat', 0, type=str)+" / "+params.get('lng', 0, type=str))
        self.config.setLocation(params.get('lat', 0, type=str), params.get('lng', 0, type=str))
        self.schedule.setUpdateTime()
        return {'status': 'OK'}

    def addShutter(self, params):
        if sys.version_info[0] < 3:
            import unicodedata
            name = params.get('name', 0, type=unicode)
            name = unicodedata.normalize('NFKD', name).encode('ascii','ignore')
            duration = params.get('duration', 0, type=unicode)
            duration = unicodedata.normalize('NFKD', duration).encode('ascii','ignore')
        else: 
            name = params.get('name', 0, type=str)
            duration = params.get('duration', 0, type=str)
        self.LogDebug("add shutter: "+ name)
        if (name in self.config.ShuttersByName):
            return {'status': 'ERROR', 'message': 'Name is not unique'}
        elif ("," in name):
            return {'status': 'ERROR', 'message': 'New name can not contain SPACES or COMMAS'}
        elif not self.isfloat(duration):
            return {'status': 'ERROR', 'message': 'seconds must be a number (may contain decimals)'}
        else:
            tmp_id = int(self.config.RTS_Address, 16)
            conflict = True
            while conflict == True:
                tmp_id = tmp_id+1
                conflict = False
                for key in self.config.Shutters:
                    if tmp_id == int(key, 16):
                        conflict = True
            id = "0x%0.2x" % tmp_id
            code = 1
            self.LogDebug("got a new shutter id: "+id)
            self.config.WriteValue(str(id), str(name)+",True,"+str(duration), section="Shutters");
            self.config.WriteValue(str(id), str(code), section="ShutterRollingCodes");
            self.config.WriteValue(str(id), str(None), section="ShutterIntermediatePositions");
            self.config.ShuttersByName[name] = id
            self.config.Shutters[id] = {'name': name, 'code': code, 'duration': duration, 'durationDown': int(float(duration)), 'durationUp': int(float(duration)), 'intermediatePosition': None}
            return {'status': 'OK', 'id': id}

    def editShutter(self, params):
        id = params.get('id', 0, type=str)
        if sys.version_info[0] < 3:
            import unicodedata
            name = params.get('name', 0, type=unicode)
            name = unicodedata.normalize('NFKD', name).encode('ascii','ignore')
            duration = params.get('duration', 0, type=unicode)
            duration = unicodedata.normalize('NFKD', duration).encode('ascii','ignore')
        else:
            name = params.get('name', 0, type=str)
            duration = params.get('duration', 0, type=str)
        self.LogDebug("edit shutter: "+id+" / "+name)
        if (not id in self.config.Shutters):
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        elif ((name == self.config.Shutters[id]['name']) and (int(float(duration)) == self.config.Shutters[id]['durationDown'])):
            return {'status': 'OK', 'nameChanged': False}  # Nothing changed – treat as silent success
        elif ((name != self.config.Shutters[id]['name']) and (name in self.config.ShuttersByName)):
            return {'status': 'ERROR', 'message': 'Name is not unique'}
        elif ("," in name):
            return {'status': 'ERROR', 'message': 'New name can not contain COMMAS'}
        elif not self.isfloat(duration):
            return {'status': 'ERROR', 'message': 'seconds must be a number (may contain decimals)'}
        else:
            nameChanged = (name != self.config.Shutters[id]['name'])
            self.config.WriteValue(str(id), str(name)+",True,"+str(duration), section="Shutters");
            self.config.ShuttersByName.pop(self.config.Shutters[id]['name'], None)
            self.config.ShuttersByName[name] = id
            self.config.Shutters[id]['name'] = name
            self.config.Shutters[id]['duration'] = duration
            self.config.Shutters[id]['durationDown'] = int(float(duration))
            self.config.Shutters[id]['durationUp'] = int(float(duration))
            return {'status': 'OK', 'nameChanged': nameChanged}

    def deleteShutter(self, params):
        id = params.get('id', 0, type=str)
        self.LogDebug("delete shutter: "+id)
        if (not id in self.config.Shutters):
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        else:
            self.config.WriteValue(str(id), self.config.Shutters[id]['name']+",False,"+self.config.Shutters[id]['duration'], section="Shutters");
            self.config.ShuttersByName.pop(self.config.Shutters[id]['name'], None)
            self.config.Shutters.pop(id, None)
            return {'status': 'OK'}

    def addSchedule(self, params):
        self.LogDebug("create new schedule")
        return self.schedule.addSchedule(params.to_dict(flat=False));

    def editSchedule(self, params):
        id = params.get('id', 0, type=str)
        self.LogDebug("change schedule: "+id)
        return self.schedule.editSchedule(id, params.to_dict(flat=False));

    def deleteSchedule(self, params):
        id = params.get('id', 0, type=str)
        self.LogDebug("delete schedule: "+id)
        return self.schedule.deleteSchedule(id);

    def getConfig(self, params):
        shutters = {}
        durations = {}
        movementStates = {}
        positions = {}
        intermediatePositions = {}
        for k in self.config.Shutters:
            shutters[k] = self.config.Shutters[k]['name']
            durations[k] = self.config.Shutters[k]['durationDown']
            movementStates[k] = self.shutter.getMovementState(k)
            positions[k] = self.shutter.getDisplayPosition(k)
            intermediatePositions[k] = self.config.Shutters[k]['intermediatePosition']
        obj = {'Latitude': self.config.Latitude, 'Longitude': self.config.Longitude, 'Shutters': shutters, 'ShutterDurations': durations, 'Schedule': self.schedule.getScheduleAsDict(), 'PhysicalRemotes': self.config.PhysicalRemotes, 'MovementStates': movementStates, 'Positions': positions, 'ShutterIntermediatePositions': intermediatePositions}
        self.LogDebug("getConfig called, sending: "+json.dumps(obj))
        return obj

    def getUnheardRemotes(self, params):
        remotes = {}
        if self.receiver is not None:
            # deque is oldest->newest; a plain dict keyed by address keeps
            # only the most recent press per address as we iterate forward.
            for address, button, rolling_code in self.receiver._unknown_remotes:
                remotes[address] = {'address': address, 'button': button,
                                    'buttonName': button_name(button),
                                    'rollingCode': rolling_code}
        return {'status': 'OK', 'remotes': list(remotes.values())}

    def assignRemote(self, params):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        address = params.get('address', 0, type=str).strip().lower()
        shutterIds = params.to_dict(flat=False).get('shutterIds[]', [])
        if not address:
            return {'status': 'ERROR', 'message': 'Address is required'}
        if not shutterIds:
            return {'status': 'ERROR', 'message': 'Select at least one shutter'}
        unknown = [s for s in shutterIds if s not in self.config.Shutters]
        if unknown:
            return {'status': 'ERROR', 'message': 'Unknown shutter(s): ' + ", ".join(unknown)}
        self.config.WriteValue(address, ",".join(shutterIds), section="PhysicalRemotes")
        self.config.PhysicalRemotes[address] = shutterIds
        return {'status': 'OK'}

    def unassignRemote(self, params):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        address = params.get('address', 0, type=str).strip().lower()
        if address not in self.config.PhysicalRemotes:
            return {'status': 'ERROR', 'message': 'Remote is not assigned'}
        if not self.config.RemoveValue(address, section="PhysicalRemotes"):
            return {'status': 'ERROR', 'message': 'Failed to update config file'}
        del self.config.PhysicalRemotes[address]
        return {'status': 'OK'}

    def setIntermediatePosition(self, params):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        shutter = params.get('shutter', 0, type=str)
        if shutter not in self.config.Shutters:
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        raw = params.get('position', 0, type=str).strip()
        if raw == "":
            position = None
        else:
            try:
                position = int(raw)
            except ValueError:
                return {'status': 'ERROR', 'message': 'Position must be a whole number between 0 and 100'}
            if position < 0 or position > 100:
                return {'status': 'ERROR', 'message': 'Position must be between 0 and 100'}
        self.config.WriteValue(shutter, str(position), section="ShutterIntermediatePositions")
        self.config.Shutters[shutter]['intermediatePosition'] = position
        return {'status': 'OK', 'intermediatePosition': position}

    def getStatus(self, params):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        shutters = {}
        for k in self.config.Shutters:
            shutters[k] = {
                'name': self.config.Shutters[k]['name'],
                'position': self.shutter.getDisplayPosition(k),
                'durationUp': self.config.Shutters[k]['durationUp'],
                'durationDown': self.config.Shutters[k]['durationDown'],
                'movementState': self.shutter.getMovementState(k)
            }
        return {'status': 'OK', 'shutters': shutters}

    def setPosition(self, params):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        shutter = params.get('shutter', 0, type=str)
        position = params.get('position', 0, type=int)
        self.LogDebug("setPosition shutter \"" + shutter + "\" to " + str(position))
        if shutter not in self.config.Shutters:
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        if position < 0 or position > 100:
            return {'status': 'ERROR', 'message': 'Position must be between 0 and 100'}
        current = self.shutter.getPosition(shutter)
        if position >= 100:
            self.shutter.rise(shutter)
        elif position <= 0:
            self.shutter.lower(shutter)
        elif position > current:
            self.shutter.risePartial(shutter, position)
        elif position < current:
            self.shutter.lowerPartial(shutter, position)
        return {'status': 'OK'}

    def run(self):
        host = "127.0.0.1" if sys.platform == "win32" else "0.0.0.0"
        # HTTPS is not implemented (UseHttps config option has no working code path)
        self.LogInfo("Starting WebServer on Port "+str(self.config.HTTPPort))
        self.app.run(host=host, threaded = True, port=self.config.HTTPPort, use_reloader = False, debug = False)
        self.LogInfo("Stopping WebServer")
