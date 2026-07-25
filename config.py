#!/usr/bin/python3

import os, sys, time, json
import errno
import logging, logging.handlers
import threading
import re

try:
    from ConfigParser import RawConfigParser
except ImportError as e:
    from configparser import RawConfigParser

class _WinSafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that skips rotation on Windows when the log file
    is still locked by another open handle (WinError 32 / EACCES).
    On Linux/macOS the error is re-raised as normal."""
    def doRollover(self):
        try:
            logging.handlers.RotatingFileHandler.doRollover(self)
        except OSError as e:
            if sys.platform != 'win32' or e.errno != errno.EACCES:
                raise

#---------- SetupLogger --------------------------------------------------------
def SetupLogger(logger_name, log_file, level=logging.DEBUG, stream = False):


    logger = logging.getLogger(logger_name)

    # remove existing log handlers
    for handler in logger.handlers[:]:      # make a copy of the list
        logger.removeHandler(handler)

    logger.setLevel(level)

    formatter = logging.Formatter('%(asctime)s : [%(levelname)s] (%(threadName)-10s) %(message)s')

    if log_file != "":
        rotate = _WinSafeRotatingFileHandler(log_file, mode='a',maxBytes=50000,backupCount=5)
        rotate.setFormatter(formatter)
        logger.addHandler(rotate)

    if stream:      # print to screen also?
        streamHandler = logging.StreamHandler()
        # Dont format stream log messages
        logger.addHandler(streamHandler)


    return logging.getLogger(logger_name)

#------------ MyLog class -----------------------------------------------------
class MyLog(object):
    def __init__(self):
        self.log = None
        self.console = None
        pass

    #--------------------------------------------------------------------------
    def LogDebug(self, Message, LogLine = False):

        if not LogLine and self.log is not None:
            self.log.debug(Message)
        elif self.log is not None:
            self.log.debug(Message + " : " + self.GetErrorLine())

    #--------------------------------------------------------------------------
    def LogInfo(self, Message, LogLine = False):

        if not LogLine and self.log is not None:
            self.log.info(Message)
        elif self.log is not None:
            self.log.info(Message + " : " + self.GetErrorLine())
        
    #---------------------------------------------------------------------------
    def LogWarn(self, Message, LogLine = False):

        if not LogLine and self.log is not None:
            self.log.warning(Message)
        elif self.log is not None:
            self.log.warning(Message + " : " + self.GetErrorLine())
            
    #---------------------MyLog::LogConsole------------------------------------
    def LogConsole(self, Message):
        if self.console is not None:
            self.console.error(Message)

    #---------------------MyLog::LogError------------------------------------
    def LogError(self, Message):
        if self.log is not None:
            self.log.error(Message)

    #---------------------MyLog::FatalError----------------------------------
    def FatalError(self, Message):
        if self.log is not None:
            self.log.critical("FATAL: " + Message)
        raise Exception(Message)

    #---------------------MyLog::LogErrorLine--------------------------------
    def LogErrorLine(self, Message):
        if self.log is not None:
            self.log.error(Message + " : " + self.GetErrorLine())

    #---------------------MyLog::GetErrorLine--------------------------------
    def GetErrorLine(self):
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        lineno = exc_tb.tb_lineno
        return fname + ":" + str(lineno)

class MyConfig (MyLog):
    #---------------------MyConfig::__init__------------------------------------
    def __init__(self, filename = None, section = None, log = None):

        super(MyLog, self).__init__()
        self.log = log
        self.FileName = filename
        self.Section = section
        self.CriticalLock = threading.RLock()       # Critical Lock (reading/writing conf file)
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
        self.PhysicalRemotes = {}
        self.ShutterPositions = {}
        # Optional (unlike TXGPIO, not guaranteed present in defaultConfig.conf)
        # — must default to None so `is not None` checks don't raise
        # AttributeError on a config file that omits them.
        self.RXGPIO = None
        self.RXSpiSCK = None
        self.RXSpiMOSI = None
        self.RXSpiMISO = None
        self.RXSpiCSN = None

        try:
            self.config = RawConfigParser(strict=False)
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

        parameters = {'LogLocation': str, 'Latitude': float, 'Longitude': float, 'SendRepeat': int, 'UseHttps': bool, 'HTTPPort': int, 'HTTPSPort': int, 'TXGPIO': int, 'RTS_Address': str, "Password": str,
                      'RXGPIO': int, 'RXSpiSCK': int, 'RXSpiMOSI': int, 'RXSpiMISO': int, 'RXSpiCSN': int}
        
        for key, type in parameters.items():
            try:
                if self.HasOption(key, section="General"):
                    setattr(self, key, self.ReadValue(key, return_type=type, section="General"))
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section General for key "+key+": " + str(e1))
                return False

        parameters = {'MQTT_Server': str, 'MQTT_Port': int, 'MQTT_User': str, 'MQTT_Password': str, 'MQTT_ClientID': str, 'EnableDiscovery': bool}
        
        for key, type in parameters.items():
            try:
                if self.HasOption(key, section="MQTT"):
                    setattr(self, key, self.ReadValue(key, return_type=type, section="MQTT"))
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section MQTT for key "+key+": " + str(e1))
                return False

        shutters = self.GetList(section="Shutters")
        for key, value in shutters:
            try:
                param1 = value.split(",")
                if param1[1].strip().lower() == 'true':
                   if (len(param1) < 3):
                       param1.append("10");
                   elif (param1[2].strip() == "") or (int(float(param1[2])) <= 0) or (int(float(param1[2])) >= 600):
                       param1[2] = "10"
                   param2 = int(self.ReadValue(key, section="ShutterRollingCodes",          return_type=int))
                   param3 =     self.ReadValue(key, section="ShutterIntermediatePositions", return_type=int)
                   if (param3 != None) and ((param3 < 0) or (param3 > 100)):
                       param3  = None
                   # If only one duration is specified, use it for both down and up durations.
                   if len (param1) < 4:
                      param1.append(param1[2])
                   self.Shutters[key] = {'name': param1[0], 'code': param2, 'duration': param1[2], 'durationDown': int(float(param1[2])), 'durationUp': int(float(param1[3])), 'intermediatePosition': param3}
                   self.ShuttersByName[param1[0]] = key
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section Shutters for key "+key+": " + str(e1))
                return False
                                   
        schedules = self.GetList(section="Scheduler")
        for key, value in schedules:
            try:
                param = value.split(",")
                if param[0].strip().lower() in ('active', 'paused'):
                   self.Schedule[key] = {'active': param[0], 'repeatType': param[1], 'repeatValue': param[2], 'timeType': param[3], 'timeValue': param[4], 'shutterAction': param[5], 'shutterIds': param[6]}
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section Scheduler for key "+key+": " + str(e1))
                return False

        remotes = self.GetList(section="PhysicalRemotes")
        for key, value in remotes:
            try:
                self.PhysicalRemotes[key] = [s.strip() for s in value.split(",")]
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section PhysicalRemotes for key "+key+": " + str(e1))
                return False

        positions = self.GetList(section="ShutterPositions")
        for key, value in positions:
            try:
                self.ShutterPositions[key] = int(value)
            except Exception as e1:
                self.LogErrorLine("Missing config file or config file entries in Section ShutterPositions for key "+key+": " + str(e1))
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
        self.WriteValue(shutterId, str(code), section="ShutterRollingCodes");
        self.Shutters[shutterId]['code'] = code
        

    #---------------------MyConfig::HasOption-----------------------------------
    def HasOption(self, Entry, section = None):

        with self.CriticalLock:
            sect = section if section is not None else self.Section
            return self.config.has_option(sect, Entry)

    #---------------------MyConfig::GetList-------------------------------------
    def GetList(self, section = None):

        with self.CriticalLock:
            sect = section if section is not None else self.Section
            if not self.config.has_section(sect):
                return []
            return self.config.items(sect)

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

        with self.CriticalLock:
            try:
                sect = section if section is not None else self.Section

                if self.config.has_option(sect, Entry):
                    if return_type == str:
                        return self.config.get(sect, Entry)
                    elif return_type == bool:
                        return self.config.getboolean(sect, Entry)
                    elif return_type == float:
                        return self.config.getfloat(sect, Entry)
                    elif return_type == int:
                        if self.config.get(sect, Entry) == 'None':
                            return None
                        else:             
                            return self.config.getint(sect, Entry)
                    else:
                        self.LogErrorLine("Error in MyConfig:ReadValue: invalid type:" + str(return_type))
                        return default
                else:
                    return default
            except Exception as e1:
                if not NoLog:
                    self.LogErrorLine("Error in MyConfig:ReadValue: " + Entry + ": " + str(e1))
                return default

    #---------------------MyConfig::WriteValue----------------------------------
    # Regex patterns for INI file parsing
    _RE_SECTION = re.compile(r'^\s*\[([^\]]+)\]\s*$')
    _RE_KEY_VALUE = re.compile(r'^(\s*)([^#=][^=]*?)\s*=\s*(.*?)\s*$')

    def WriteValue(self, Entry, Value, section = None):

        sect = section if section is not None else self.Section

        try:
            with self.CriticalLock:
                with open(self.FileName, 'r') as f:
                    lines = f.read().splitlines()

                in_target_section = False
                section_header_line = -1
                key_line = -1
                last_data_line = -1  # last non-blank, non-comment line in target section

                for i, line in enumerate(lines):
                    m_sect = self._RE_SECTION.match(line)
                    if m_sect:
                        if in_target_section:
                            break  # reached next section, stop
                        if m_sect.group(1).strip().lower() == sect.lower():
                            in_target_section = True
                            section_header_line = i
                        continue

                    if in_target_section:
                        m_kv = self._RE_KEY_VALUE.match(line)
                        if m_kv and m_kv.group(2).strip() == Entry:
                            key_line = i
                        stripped = line.strip()
                        if stripped and not stripped.startswith('#'):
                            last_data_line = i

                if not in_target_section:
                    # Auto-create the missing section rather than failing:
                    # fresh installs get every section from defaultConfig.conf,
                    # but a pre-M1 config file being upgraded in place may be
                    # missing newer sections (e.g. [PhysicalRemotes],
                    # [ShutterPositions]) entirely.
                    lines.append("")
                    lines.append("[" + sect + "]")
                    section_header_line = len(lines) - 1

                if key_line >= 0:
                    # Replace existing key
                    lines[key_line] = Entry + " = " + Value
                else:
                    # Insert after last data line, or after section header if section is empty
                    insert_after = last_data_line if last_data_line >= 0 else section_header_line
                    lines.insert(insert_after + 1, Entry + " = " + Value)

                content = "\n".join(lines) + "\n"

                # Atomic write: write to temp file, then replace
                tmp = self.FileName + ".tmp"
                with open(tmp, 'w') as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                if sys.version_info[0] >= 3:
                    os.replace(tmp, self.FileName)
                else:
                    if os.path.exists(self.FileName):
                        os.remove(self.FileName)
                    os.rename(tmp, self.FileName)

                # update the read data that is cached
                self.config.read(self.FileName)
            return True

        except Exception as e1:
            self.LogError("Error in WriteValue: " + str(e1))
            return False

    #---------------------MyConfig::RemoveValue----------------------------------
    # Deletes a single key from a section — WriteValue can only replace/insert
    # a key, never remove one, which a real "unassign" (e.g. [PhysicalRemotes])
    # needs, unlike [Shutters]'s soft-delete-via-flag convention which doesn't
    # fit a plain "key = value" row shape. Mirrors WriteValue's exact
    # scan-then-atomic-rewrite pattern. Idempotent: removing an already-absent
    # key (or a section that doesn't exist at all) is not an error.
    def RemoveValue(self, Entry, section = None):

        sect = section if section is not None else self.Section

        try:
            with self.CriticalLock:
                with open(self.FileName, 'r') as f:
                    lines = f.read().splitlines()

                in_target_section = False
                key_line = -1

                for i, line in enumerate(lines):
                    m_sect = self._RE_SECTION.match(line)
                    if m_sect:
                        if in_target_section:
                            break  # reached next section, stop
                        if m_sect.group(1).strip().lower() == sect.lower():
                            in_target_section = True
                        continue

                    if in_target_section:
                        m_kv = self._RE_KEY_VALUE.match(line)
                        if m_kv and m_kv.group(2).strip() == Entry:
                            key_line = i
                            break

                if not in_target_section or key_line < 0:
                    return True  # nothing to remove — idempotent, not an error

                del lines[key_line]
                content = "\n".join(lines) + "\n"

                # Atomic write: write to temp file, then replace
                tmp = self.FileName + ".tmp"
                with open(tmp, 'w') as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                if sys.version_info[0] >= 3:
                    os.replace(tmp, self.FileName)
                else:
                    if os.path.exists(self.FileName):
                        os.remove(self.FileName)
                    os.rename(tmp, self.FileName)

                # RawConfigParser.read() only merges in additions/updates, it
                # never drops an option that disappeared from the file — the
                # removed key would otherwise stay stale in the cached view.
                try:
                    self.config.remove_option(sect, Entry)
                except Exception:
                    pass
                self.config.read(self.FileName)
            return True

        except Exception as e1:
            self.LogError("Error in RemoveValue: " + str(e1))
            return False
