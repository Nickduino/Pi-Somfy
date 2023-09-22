#!/usr/bin/python3
import logging
try:
    from flask import Flask, render_template, request, Response, jsonify, json
except Exception as e1:
    print("\n\nThis program requires the Flask library. Please see the project documentation at https://github.com/Nickduino/Pi-Somfy.\n")
    print("Error: " + str(e1))
    sys.exit(2)

import sys, signal, os, socket, atexit, time, subprocess, threading, signal, errno, collections, traceback

try:
    from mylog import MyLog
except Exception as e1:
    print("\n\nThis program requires the modules located from the same github repository that are not present.\n")
    print("Error: " + str(e1))
    sys.exit(2)

class EndpointAction():

    def __init__(self, action):
        self.action = action
        self.response = Response(status=200, headers={})

    def __call__(self, *args, **kwargs):
        if ((len(args) > 0) or (len(kwargs) > 0)):
            self.response = self.action(args, kwargs)
        else:   
            self.response = self.action()
        return self.response


class FlaskAppWrapper(MyLog):
    app = None
    CriticalLock = None

    def __init__(self, name = __name__, static_url_path = '', log = None, shutter = None, schedule = None, config = None):
        if log != None:
            self.log = log
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
    
        self.shutter = shutter
        self.schedule = schedule
        self.config = config
        
        self.app = Flask(import_name=name, static_url_path="", static_folder=static_url_path)
        self.app.after_request(self.add_header)
        self.add_endpoint(endpoint='/', endpoint_name='main', handler=self.requestMain)
        self.add_endpoint(endpoint='/shutdown', endpoint_name='shutdown', handler=self.shutdown_server)
        self.add_endpoint(endpoint='/cmd/<command>', endpoint_name='cmd', handler=self.processCommand, methods=['GET', 'POST'])
        
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
        
    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, methods=['GET']):
        self.app.add_url_rule(endpoint, endpoint_name, EndpointAction(handler), methods=methods)

    def requestMain(self):
        if not self.validatePassword(header=False):
            return self.app.send_static_file("error.html")
        self.LogDebug(request.url)
        return self.app.send_static_file('index.html')
        
    def processCommand(self, *args, **kwargs):
        self.LogDebug(request.url + " ( "+ request.method + " ): "+ str(args) + " | "+ str(kwargs))
        try:
            # self.LogDebug(request.values.get('sitename', 0, type=str))
            # self.LogDebug("JSON: "+str(request.get_json()))
            # self.LogDebug("RAW: "+str(request.get_data()))
            command = args[1]['command']
            if command in ["up", "down", "stop", "program", "press", "getConfig", "addSchedule", "editSchedule", "deleteSchedule", "addShutter", "editShutter", "deleteShutter", "setLocation" ]:
                self.LogInfo("processing Command \"" + command + "\" with parameters: "+str(request.values))
                result = getattr(self, command)(request.values)
                return Response(json.dumps(result), status=200)
            else:
                self.LogWarn("UNKNOWN COMMAND " + command)
                return Response("Error: Unknown Command: " + command, status=400)
        except Exception as e1:
            tb = traceback.format_exc()
            self.LogErrorLine("Error in Process Command: " + command + ": " + str(e1))
            self.LogError(tb)
            return Response("Error: Exception occured", status=400)

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
        
    def up(self, params):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        shutter=params.get('shutter', 0, type=str)
        self.LogDebug("rise shutter \""+shutter+"\"")
        if (not shutter in self.config.Shutters):
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        self.shutter.rise(shutter)
        return {'status': 'OK'}

    def down(self, params):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        shutter=params.get('shutter', 0, type=str)
        self.LogDebug("lower shutter \""+shutter+"\"")
        if (not shutter in self.config.Shutters):
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        self.shutter.lower(shutter)
        return {'status': 'OK'}

    def stop(self, params):
        if not self.validatePassword():
            return {'status': 'ERROR'}
        shutter=params.get('shutter', 0, type=str)
        self.LogDebug("stop shutter \""+shutter+"\"")
        if (not shutter in self.config.Shutters):
            return {'status': 'ERROR', 'message': 'Shutter does not exist'}
        self.shutter.stop(shutter)
        return {'status': 'OK'}

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
            id = "0x%0.2X" % tmp_id
            code = 1
            self.LogDebug("got a new shutter id: "+id)
            self.config.WriteValue(str(id), str(name)+",True,"+str(duration), section="Shutters");
            self.config.WriteValue(str(id), str(code), section="ShutterRollingCodes");
            self.config.WriteValue(str(id), str(None), section="ShutterIntermediatePositions");
            self.config.ShuttersByName[name] = id
            self.config.Shutters[id] = {'name': name, 'code': code, 'duration': duration, 'durationDown': int(duration), 'durationUp': int(duration), 'intermediatePosition': None}
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
        elif ((name == self.config.Shutters[id]['name']) and (duration == self.config.Shutters[id]['duration'])):
            return {'status': 'ERROR', 'message': 'Neither Name nor Duration has not changed, remaining the same.'}
        elif ((name != self.config.Shutters[id]['name']) and (name in self.config.ShuttersByName)):
            return {'status': 'ERROR', 'message': 'Name is not unique'}
        elif ("," in name):
            return {'status': 'ERROR', 'message': 'New name can not contain COMMAS'}
        elif not self.isfloat(duration):
            return {'status': 'ERROR', 'message': 'seconds must be a number (may contain decimals)'}
        else:
            self.config.WriteValue(str(id), str(name)+",True,"+str(duration), section="Shutters");
            self.config.ShuttersByName.pop(self.config.Shutters[id]['name'], None)
            self.config.ShuttersByName['name'] = id
            self.config.Shutters[id]['name'] = name
            self.config.Shutters[id]['duration'] = duration
            return {'status': 'OK'}

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
        for k in self.config.Shutters:
            shutters[k] = self.config.Shutters[k]['name']  
            durations[k] = self.config.Shutters[k]['durationDown']            
        obj = {'Latitude': self.config.Latitude, 'Longitude': self.config.Longitude, 'Shutters': shutters, 'ShutterDurations': durations, 'Schedule': self.schedule.getScheduleAsDict()}
        self.LogDebug("getConfig called, sending: "+json.dumps(obj))
        return obj

    def generate_adhoc_ssl_context(self):
        """Generates an adhoc SSL context for the development server."""
        #        crypto = _get_openssl_crypto_module()
        import tempfile
        import atexit
        from random import random
        
        cert = crypto.X509()
        cert.set_serial_number(int(random() * sys.maxsize))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(60 * 60 * 24 * 365)

        subject = cert.get_subject()
        subject.CN = '*'
        subject.O = 'Dummy Certificate'

        issuer = cert.get_issuer()
        issuer.CN = 'Untrusted Authority'
        issuer.O = 'Self-Signed'

        pkey = crypto.PKey()
        pkey.generate_key(crypto.TYPE_RSA, 2048)
        cert.set_pubkey(pkey)
        cert.sign(pkey, 'sha256')

        cert_handle, cert_file = tempfile.mkstemp()
        pkey_handle, pkey_file = tempfile.mkstemp()
        atexit.register(os.remove, pkey_file)
        atexit.register(os.remove, cert_file)
    
        os.write(cert_handle, crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        os.write(pkey_handle, crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey))
        os.close(cert_handle)
        os.close(pkey_handle)
        # ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
        ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ctx.load_cert_chain(cert_file, pkey_file)
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


    def run(self):
        if self.config.UseHttps:
            import ssl
            from OpenSSL import crypto
            self.LogInfo("Starting secure WebServer on Port "+str(self.config.HTTPSPort))
            self.app.run(host="0.0.0.0", port=self.config.HTTPSPort, threaded = True, ssl_context=self.generate_adhoc_ssl_context(), use_reloader = False, debug = False)
        else:
            self.LogInfo("Starting WebServer on Port "+str(self.config.HTTPPort))
            self.app.run(host="0.0.0.0", threaded = True, port=self.config.HTTPPort, use_reloader = False, debug = False)
        self.LogInfo("Stopping WebServer")





