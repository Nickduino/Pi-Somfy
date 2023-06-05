#!/usr/bin/python3

import threading
try:
    from ConfigParser import RawConfigParser
except ImportError as e:
    from configparser import RawConfigParser

from mylog import MyLog

class MyConfig (MyLog):
    #---------------------MyConfig::__init__------------------------------------
    def __init__(self, filename = None, section = None, log = None):

        super(MyLog, self).__init__()
        self.log = log
        self.FileName = filename
        self.Section = section
        self.CriticalLock = threading.Lock()        # Critical Lock (writing conf file)
        self.InitComplete = False

        self.LogLocation = "/var/log/"
        self.Latitude = 51.4769
        self.Longitude = 0
        self.SendRepeat = 1
        self.UseHttps = False
        self.HTTPPort = 80
        self.HTTPSPort = 443
        self.RTS_Address = "0x279620"
        self.MQTT_ClientID = "somfy-mqtt-bridge"
        self.Shutters = {}
        self.ShuttersByName = {}
        self.Schedule = {}
        self.Password = ""

        try:
            self.config = RawConfigParser()
            self.config.read(self.FileName)

            if self.Section == None:
                SectionList = self.GetSections()
                if len(SectionList):
                    self.Section = SectionList[0]

        except Exception as e1:
            self.LogErrorLine("Error in MyConfig:init: " + str(e1))
            return
        self.InitComplete = True

    # -------------------- MyConfig::LoadConfig-----------------------------------
    def LoadConfig(self):

        parameters = {'LogLocation': str, 'Latitude': float, 'Longitude': float, 'SendRepeat': int, 'UseHttps': bool, 'HTTPPort': int, 'HTTPSPort': int, 'TXGPIO': int, 'RTS_Address': str, "Password": str}
        
        self.SetSection("General");
        for key, type in parameters.items():
            try:
                if self.HasOption(key):
                    setattr(self, key, self.ReadValue(key, return_type=type))
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section General for key "+key+": " + str(e1))
                return False

        parameters = {'MQTT_Server': str, 'MQTT_Port': int, 'MQTT_User': str, 'MQTT_Password': str, 'MQTT_ClientID': str, 'EnableDiscovery': bool}
        
        self.SetSection("MQTT");
        for key, type in parameters.items():
            try:
                if self.HasOption(key):
                    setattr(self, key, self.ReadValue(key, return_type=type))
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section General for key "+key+": " + str(e1))
                return False

        self.SetSection("Shutters");
        shutters = self.GetList();
        for key, value in shutters:
            try:
                param1 = value.split(",")
                if param1[1].strip().lower() == 'true':
                   if (len(param1) < 3):
                       param1.append("10");
                   elif (param1[2].strip() == "") or (int(param1[2]) <= 0) or (int(param1[2]) >= 100):
                       param1[2] = "10"
                   param2 = int(self.ReadValue(key, section="ShutterRollingCodes",          return_type=int))
                   param3 =     self.ReadValue(key, section="ShutterIntermediatePositions", return_type=int)
                   if (param3 != None) and ((param3 < 0) or (param3 > 100)):
                       param3  = None
                   # If only one duration is specified, use it for both down and up durations.
                   if len (param1) < 4:
                      param1.append(param1[2])
                   self.Shutters[key] = {'name': param1[0], 'code': param2, 'duration': param1[2], 'durationDown': int(param1[2]), 'durationUp': int(param1[3]), 'intermediatePosition': param3}
                   self.ShuttersByName[param1[0]] = key
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section Shutters for key "+key+": " + str(e1))
                return False
                                   
        self.SetSection("Scheduler")
        schedules = self.GetList()
        for key, value in schedules:
            try:
                param = value.split(",")
                if param[0].strip().lower() in ('active', 'paused'):
                   self.Schedule[key] = {'active': param[0], 'repeatType': param[1], 'repeatValue': param[2], 'timeType': param[3], 'timeValue': param[4], 'shutterAction': param[5], 'shutterIds': param[6]}
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section Scheduler for key "+key+": " + str(e1))
                return False
                                   
        return True

    #---------------------MyConfig::setLocation---------------------------------
    def setLocation(self, lat, lng):
        self.WriteValue("Latitude", lat, section="General");
        self.WriteValue("Longitude", lng, section="General");
        self.Latitude = lat
        self.Longitude = lng

    #---------------------MyConfig::setCode---------------------------------
    def setCode(self, shutterId, code):
        self.WriteValue(shutterId, str(code).upper(), section="ShutterRollingCodes");
        self.Shutters[shutterId]['code'] = code
        

    #---------------------MyConfig::HasOption-----------------------------------
    def HasOption(self, Entry):

        return self.config.has_option(self.Section, Entry)

    #---------------------MyConfig::GetList-------------------------------------
    def GetList(self):

        return self.config.items(self.Section)

    #---------------------MyConfig::GetSections---------------------------------
    def GetSections(self):

        return self.config.sections()

    #---------------------MyConfig::SetSection----------------------------------
    def SetSection(self, section):

        # if not (isinstance(section, str) or isinstance(section, unicode)) or not len(section):
        if not len(section):
            self.LogError("Error in MyConfig:ReadValue: invalid section: " + str(section))
            return False
        self.Section = section
        return True
    #---------------------MyConfig::ReadValue-----------------------------------
    def ReadValue(self, Entry, return_type = str, default = None, section = None, NoLog = False):

        try:

            if section != None:
                self.SetSection(section)

            if self.config.has_option(self.Section, Entry):
                if return_type == str:
                    return self.config.get(self.Section, Entry)
                elif return_type == bool:
                    return self.config.getboolean(self.Section, Entry)
                elif return_type == float:
                    return self.config.getfloat(self.Section, Entry)
                elif return_type == int:
                    if self.config.get(self.Section, Entry) == 'None':
                        return None
                    else:             
                        return self.config.getint(self.Section, Entry)
                else:
                    self.LogErrorLine("Error in MyConfig:ReadValue: invalid type:" + str(return_type))
                    return default
            else:
                return default
        except Exception as e1:
            if not NoLog:
                self.LogErrorLine("Error in MyConfig:ReadValue: " + Entry + ": " + str(e1))
            return default


    #---------------------MyConfig::WriteSection--------------------------------
    def WriteSection(self, SectionName):

        SectionList = self.GetSections()

        if SectionName in SectionList:
            self.LogError("Error in WriteSection: Section already exist.")
            return True
        try:
            with self.CriticalLock:
                with open(self.FileName, "a") as ConfigFile:
                    ConfigFile.write("[" + SectionName + "]")
                    ConfigFile.flush()
                    ConfigFile.close()
                    # update the read data that is cached
                    self.config.read(self.FileName)
            return True
        except Exception as e1:
            self.LogErrorLine("Error in WriteSection: " + str(e1))
            return False

    #---------------------MyConfig::WriteValue----------------------------------
    def WriteValue(self, Entry, Value, remove = False, section = None):

        if section != None:
            self.SetSection(section)

        SectionFound = False
        try:
            with self.CriticalLock:
                Found = False
                ConfigFile = open(self.FileName,'r')
                FileList = ConfigFile.read().splitlines()
                ConfigFile.close()
                
                mySectionStart = -1;
                mySectionEnd = -1;
                myLine = -1; 
                currentLastDataLine = -1;
                for i, line in enumerate(FileList):
                   if self.LineIsSection(line) and self.Section.lower() == self.GetSectionName(line).lower():
                      mySectionStart = i
                   elif mySectionStart >=0 and mySectionEnd == -1 and len(line.strip().split('=')) >= 2 and (line.strip().split('='))[0].strip() == Entry:
                      myLine = i
                   elif mySectionStart >=0 and mySectionEnd == -1 and self.LineIsSection(line):
                      mySectionEnd = currentLastDataLine

                   if not line.isspace() and not len(line.strip()) == 0 and not line.strip()[0] == "#":
                      currentLastDataLine = i
                if mySectionStart >=0 and mySectionEnd == -1:
                    mySectionEnd = currentLastDataLine    

                self.LogDebug("CONFIG FILE WRITE ->> mySectionStart = "+str(mySectionStart)+", mySectionEnd = "+str(mySectionEnd)+", myLine = "+str(myLine))
                if mySectionStart == -1:
                    raise Exception("NOT ABLE TO FIND SECTION:"+self.Section)

                ConfigFile = open(self.FileName,'w')
                for i, line in enumerate(FileList):
                    if myLine >= 0 and myLine == i and not remove:      # I found my line, now write new value
                       ConfigFile.write(Entry + " = " + Value + "\n")
                    elif myLine == -1 and mySectionEnd == i:            # Here we have to insert the new record...
                       ConfigFile.write(line+"\n")
                       ConfigFile.write(Entry + " = " + Value + "\n")
                    else:                                               # Nothing special, just copy the previous line....
                       ConfigFile.write(line+"\n")

                ConfigFile.flush()
                ConfigFile.close()
                # update the read data that is cached
                self.config.read(self.FileName)
            return True

        except Exception as e1:
            self.LogError("Error in WriteValue: " + str(e1))
            return False

    #---------------------MyConfig::GetSectionName------------------------------
    def GetSectionName(self, Line):

        Line = Line.strip()
        if Line.startswith("[") and Line.endswith("]") and len(Line) >=3 :
            Line = Line.replace("[", "")
            Line = Line.replace("]", "")
            return Line
        return ""
    #---------------------MyConfig::LineIsSection-------------------------------
    def LineIsSection(self, Line):

        Line = Line.strip()
        if Line.startswith("[") and Line.endswith("]") and len(Line) >=3 :
            return True
        return False
