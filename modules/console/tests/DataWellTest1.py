# Simple HTTP example
#
# A simple example using the HTTP plugin that shows the retrieval of a
# single page via HTTP. The resulting page is written to a file.
#
# More complex HTTP scripts are best created with the TCPProxy.


from net.grinder.script.Grinder import grinder
from net.grinder.script import Test
from net.grinder.plugin.http import HTTPRequest, HTTPPluginControl
from HTTPClient import NVPair

from threading import Condition
from java.lang import System
from java.io import FileInputStream
import random

ingestCount = 0
first = 0

cv = Condition()           # Used to synchronise thread activity.

runs = 0

RETRIEVECOUNT=grinder.getProperties().getProperty('RetrieveCount')

INGEST_PROP=grinder.getProperties().getProperty('ingest_prop')

SERVER = 'http://' + grinder.getProperties().getProperty('fcrepo.targetHost')

PIDPREFIX = grinder.getProperties().getProperty('pidprefix')

log = grinder.logger.output # alias


testCycle = Test(0,"Full Cycle")

test1 = Test(1, "RetrieveDC")
test2 = Test(2, "Ingest")
test3 = Test(3, "modifyRELSEXT")
test4 = Test(4, "RetrieveRELSEXT")



utilities = HTTPPluginControl.getHTTPUtilities()
auth = utilities.basicAuthorizationHeader(grinder.getProperties().getProperty('fcrepo.userName'),grinder.getProperties().getProperty('fcrepo.password'))
contenttype = NVPair('Content-Type','text/xml')
dedupobject = FileInputStream('fcagent-file-store/current/DataWellDeDup.xml')


requestDCHTTP = test1.wrap(HTTPRequest())
ingestHTTP = test2.wrap(HTTPRequest())

requestRELSEXT = test4.wrap(HTTPRequest())


            
def establishFirstFromFedora():
    global auth
    log("establish First")
    contenttype = NVPair('Content-Type','text/xml')
    target =  SERVER + '/objects/nextPID?format=xml'

    
    result = HTTPRequest().POST(target,None,[contenttype,auth])
    text =  str(result.getText())
    log(text)
    pidstart = text.index("<pid>")
    pidend = text.index("</pid>")
    pid = text[pidstart+5:pidend]
    log(pid)
    return pid

def establishFirstFromConfig():
    global PIDPREFIX
    number = grinder.getProperties().getProperty('firstpid')
    return PIDPREFIX+number



establishFirst = establishFirstFromFedora


def ingest():
    global ingestCount
    global first
    global auth
    global ingestHTTP
    global contenttype
    
    log('doing ingest')
    dedupobject = FileInputStream('fcagent-file-store/current/DataWellDeDup.xml')
    target = SERVER + '/objects/new'
    result = ingestHTTP.POST(target,dedupobject,[contenttype,auth])
    pid = result.getText()
    log('returned pid' + pid)
    number = pid.replace(PIDPREFIX,"")
        
    cv.acquire()
    if (int(number) > int(ingestCount)):
        ingestCount = number
    cv.release()
    return number

def requestDC(number):
    log('requestDC')
    global ingestCount
    global first
    global auth
    global requestDCHTTP

       
    pids = []
    cv.acquire()
    currentMax = ingestCount
    cv.release()
    request = requestDCHTTP
    for i in range(0,int(number)) :
            
        #todo something about seed
        index = random.randint(int(first)+1,int(currentMax)-1)
        log("requesting "+ str(index) + "as nr " + str(i))
        pid = PIDPREFIX+str(index)

        target = SERVER + '/objects/' + pid + '/datastreams/DC/content'
        result = request.GET(target)
        if (result.getStatusCode() == 200):
            pids.append(pid)
            
    return pids

def modifyDefensively(targetIN,rdf,auth):
    attempts = 0
    log("modifying object defensively")
    while (attempts<5):
        result = HTTPRequest().PUT(targetIN,rdf,[auth])
        status = result.getStatusCode()
        if status >= 200 and status < 300:
            break
        else:
            log("failed attempt "+str(attempts))
            grinder.sleep(1000)
            attempts = attempts+1
            #todo sleep a while
    stats = grinder.getStatistics().getForCurrentTest()
    status = result.getStatusCode()
    if status >= 200 and status < 300:
        stats.setSuccess(True)
    else:
        log("failed to modifyDefensively, ended with status "+str(status))
        stats.setSuccess(False)

modifyDatastreamHTTP = test3.wrap(modifyDefensively)
   
def pickRandomPid(pids):
    index = random.randint(1,len(pids))
    pid = pids[index-1]
    return pid

def addRel(pids):
    global auth
    log("adding rel")

    pid = pickRandomPid(pids)
    targetOUT = SERVER + '/objects/' + pid + '/datastreams/MY-RELS-EXT/content'
    result = requestRELSEXT.GET(targetOUT,[auth])
    if (result.getStatusCode() != 200):
        #very dirty check of the object exists. I dont think we will randomly pick two nonexisting objects in a row
        pids.remove(pid)
        pid = pickRandomPid(pids)
        targetOUT = SERVER + '/objects/' + pid + '/datastreams/MY-RELS-EXT/content'
        result = requestRELSEXT.GET(targetOUT,[auth])
    
    log("adding rel to " + pid)
    targetIN = SERVER + '/objects/' + pid + '/datastreams/MY-RELS-EXT'

    rdf = str(result.getText())
    log("getting rdf result " + rdf)
    end1 = '</rdf:Description>'
    end2 = '</rdf:RDF>'
    rdf = rdf.replace(end1,"")
    rdf = rdf.replace(end2,"")
    relation = "<hasPackage rdf:resource=\"http://some.fedora.server.statsbiblioteket.dk/fedora/objects/"+pid+str(random.random())+"\" xmlns=\"http://example.org\"/>"
        
    #todo create relation
    rdf = rdf + relation
    rdf = rdf + end1 + end2
    log("new rdf "+rdf)
    modifyDatastreamHTTP(targetIN,rdf,auth)
    #this can fail to locking, make it retry until succes



        

ingestWrap = ingest #test1.wrap(ingest) #ingest requests
requestDCWrap = requestDC #test2.wrap(requestDC) #retrieve DC
addRelWrap = addRel #test3.wrap(addRel) #retrieve RELS-EXT
        
def lifeCycle():
        global ingestCount
        global first
        global RETRIEVECOUNT
        global INGEST_PROP
        global runs
        runs = int(runs) + 1
        log('started nr. '+str(runs))

        if int(ingestCount)-int(first) < int(RETRIEVECOUNT):
            log("ingestcount "+str(ingestCount)+", doing ingest")
            ingestWrap()
        else:
            log("stuff in there, retriving")
            pids = requestDCWrap(RETRIEVECOUNT)
            log("decide on ingest or rel-add")
            randomnumber = random.random()
            log("randumnumber = "+str(randomnumber))
            if float(randomnumber) > float(INGEST_PROP):
                log("add rel to existing")
                addRelWrap(pids)
            else:
                log("ingest new object")
                ingestWrap()

lifeCycleWrap = testCycle.wrap(lifeCycle)

class TestRunner:

    def __init__(self):
        global first
        log("TestRunner created")
        startingpid = grinder.getProperties().getProperty('firstpid')
        if (startingpid is not None and startingpid > 0):
            first = startingpid
        else:
            pid = establishFirst()
            number = pid.replace(PIDPREFIX,"")
            first = number
        log("found "+first+" as the first nonused pid")
        
        self.initialisationTime = System.currentTimeMillis()

        log("New thread started at time %s" %
                              self.initialisationTime)
                            
    def __call__(self):
        lifeCycleWrap()





