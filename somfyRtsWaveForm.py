
import pigpio

def createWaveForm(txBcmPinNum, teleco, button, code, repetition, logger = None):

    checksum = 0

    frame = bytearray(7)
    
    frame[0] = 0xA7;       # Encryption key. Doesn't matter much
    frame[1] = button << 4 # Which button did  you press? The 4 LSB will be the checksum
    frame[2] = code >> 8               # Rolling code (big endian)
    frame[3] = (code & 0xFF)           # Rolling code

    frame[4] = teleco >> 16            # Remote address
    frame[5] = ((teleco >>  8) & 0xFF) # Remote address
    frame[6] = (teleco & 0xFF)         # Remote address

    outstring = "Frame  :    "
    for octet in frame:
        outstring = outstring + "0x%0.2X" % octet + ' '
    if logger == None:
        print(outstring)
    else:
        logger.info (outstring)

    for i in range(0, 7):
        checksum = checksum ^ frame[i] ^ (frame[i] >> 4)

    checksum &= 0b1111; # We keep the last 4 bits only

    frame[1] |= checksum;

    outstring = "With cks  : "
    for octet in frame:
        outstring = outstring + "0x%0.2X" % octet + ' '
    if logger == None:
        print(outstring)
    else:
        logger.info (outstring)


    for i in range(1, 7):
        frame[i] ^= frame[i-1];

    outstring = "Obfuscated :"
    for octet in frame:
        outstring = outstring + "0x%0.2X" % octet + ' '
    if logger == None:
        print(outstring)
    else:
        logger.info (outstring)


    #This is where all the awesomeness is happening. You're telling the daemon what you wanna send
    wf=[]
    wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 9415)) # wake up pulse
    wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 89565)) # silence
    for i in range(2): # hardware synchronization
        wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 2560))
        wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 2560))
    wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 4550)) # software synchronization
    wf.append(pigpio.pulse(0, 1<<txBcmPinNum,  640))

    for i in range (0, 56): # manchester enconding of payload data
        if ((frame[int(i/8)] >> (7 - (i%8))) & 1):
            wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 640))
            wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 640))
        else:
            wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 640))
            wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 640))

    wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 30415)) # interframe gap

    for j in range(1,repetition): # repeating frames
                for i in range(7): # hardware synchronization
                    wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 2560))
                    wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 2560))
                wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 4550)) # software synchronization
                wf.append(pigpio.pulse(0, 1<<txBcmPinNum,  640))

                for i in range (0, 56): # manchester enconding of payload data
                    if ((frame[int(i/8)] >> (7 - (i%8))) & 1):
                        wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 640))
                        wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 640))
                    else:
                        wf.append(pigpio.pulse(1<<txBcmPinNum, 0, 640))
                        wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 640))

                wf.append(pigpio.pulse(0, 1<<txBcmPinNum, 30415)) # interframe gap


    return wf