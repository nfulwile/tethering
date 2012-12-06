#!/usr/bin/python
"""This file is intended for the actual sniffing thread.  It will allow us to decide which packets we want to further handle,
	and then we can give them back to the websocket for it to send back to the client tun over the tethering phone """

#import logging
#logging.getLogger("scapy").setLevel(1)
from scapy.all import *
import socket
import fcntl
import struct
import sys
import os
import select

import alex #yeah I'll come up with a better name 

from threading import Thread
# so that i can test using their io in this file
import tornado.ioloop


#global variables
filter = 'tcp'
iface = 'eth0'
sniffer = None
# the event loop
ioloop = None

def quit():
	global sniffer
	if (sniffer != None):
		sniffer.running = False
	ioloop.stop()
def stars():
	print('**********************************************************')

commands={\
'q':quit,
'quit':quit,
's':stars,
}
#^^^^^^^^^
# handlers
def stdinHandler(fd, events):
	buff = sys.stdin.readline().strip()
	try:
		commands[buff]()
	except KeyError:
		print('Command not recognized:'+buff)

def run_sniff():
	global sniffer
	global ioloop
	try:
		ioloop = tornado.ioloop.IOLoop.instance()
		ioloop.add_handler(sys.stdin.fileno(), stdinHandler, ioloop.READ)
		sniffer = SniffingThread()
		sniffer.start()
		print('running sniffer: '+str(sniffer))
		ioloop.start()
	except Exception, err:
		print("ERROR: "+str(err))
	
	

def stopperCheck(sniffer):
	return sniffer.running

class SniffingThread(Thread):
    def __init__ (self, node):
        Thread.__init__(self)
        """We may want to have these as arguments to pass in, but for now I'm just stating them as globals above"""
        self.filter = filter
        self.iface = iface
        self.running = False
        self.node = node	# has reference to node that owns it

	def stopSniffing(self):
		self.running = False #we'll have to wait until stopperCheck is checked again by sniff function for this to be noticed        
      
    def pkt_callback(self,pkt):
        self.node.handle_sniffed(pkt) #this applies further filtering
                
    def run(self):
    	self.running = True
    	print('starting sniffing....')
    	# See why sniff has these funky parameters with code at bottom of file
        returnList = sniff(iface = self.iface, filter=self.filter, prn=self.pkt_callback, stopperTimeout=1, stopper=stopperCheck(self), store=0)
        print('done sniffing.  Results:')
        print(returnList)
		
 
# THIS IS A PATCH BY GOOGLE THAT I COPIED        
def sniff(count=0, store=1, offline=None, prn = None, lfilter=None, L2socket=None, timeout=None, stopperTimeout=None, stopper = None, *arg, **karg):
    """Sniff packets
sniff([count=0,] [prn=None,] [store=1,] [offline=None,] [lfilter=None,] + L2ListenSocket args) -> list of packets

  count: number of packets to capture. 0 means infinity
  store: wether to store sniffed packets or discard them
    prn: function to apply to each packet. If something is returned,
         it is displayed. Ex:
         ex: prn = lambda x: x.summary()
lfilter: python function applied to each packet to determine
         if further action may be done
         ex: lfilter = lambda x: x.haslayer(Padding)
offline: pcap file to read packets from, instead of sniffing them
timeout: stop sniffing after a given time (default: None)
stopperTimeout: break the select to check the returned value of 
         stopper() and stop sniffing if needed (select timeout)
stopper: function returning true or false to stop the sniffing process
L2socket: use the provided L2socket
    """
    c = 0

    if offline is None:
        if L2socket is None:
            L2socket = conf.L2listen
        s = L2socket(type=ETH_P_ALL, *arg, **karg)
    else:
        s = PcapReader(offline)

    lst = []
    if timeout is not None:
        stoptime = time.time()+timeout
    remain = None

    if stopperTimeout is not None:
        stopperStoptime = time.time()+stopperTimeout
    remainStopper = None
    while 1:
        try:
            if timeout is not None:
                remain = stoptime-time.time()
                if remain <= 0:
                    break

            if stopperTimeout is not None:
                remainStopper = stopperStoptime-time.time()
                if remainStopper <=0:
                    if stopper and stopper():
                        break
                    stopperStoptime = time.time()+stopperTimeout
                    remainStopper = stopperStoptime-time.time()

                sel = select.select([s],[],[],remainStopper)
                if s not in sel[0]:
                    if stopper and stopper():
                        break
            else:
                sel = select.select([s],[],[],remain)

            if s in sel[0]:
                p = s.recv(MTU)
                if p is None:
                    break
                if lfilter and not lfilter(p):
                    continue
                if store:
                    lst.append(p)
                c += 1
                if prn:
                    r = prn(p)
                    if r is not None:
                        print r
                if count > 0 and c >= count:
                    break
        except KeyboardInterrupt:
            break
    s.close()
    return plist.PacketList(lst,"Sniffed")



