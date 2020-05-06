# Detect portscans of host, automatically blacklist addresses that scan and runs connecting addresses to see if they were similar to blacklisted
from scapy.all import *
import os
import sys
from datetime import datetime
import socket
from collections import OrderedDict
import iptc

#  Logic of program:
#  Sniff network for (TCP ONLY RIGHT NOW) connections
#  Log each connection in the dictionary
#       ->Only keep track of N number of connections
#       ->If an incoming connection connects to more than the scan threshold of ports
#           add it to the blocklist
#       -> If in blocklist, make an IPtable rule to prevent future connections
#



#This value is how many port connections an IP connects to on the host before it is considered hostile
SCANTHRESHOLD = 25
#This value is how many seconds a 2 potential scans must be within to stay in the log
TIMEOUT = 10

class Connection():
        def __init__(self, pkt):
                self.src = pkt[IP].src
                self.dst = pkt[IP].dst
                self.ports = set()
                self.time = pkt.time
                self.timeStamp = datetime.fromtimestamp(pkt.time)
                self.pkt = pkt


def printTime(t):
        return str(t.strftime('%Y-%m-%d %H:%M:%S.%f'))
def timeStamp(pkt):
        #print(datetime.fromtimestamp(pkt.time).strftime('%Y-%m-%d %H:%M:%S.%f'))
        return datetime.fromtimestamp(pkt.time)

def getFlags(pkt):
        F = pkt[TCP].flags
        return F


blockList = set()
connections = OrderedDict() #a dictionary of connections to the host, maintains insertion order
                #k,v = ip, pkt
maxConnections = 50


#_______FIGURE OUT A WAY TO HAVE A MAX SIZE DICT
def addConn(key,conn):
        connections[key] = conn
        if len(connections) > maxConnections:
                connections.popitem(False); #pops the fist item

def block(ip):
    rule = iptc.Rule()
    rule.protocol = "tcp"
    rule.src = ip
    rule.target = rule.create_target("DROP")
    chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "INPUT")
    chain.insert_rule(rule)

def process_packet(pkt):
        #TCP Connect scan
        # Connect 18
        # Syn 2
        # Fin 1
        # Ack 16
        
        if TCP in pkt:
                srcIP = pkt[IP].src
                dstIP = pkt[IP].dst
                srcPrt = pkt[IP].sport
                dstPrt = pkt[IP].dport
                flags = getFlags(pkt)

                if pkt[IP].src in blockList:
                    rule = iptc.Rule()
                    rule.src = srcIP

                key = srcIP
                if key in connections:
                        connection = connections[key]
                        connection.timeStamp = timeStamp(pkt)
                        connection.time = pkt.time
                        connection.ports.add(dstPrt)
                if key not in connections:
                        connection = Connection(pkt)
                        addConn(key,connection)
                        print("----------------Adding Connection----------------")
                        print("[+] "+ str(datetime.fromtimestamp(connection.time)) +" "+srcIP+":"+str(srcPrt) +" -> "+dstIP+":"+str(dstPrt))
                        print("Flag: "+ str(flags))
                        if flags ==0:
                                print("TCP Null Scan")
                        if flags == 1:
                                print("TCP Fin Scan")
                        if flags == 2:
                                print("TCP Syn Scan")
                        if flags == 16:
                                print("TCP Ack Scan")
                        if flags == 18:
                                print("TCP Connect Scan")
                        print("--------------------------------------------------")
                if len(connections[key].ports) >= SCANTHRESHOLD:

                        print("[!]============ Port scan detected============")
                        print(connections[key].src)
                        
                        blockList.add(connections[key])
                        print(str(datetime.fromtimestamp(connections[key].time))+": "+connections[key].src)

                        print("--------------------------------------------------")
                        block(str(key)) 
                        
                        return
            

def log(iface=None):
        hostIP = str(socket.gethostbyname(socket.gethostname()))
        filterStr = "ip and dst host "+hostIP
        sniff(filter= filterStr, prn=process_packet, iface = iface)
def main():
        #check if user is root/sudo
        try:
            if os.geteuid() == 0:
                    log()
            else:
                    print("[-] Warning: Must run as root.")
                    sys.exit()
        finally:
                print()
                print([x.src for x in blockList])
                sys.exit(0)
if __name__ == '__main__':
        main()
 
