#! /usr/bin/env python3

from subprocess import Popen, PIPE
import logging
import datetime
import json

"""
 Varible setup
"""
DOWNLOAD_CAP = 200 # Gib

"""
 Logging setup
"""
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S',
                    filename='/var/log/system-monitor/torrent_alerts.log',
                    level=logging.DEBUG
                    )


def getTorrentStats(path="/var/lib/transmission-daemon/info/stats.json"):
    logging.info('Retriving stats...')
    try:
        f = open(path, "r")
        return json.load(f)
    except Exception as err:
        logging.error('Error: %s' % err)
    
def getPublicIP():
    child = Popen(["curl", "--silent", "ident.me"], stdout=PIPE)
    (out, err) = child.communicate()
    
    if err:
        logging.error('%s\nOut: %s' % (err, out))
        return -1
    else:
        return out.decode("utf-8")
        
def checkStatus(command):
    child = Popen(["service", command, "status"], stdout=PIPE, stderr=PIPE)
    (out, err) = child.communicate()
        
    if err:
        logging.error('%s\nOut: %s' % (err, out))
        return -1
    else:
        if 'not running' in out.decode('utf-8'):
            return 0
        else:
            return 1
                
def openvpnService(state):
    currentStatus = checkStatus('openvpn')
    
    if currentStatus == 1 and state == 'start':
        logging.info('openvpn is already running')
        return 1
    elif currentStatus == 0 and state == 'stop':
        logging.info('openvpn is already stopped')
        return 1
    
    IPBefore = getPublicIP()
    
    child = Popen(["service", "openvpn", state], stdout=PIPE, stderr=PIPE)
    (out, err) = child.communicate()
    
    IPAfter = getPublicIP()
    
    if numberOfTorrents() == 0 and state == 'start':
        logging.info('No torrents, not starting vpn')
        return 0
    
    if err:
        logging.error('%s\nOut: %s' % (err, out))
        return -1
    else:
        logging.info('%sed openvpn service' % state)
        
        if IPBefore == IPAfter:
            logging.warning("IP (%s) has not changed" % IPBefore)
        else:
            logging.info("%s -> %s" % (IPBefore, IPAfter))
        
        return 1
        
def transmissionService(state):
    currentStatus = checkStatus('transmission-daemon')
    
    if currentStatus == 1 and state == 'start':
        logging.info('transmission-daemon is already running')
        return 1
    elif currentStatus == 0 and state == 'stop':
        logging.info('transmission-daemon is already stopped')
        return 1
    
    child = Popen(["service", "transmission-daemon", state], stdout=PIPE, stderr=PIPE)
    (out, err) = child.communicate()
    
    if err:
        logging.error('%s\nOut: %s' % (err, out))
        return -1
    else:
        logging.info('%sed transmission-daemon service' % state)
        return 1

def saveStats():
    today = datetime.datetime.now()
    if today.day == 1 and today.hour == 0 and today.minute == 0:
        logging.info('Saving copy as %s' % str(today))
        try:
            f = open('/var/lib/transmission-daemon/info/stats.prev.json', 'w')
            stats = getTorrentStats()
            json.dump(stats, f)
            logging.info('Success!')
        except Exception as err:
            logging.error("Error: %s" %err)
        
        
def compareStats():
    prevStats = getTorrentStats("/var/lib/transmission-daemon/info/stats.prev.json")
    stats = getTorrentStats()
    
    if not prevStats:
        return int(stats["downloaded-bytes"]) / 1073741824
    else:
        return (int(stats["downloaded-bytes"]) - int(prevStats["downloaded-bytes"])) / 1073741824
       
def numberOfTorrents(path='/mnt/media/downloads/incomplete/'):
    child1 = Popen(['ls', path], stdout=PIPE)
    child2 = Popen(['wc', '-l'], stdin=child1.stdout, stdout=PIPE)
    
    (out, err) = child2.communicate()
            
    if err:
        logging.error('%s\nOut: %s' % (err, out))
        return -1
    else:
        total = int(out[:-1].decode('utf-8'))
        
        if int(total) == 0:
            return 0
        else:
            return 1
        
def checkCap():
    downloadSinceMonthStart = compareStats()
    logging.info("Downloaded %.2f GB since month start" % downloadSinceMonthStart)
    if downloadSinceMonthStart > DOWNLOAD_CAP:
        logging.warning("Downloaded %.2f GB over %.2f GB cap" % (downloadSinceMonthStart - DOWNLOAD_CAP, DOWNLOAD_CAP))
        logging.info("Stopping transmission service")
        transmissionService("stop")
        logging.info("Stopping openvpn service")
        openvpnService("stop")
    else:
        logging.info("Under %i GB cap" % DOWNLOAD_CAP)
        checkTorrents()
        logging.info("Starting transmission service")
        transmissionService("start")
        
def checkTorrents():
    if numberOfTorrents() == 0:
        logging.info('No torrents, stopping openvpn')
        openvpnService('stop')
    else:
        logging.info('Still torrents, starting openvpn')
        openvpnService('start')
        
if __name__ == "__main__":
    saveStats()
    checkCap()
    console.log('bye')
