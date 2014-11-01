#! /usr/bin/env python3

from subprocess import Popen, PIPE
import smtplib
from email.mime.text import MIMEText
import logging
import sqlite3
import datetime

"""
 Varible setup
"""
FROM_ADDRESS = "me@example"
EMAIL_PASSWORD = "password"
TO_ADDRESS   = ["me@example.com"]

DB_DATABASE = "system_monitoring"

ALERT_SUBJECT = 'System monitoring alerts' 
ALERT_HEADER_NETWORKING = "## Networking\n"
ALERT_BODY = '# Server Status\n\n'

SERVERS = {
    "8.8.8.8"               : "Network", # Check network is working
    "google.com"            : "DNS" # Check DNS is working
}

# FLAGS
ALERT = False

"""
 Logging setup
"""
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S',
                    filename='/var/log/system-monitor/server_alerts.log',
                    level=logging.DEBUG
                    )


def canAlert(cursor, alert_name):
    sql = "SELECT alert_date, alert_frequency FROM last_alert WHERE alert_name =\"%s\"" % alert_name
    try:
        cursor.execute(sql)
        (alert_date, alert_frequency) = cursor.fetchone()        
        
        if not alert_date: # If date NULL
            return True
        
        now = datetime.datetime.now()
        alert_frequency = datetime.timedelta(hours=alert_frequency)
        alert_date = datetime.datetime.strptime(alert_date, '%Y-%m-%d %H:%M:%S')
        alert_from = alert_date + alert_frequency
        
        if now > alert_from:
            return True
        else:
            return False
        
    except Exception as err:
        logging.error('Calculating next alert time FAILED - %s' % err)
    
    return False
    
def updateAlertDate(db, cursor, alert_name):
    sql = "UPDATE last_alert SET alert_date=DATETIME() WHERE alert_name = \"%s\"" % alert_name
    
    try:
        cursor.execute(sql)
        db.commit()    
    except Exception as err:
        logging.error('Updating alert date FAILED - %s' % err)
        db.rollback()    

def checkHost(host, name):
    child = Popen(["ping", "-c 4", "-t 20", host], stdout=PIPE)
    (out, err) = child.communicate()
    logging.info('Pinging %s - %s' % (host, name))
    if err:
        logging.error('%s\nOut: %s' % (err, out))
        return -1
    elif child.returncode == 0:
        logging.info('Host is up - %s' % name)
        return 0
    else:
        logging.warning('Host is down - %s' % name)
        # Group messages into a single alert
        return 1

def formMessage(subject, body):
    logging.info('Forming message with subject: %s and body:\n%s' % (subject, body))

    msg = MIMEText(body)
    msg['From'] = FROM_ADDRESS
    msg['To'] = TO_ADDRESS[0]
    msg['Subject'] = subject
    
    return msg
        
def sendAlert(msg):
    logging.info('Sending message\n%s%s\n%s' % ('-'*80, msg.as_string(), '-'*80))
    
    try:
        logging.info('Conecting to smtp server...')
        server = smtplib.SMTP('smtp.gmail.com', 587)
        logging.info('Success')
        server.ehlo()
        server.starttls()
        logging.info('Logging into smtp server...')
        server.login(FROM_ADDRESS, EMAIL_PASSWORD)
        logging.info('Success')
        logging.info('Sending message...')
        server.sendmail(FROM_ADDRESS, TO_ADDRESS, msg.as_string())
        logging.info('Success')
        server.close()
    except Exception as err:
        logging.error('Could not send email - ' + str(err))
    

if __name__ == "__main__":
    
    """
     Database setup
    """
    try:
        db = sqlite3.connect(DB_DATABASE)
        cursor = db.cursor()
    except Exception as err:
        logging.error('Error connecting to db - %s' % err)


    ALERT_BODY += ALERT_HEADER_NETWORKING
    for host, name in SERVERS.items():
        if checkHost(host, name) == 1:
            ALERT = True
            ALERT_BODY += "  - %s (%s) is DOWN\n" % (name, host)
    
    if ALERT and canAlert(cursor, "network_status"):
        msg = formMessage(ALERT_SUBJECT, ALERT_BODY)
        sendAlert(msg)
        updateAlertDate(db, cursor, "network_status")
    elif ALERT:
        logging.info('Alerts not sent as within frequency limit')
    else:
        logging.info('No alerts to send')
        
    try:    
        db.close()
    except Exception as err:
        logging.error('Error closing db - %s' % err)
        
    logging.info('Bye')
