
import usb.core
import usb.util
from array import array
from random import randint
import struct
import sys

class CypressError(Exception):
    """Base class for other exceptions"""
    pass 

class CypressWriteRequestError(CypressError):
    """Raised if an USB write error occours"""
    pass

class CypressReadResponseError(CypressError):
    """Raised if an USB read error occours"""
    pass

class CypressOpcError(CypressError):
    """Raised for wrong operation code"""
    pass

class CypressSeqError(CypressError):
    """Raised for response wrong sequence number"""
    pass

class Cypress():

    def __init__(self):
        self.opc_rd = 0x20
        self.opc_wr = 0x10
        self.ep_rd = (6 | 128)
        self.ep_wr = 2
        self.ep_data = (8 | 128)
        self.dev = None

    def open(self, index):
        self.lst = list(usb.core.find(idVendor=0x04b4, idProduct=0x8613, find_all=True))

        try:
           self.dev = self.lst[index]
        except Exception as e:
          print("ERROR: Cypress device not found")
          sys.exit(1)
        else:
           self.dev.set_configuration(1)
           self.dev.set_interface_altsetting(interface = 0, alternate_setting = 1)

    def busclear(self):
        while True:
            try:
                data = self.dev.read(self.ep_rd, 1)
            except usb.core.USBError as e:
                break

    def readmem(self, addr):
        wrbuf = array('B')
        wrbuf.append(self.opc_rd)
        seq = randint(1,15)
        wrbuf.append(seq)
        wrbuf.append((addr & 0xFF00) >> 8)
        wrbuf.append(addr & 0x00FF)

        wrbuf[0], wrbuf[1] = wrbuf[1], wrbuf[0]
        wrbuf[2], wrbuf[3] = wrbuf[3], wrbuf[2]

        # write request
        try:
            self.dev.write(self.ep_wr, wrbuf)
        except:
            raise CypressWriteRequestError("Cypress error sending READ(addr) request")

        # read response
        try:
           rdbuf = self.dev.read(self.ep_rd, 4)
        except:
           raise CypressReadResponseError("Cypress error receiving READ(addr) response")

        rdbuf[0], rdbuf[1] = rdbuf[1], rdbuf[0]
        rdbuf[2], rdbuf[3] = rdbuf[3], rdbuf[2]

        if(rdbuf[0] != self.opc_rd):
            raise CypressOpcError("Cypress op code error in WRITE(addr,val) response")

        if(rdbuf[1] != seq):
            raise CypressSeqError("Cypress seq number error in WRITE(addr,val) response")

        value = rdbuf[3] + (rdbuf[2] << 8)

        return(value)

    def writemem(self, addr, value):
        wrbuf = array('B')
        wrbuf.append(self.opc_wr)
        seq = randint(1,15)
        wrbuf.append(seq)
        wrbuf.append((addr & 0xFF00) >> 8)
        wrbuf.append(addr & 0x00FF)
        wrbuf.append((value & 0xFF00) >> 8)
        wrbuf.append(value & 0x00FF)

        wrbuf[0], wrbuf[1] = wrbuf[1], wrbuf[0]
        wrbuf[2], wrbuf[3] = wrbuf[3], wrbuf[2]
        wrbuf[4], wrbuf[5] = wrbuf[5], wrbuf[4]

        # write request
        try:
            self.dev.write(self.ep_wr, wrbuf)
        except:
            raise CypressWriteRequestError("Cypress error sending WRITE(addr,val) request")

        # read response 
        try:
            rdbuf = self.dev.read(self.ep_rd, 4)
        except:
            raise CypressReadResponseError("Cypress error receiving WRITE(addr,val) response")

        rdbuf[0], rdbuf[1] = rdbuf[1], rdbuf[0]

        if(rdbuf[0] != self.opc_wr):
            raise CypressOpcError("Cypress op code error in WRITE(addr,val) response")

        if(rdbuf[1] != seq):
            raise CypressSeqError("Cypress seq number error in WRITE(addr,val) response")

    def readhist(self):
        rdhist8 = array('B')
        # read histogram
        while True:
           try:
              chunk = self.dev.read(self.ep_data, 1024, timeout=100)
           except Exception as e:
              #print(e)
              #raise CypressReadResponseError("Cypress error receiving histogram data: " + str(e))	
              break;
           else:
              rdhist8.extend(chunk)

        count = len(rdhist8) // 2
        rdhist16 = struct.unpack('H'*count, rdhist8)

        # delete element '32768'
        hist = array('H')
        for item in rdhist16:
           if item != 32768:
              hist.append(item)

        return(hist[:-9])
