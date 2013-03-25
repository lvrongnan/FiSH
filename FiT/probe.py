#probe.py
from twisted.internet.protocol import ClientFactory, Protocol
from twisted.internet import reactor
import json
from common import *
import logging

EVENT_CODES={
    0:'FILES_LISTED',
    2:'FILE_RECIEVED'
}
        
class HashListRetrieve(StreamLineProtocol):
    def __init__(self):
        StreamLineProtocol.__init__(self)

    def connectionMade(self):
        self.sendLine(FiTMessage(1,[]))

    def serviceMessage(self, message):
        success=True
        fileHT={}
        try:
            fileHT=json.loads(message)
        except:
            logging.error('Invalid JSON recieved from peer')
            success=False
        self.transport.loseConnection()
        self.factory.got_HT(success, fileHT)
  
class FileTransfer(StreamLineProtocol):
    def __init__(self, fileHash, f_container):
        StreamLineProtocol.__init__(self)
        self.fileHash=fileHash
        self.fObj=f_container
        self.retFn=self._FTReply
        self.fRem=0
        self.fSize=0
        self.state=0

    def connectionMade(self):
        self.sendLine(FiTMessage(2,[(self.fileHash,)]))
        self.state=1

    def serviceMessage(self, message):
        self.retFn(message)

    def _FTReply(self, reply):
        try:
            msg=FiTMessage(message_str=reply)
            if msg.key == 4:
                raise Exception(msg.data[0])
            elif msg.key != 3:
                raise Exception('Wrong Code')
        except Exception as e:
            logging.error('Failed to negotiate file transfer')
            self.transport.loseConnection()
            self.transport.got_file(False)
            return
        self.state=2
        self.fRem=int(msg.data[0][0])
        self.fSize=self.fRem
        reply_msg=FiTMessage(3,[(str(self.fSize),)])
        StreamLineProtocol.registerSpHandler(self, self.fillFile)
        self.sendLine(reply_msg)
        self.state=3

    def fillFile(self, data):
        self.fRem-=len(data)
        self.fObj.write(data)
        if self.fRem <= 0:
            self.fObj.close()
            self.transport.loseConnection()
            self.factory.got_file(True)
            

class FHFactory(ClientFactory):
    protocol=HashListRetrieve
    def __init__(self, def_obj):
        self.def_obj=def_obj

    def got_HT(self, success, fileHT):
        if self.def_obj is not None:
            d, self.def_obj = self.def_obj, None
            if success:    
                d.callback(fileHT)
            else:
                d.errback('Parsing JSON error')

    def clientConnectionFailed(self, connector, reason):
        if self.def_obj is not None:
            d, self.def_obj = self.def_obj, None
            d.errback(reason)

class FTFactory(ClientFactory):
    def __init__(self, fHash, f_container, def_obj):
        self.fHash=fHash
        self.fObj=f_container
        self.def_obj=def_obj

    def got_file(self, success):
        if self.def_obj is not None:
            d, self.def_obj = self.def_obj, None
            if success:    
                d.callback(True)
            else:
                d.errback('Truncted file transfer')
        
    def buildProtocol(self, addr):
        self.ftInst=FileTransfer(self.fHash, self.fObj)
        self.ftInst.factory=self
        return ftInst

    def clientConnectionFailed(self, connector, reason):
        if self.def_obj is not None:
            d, self.def_obj = self.def_obj, None
            d.errback(reason)