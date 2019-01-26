#!/usr/bin/python3
import os, sys, time, json
import logging, logging.handlers

#---------- SetupLogger --------------------------------------------------------
def SetupLogger(logger_name, log_file, level=logging.DEBUG, stream = False):


    logger = logging.getLogger(logger_name)

    # remove existing logg handlers
    for handler in logger.handlers[:]:      # make a copy of the list
        logger.removeHandler(handler)

    logger.setLevel(level)

    formatter = logging.Formatter('%(asctime)s : [%(levelname)s] (%(threadName)-10s) %(message)s')

    if log_file != "":
        rotate = logging.handlers.RotatingFileHandler(log_file, mode='a',maxBytes=50000,backupCount=5)
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

        if ((not LogLine) and (not self.log == None)):
            self.log.debug(Message)
        elif (not self.log == None):
            self.log.debug(Message + " : " + self.GetErrorLine())
        # self.LogConsole(Message)

    #--------------------------------------------------------------------------
    def LogInfo(self, Message, LogLine = False):

        if ((not LogLine) and (not self.log == None)):
            self.log.info(Message)
        elif (not self.log == None):
            self.log.info(Message + " : " + self.GetErrorLine())
        # self.LogConsole(Message)
        
    #---------------------------------------------------------------------------
    def LogWarn(self, Message, LogLine = False):

        if ((not LogLine) and (not self.log == None)):
            self.log.warn(Message)
        elif (not self.log == None):
            self.log.warn(Message + " : " + self.GetErrorLine())
        # self.LogConsole(Message)
            
    #---------------------MyLog::LogConsole------------------------------------
    def LogConsole(self, Message):
        if not self.console == None:
            self.console.error(Message)

    #---------------------MyLog::LogError------------------------------------
    def LogError(self, Message):
        if (not self.log == None):
            self.log.error(Message)

    #---------------------MyLog::FatalError----------------------------------
    def FatalError(self, Message):
        if not self.log == None:
            self.log.critical("FATAL: " + Message)
        raise Exception(Message)

    #---------------------MyLog::LogErrorLine--------------------------------
    def LogErrorLine(self, Message):
        if (not self.log == None):
            self.log.error(Message + " : " + self.GetErrorLine())

    #---------------------MyLog::GetErrorLine--------------------------------
    def GetErrorLine(self):
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        lineno = exc_tb.tb_lineno
        return fname + ":" + str(lineno)

