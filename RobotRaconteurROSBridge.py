#  RobotRaconteurROSBridge - A program to proide a bridge between ROS and Robot Raconteur(R)
#  Copyright (C) 2014 John Wason <wason@wasontech.com>
#                     Wason Technology, LLC
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>


import RobotRaconteur as RR
import rospy
import threading
import thread
import random
import sys

robotraconteurosbridge_def="""service ROSBridge
struct time
    field int32 secs
    field int32 nsecs
end struct

struct duration
    field int32 secs
    field int32 nsecs
end struct

object ROSBridgeManager
    function int32 subscribe(string topic, string msgtype)
    objref varobject{int32} subscribers
    function int32 publish(string topic, string msgtype)
    objref varobject{int32} publishers
    function int32 client(string service, string srvtype)
    objref varobject{int32} clients
    function int32 regservice(string service, string srvtype)
    objref varobject{int32} services
end object

"""


def _rr2ros_time(i):
    return rospy.Time(i.secs, i.nsecs)

def _ros2rr_time(i):
    o=RR.RobotRaconteurNode.s.NewStructure("ROSBridge.time")  # @UndefinedVariable
    o.secs=i.secs
    o.nsecs=i.nsecs
    return o

def _rr2ros_duration(i):
    return rospy.Duration(i.secs, i.nsecs)

def _ros2rr_duration(i):
    o=RR.RobotRaconteurNode.s.NewStructure("ROSBridge.duration")  # @UndefinedVariable
    o.secs=i.secs
    o.nsecs=i.nsecs
    return o

class MsgAdapter(object):
    def __init__(self,msgname,rrmsgname,rrtopicname,rr2ros,ros2rr,rosmsgtype):
        self.msgname=msgname
        self.rrmsgname=rrmsgname
        self.rrtopicname=rrtopicname
        self.rr2ros=rr2ros
        self.ros2rr=ros2rr
        self.rosmsgtype=rosmsgtype

class SrvAdapter(object):
    def __init__(self, rossrvtype, rrservicename, reqadapter, resadapter):
        self.rossrvtype=rossrvtype
        self.rrservicename=rrservicename
        self.reqadapter=reqadapter
        self.resadapter=resadapter

class rr2ros_class(object):
    def __init__(self,func, rostype, adapters):
        self.rostype=rostype
        self.func=func
        self.adapters=adapters
        
    def __call__(self,i):
        return self.func(i,self.rostype,self.adapters)
    
class ros2rr_class(object):
    def __init__(self, func, adapters):
        self.func=func
        self.adapters=adapters
        
    def __call__(self,i):
        return self.func(i,self.adapters)
    

class ROSTypeAdapterManager(object):

    def __init__(self):
        self.rosmsgs=dict()
        self.rossrvs=dict()
        self.lock=threading.RLock()

    

    def getMsgAdapter(self, msgname):
        with self.lock:
            if (msgname in self.rosmsgs):
                return self.rosmsgs[msgname]
            
            
            
            (packagename, messagename)=msgname.split('/')
            
            rostype=__import__(packagename + '.msg',fromlist=['']).__dict__[messagename]
            
            
            slots=rostype.__slots__
            slot_types=rostype._slot_types
    
            rrtype=RR.ServiceDefinition()
            rrtypename="rosmsg_" + packagename + "__" + messagename
            rrtopicname="rostopic_" + packagename + "__" + messagename
            #print rrtypename
            #print rrtype
            rrtype.Name=rrtypename
            
            rr2ros, ros2rr=self._generateAdapters(msgname, rrtype, messagename, slot_types, slots, rostype)
            
                        
            a= MsgAdapter(msgname, rrtypename + "." + messagename, rrtopicname, rr2ros, ros2rr, rostype)
            self.rosmsgs[msgname]=a
            
            #print rrtype.ToString()

            RR.RobotRaconteurNode.s.RegisterServiceType(rrtype.ToString())  # @UndefinedVariable
            
                        
            
            
            topic="service " +  "rostopic_" + packagename + "__" + messagename + "\n\n"
            #topic+="import ROSBridge\n"
            topic+="import " + rrtypename + "\n\n"
            topic+="object subscriber\n"
            topic+="\tpipe " + rrtypename + "." + messagename + " subscriberpipe\n"
            topic+="\twire " + rrtypename + "." + messagename + " subscriberwire\n"
            topic+="\tfunction void unsubscribe()\n"
            topic+="end object\n"
            topic+="\n"
            topic+="object publisher\n"
            topic+="\tfunction void publish(" + rrtypename + "." + messagename + " m)\n"
            topic+="end object\n"
            
            #print topic
            
            
            RR.RobotRaconteurNode.s.RegisterServiceType(topic)  # @UndefinedVariable
            
            return a
    
    
    def getSrvAdapter(self, srvname):
        with self.lock:
            if (srvname in self.rossrvs):
                return self.rossrvs[srvname]
            
            (packagename, servicename)=srvname.split('/')
            
            rostype=__import__(packagename + '.srv',fromlist=['']).__dict__[servicename]
            rosreqtype=__import__(packagename + '.srv',fromlist=['']).__dict__[servicename+ "Request"]
            rosrestype=__import__(packagename + '.srv',fromlist=['']).__dict__[servicename+ "Response"]
            
            rrtype=RR.ServiceDefinition()
            rrtypename="rosservice_" + packagename + "__" + servicename
            rrtype.Name=rrtypename
            
            
            #Generate the request adapter
            rr2ros_req, ros2rr_req=self._generateAdapters(srvname, rrtype, servicename+"Request", rosreqtype._slot_types, rosreqtype.__slots__, rosreqtype)
            reqadapter= MsgAdapter(srvname, rrtypename + "." + servicename+"Request", "", rr2ros_req, ros2rr_req, rosreqtype)
            
            #Generate the response adapter
            rr2ros_res, ros2rr_res=self._generateAdapters(srvname, rrtype, servicename+"Response", rosrestype._slot_types, rosrestype.__slots__, rosrestype)
            resadapter= MsgAdapter(srvname, rrtypename + "." + servicename+"Response", "", rr2ros_res, ros2rr_res, rosrestype)
            
            a=SrvAdapter(rostype, rrtypename, reqadapter, resadapter)
            
            self.rossrvs[srvname]=a
            
            clientstr="object rosclient\n"
            clientstr+="function " + servicename + "Response call(" + servicename +"Request request)\n"
            clientstr+="end object\n"
            clientobj=RR.ServiceEntryDefinition(rrtype)
            clientobj.FromString(clientstr)
            
            servicestr="object rosservice\n"
            servicestr+="callback " + servicename + "Response servicefunction(" + servicename +"Request request)\n"
            servicestr+="end object\n"
            serviceobj=RR.ServiceEntryDefinition(rrtype)
            serviceobj.FromString(servicestr)
            
            rrtype.Objects.append(clientobj)
            rrtype.Objects.append(serviceobj)
            
            #print rrtype.ToString()
            
            RR.RobotRaconteurNode.s.RegisterServiceType(rrtype.ToString())
            
            return a
            
            
    def _generateAdapters(self,rostype,rrtype,messagename,slot_types,slots,rosmsgtype):
        
        __primtypes__=["int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64", "float32", "float64", "bool" ]
        
        rrtype_entry=RR.ServiceEntryDefinition(rrtype)
        rrtype_entry.Name=messagename
        rrtype_entry.IsStructure=True
        
        
        rrtype.Structures.append(rrtype_entry)
        
        rr2ros_str="def rr2ros(i, rostype, adapters):\n\to=rostype()\n"
        ros2rr_str="def ros2rr(i, adapters):\n\to=RR.RobotRaconteurNode.s.NewStructure('" + rrtype.Name + "." + messagename+ "')\n"
        
        adapters=dict()
        
        for i in xrange(len(slots)):
            slot_type=slot_types[i]
            isarray=False
            arrlength=0
            arrfixed=False
            if ('[' in slot_type):
                isarray=True
                (slot_type,a)=slot_type.split('[')
                a=a.rstrip(']').strip()
                if (len(a)!=0):
                    arrfixed=True
                    arrlength=int(a)
                       
            if (slot_type in __primtypes__):
                slot_type2=slot_type
                if (slot_type=='float32'): slot_type2='single'
                if (slot_type=='float64'): slot_type2='double'
                if (slot_type=='bool'): slot_type2='uint8'
                
                t=RR.TypeDefinition()
                t.Name=slots[i]
                t.Type=RR.TypeDefinition.DataTypeFromString(slot_type2)
                t.IsArray=isarray
                t.Length=arrlength
                t.VarLength=not arrfixed
                
                field=RR.PropertyDefinition(rrtype_entry)
                field.Name=slots[i]
                field.Type=t
                
                t.SetMember(field)
                
                rrtype_entry.Members.append(field)
                
                if (isarray and arrfixed):
                    rr2ros_str+="\tif (len(i." + slots[i] + ")!=" + str(arrlength) + "): raise Exception('Invalid length')\n"
                    ros2rr_str+="\tif (len(i." + slots[i] + ")!=" + str(arrlength) + "): raise Exception('Invalid length')\n"
                if (not ((slot_type=='int8' or slot_type=='uint8') and isarray)):
                    rr2ros_str+="\to." + slots[i] + "=i." + slots[i] + "\n"
                    ros2rr_str+="\to." + slots[i] + "=i." + slots[i] + "\n"
                else:
                    rr2ros_str+="\to." + slots[i] + "=i." + slots[i] + "\n"
                    ros2rr_str+="\to." + slots[i] + "=bytearray(i." + slots[i] + ")\n"
            
            
            
            elif (slot_type=='string'):
                t=RR.TypeDefinition()
                t.Name=slots[i]
                t.Type=RR.DataTypes_string_t
                t.IsList=isarray
                if (isarray):
                    
                    t.Length=arrlength
                    t.VarLength=not arrfixed
                
                field=RR.PropertyDefinition(rrtype_entry)
                field.Name=slots[i]
                field.Type=t
                
                t.SetMember(field)
                
                rrtype_entry.Members.append(field)
                
                if (isarray and arrfixed):
                    rr2ros_str+="\tif (len(i." + slots[i] + ")!=" + str(arrlength) + "): raise Exception('Invalid length')\n"
                    ros2rr_str+="\tif (len(i." + slots[i] + ")!=" + str(arrlength) + "): raise Exception('Invalid length')\n"
                if (not isarray):
                    rr2ros_str+="\to." + slots[i] + "=i." + slots[i] + "\n"
                    ros2rr_str+="\to." + slots[i] + "=i." + slots[i] + "\n"
                else:
                    rr2ros_str+="\to." + slots[i] + "=(i." + slots[i] + ")\n"
                    ros2rr_str+="\to." + slots[i] + "=(i." + slots[i] + ")\n"
            
            elif (slot_type=='time' or slot_type=='duration'):
                if (not 'RobotRaconteurROSBridge' in rrtype.Imports): 
                    rrtype.Imports.append('ROSBridge')
                t=RR.TypeDefinition()
                t.Name=slots[i]
                t.Type=RR.DataTypes_structure_t
                if (slot_type=='time'): t.TypeString='ROSBridge.time'
                if (slot_type=='duration'): t.TypeString='ROSBridge.duration'
                t.IsList=isarray
                if (isarray):
                    
                    t.Length=arrlength
                    t.VarLength=not arrfixed
                
                field=RR.PropertyDefinition(rrtype_entry)
                field.Name=slots[i]
                field.Type=t
                
                t.SetMember(field)
                
                rrtype_entry.Members.append(field)
            
                if (isarray and arrfixed):
                    rr2ros_str+="\tif (len(i." + slots[i] + ")!=" + str(arrlength) + "): raise Exception('Invalid length')\n"
                    ros2rr_str+="\tif (len(i." + slots[i] + ")!=" + str(arrlength) + "): raise Exception('Invalid length')\n"
                if (slot_type=='time'):
                    if (not isarray):
                        rr2ros_str+="\to." + slots[i] + "=_rr2ros_time(i." + slots[i] + ")\n"
                        ros2rr_str+="\to." + slots[i] + "=_ros2rr_time(i." + slots[i] + ")\n"
                    else:
                        rr2ros_str+="\to." + slots[i] + "=(i." + slots[i] + ",_rr2ros_time)\n"
                        ros2rr_str+="\to." + slots[i] + "=(i." + slots[i] + ",_ros2rr_time)\n"
            
                if (slot_type=='duration'):
                    if (not isarray):
                        rr2ros_str+="\to." + slots[i] + "=_rr2ros_duration(i." + slots[i] + ")\n"
                        ros2rr_str+="\to." + slots[i] + "=_ros2rr_duration(i." + slots[i] + ")\n"
                    else:
                        rr2ros_str+="\to." + slots[i] + "=(i." + slots[i] + ",_rr2ros_duration)\n"
                        ros2rr_str+="\to." + slots[i] + "=(i." + slots[i] + ",_ros2rr_duration)\n"
            
            elif ('/' in slot_type):
                
                if (not slot_type in adapters):
                    adapters[slot_type]=self.getMsgAdapter(slot_type)
                
                (ipackage, imessage)=slot_type.split('/')
                
                rripackagename="rosmsg_" + ipackage + "__" + imessage
                if (not rripackagename in rrtype.Imports): 
                    rrtype.Imports.append(rripackagename)
                t=RR.TypeDefinition()
                t.Name=slots[i]
                t.Type=RR.DataTypes_structure_t
                t.TypeString=rripackagename + "." + imessage
                t.IsList=isarray
                if (isarray):
                    
                    t.Length=arrlength
                    t.VarLength=not arrfixed
                
                field=RR.PropertyDefinition(rrtype_entry)
                field.Name=slots[i]
                field.Type=t
                
                t.SetMember(field)
                
                rrtype_entry.Members.append(field)
                
                if (isarray and arrfixed):
                    rr2ros_str+="\tif (len(i." + slots[i] + ")!=" + str(arrlength) + "): raise Exception('Invalid length')\n"
                    ros2rr_str+="\tif (len(i." + slots[i] + ")!=" + str(arrlength) + "): raise Exception('Invalid length')\n"
                if (not isarray):
                    rr2ros_str+="\to." + slots[i] + "=adapters['"+ slot_type +"'].rr2ros(i." + slots[i] + ")\n"
                    ros2rr_str+="\to." + slots[i] + "=adapters['"+ slot_type +"'].ros2rr(i." + slots[i] + ")\n"
                else:
                    rr2ros_str+="\to." + slots[i] + "=[adapters['"+ slot_type +"'].rr2ros(d) for d in (i." + slots[i] + ")]\n"
                    ros2rr_str+="\to." + slots[i] + "=[adapters['"+ slot_type +"'].ros2rr(d) for d in (i." + slots[i] + ")]\n"
            
            else:
                raise Exception("Cannot convert message type " + rostype._type)
        
        rr2ros_str+="\treturn o"
        ros2rr_str+="\treturn o"
        
        exec(rr2ros_str)
        exec(ros2rr_str)
        
        #print rr2ros_str
        #print ros2rr_str
        
        return rr2ros_class(rr2ros,rosmsgtype,adapters), ros2rr_class(ros2rr,adapters)  # @UndefinedVariable
        

class ROSBridgeManager(object):
    
    def __init__(self):
        self._subscribers=dict()
        self._publishers=dict()
        self._clients=dict()
        self._services=dict()
        self.adapterManager=ROSTypeAdapterManager()
    
    def subscribe(self,topic, msgtype):
        #print topic
        #print msgtype
        adapter=self.adapterManager.getMsgAdapter(str(msgtype))
        s=subscriber(str(topic),adapter)
        
        handle=random.randint(1,2**30)
        if (handle in self._subscribers):
            handle=random.randint(1,2**30)
        self._subscribers[handle]=s
        
        return handle
    
    def publish(self,topic, msgtype):
        #print topic
        #print msgtype
        adapter=self.adapterManager.getMsgAdapter(str(msgtype))
        s=publisher(str(topic),adapter)
        
        handle=random.randint(1,2**30)
        if (handle in self._subscribers):
            handle=random.randint(1,2**30)
        self._publishers[handle]=s
        
        return handle
    
    def client(self, service, srvtype):
        adapter=self.adapterManager.getSrvAdapter(str(srvtype))
        c=client(str(service), adapter)
        
        handle=random.randint(1,2**30)
        if (handle in self._subscribers):
            handle=random.randint(1,2**30)
        self._clients[handle]=c
        
        return handle
    
    def regservice(self, service_, srvtype):
        adapter=self.adapterManager.getSrvAdapter(str(srvtype))
        c=service(str(service_), adapter)
        
        handle=random.randint(1,2**30)
        if (handle in self._subscribers):
            handle=random.randint(1,2**30)
        self._services[handle]=c
        
        return handle
    
    def get_subscribers(self,handle):
        s=self._subscribers[int(handle)]
        return s, s.rrtype
    
    def get_publishers(self,handle):
        s=self._publishers[int(handle)]
        return s, s.rrtype

    def get_clients(self,handle):
        s=self._clients[int(handle)]
        return s, s.rrtype

    def get_services(self,handle):
        s=self._services[int(handle)]
        return s, s.rrtype

class subscriber(object):
    def __init__(self, topic, msgadapter):
                
        self.topic=topic
        self.msgadapter=msgadapter
        self.wires=dict()
        self.pipes=dict()
        self.rrtype=msgadapter.rrtopicname + ".subscriber"
        self._subscriberwire=None
        self._subscriberpipe=None
        self._connected_wires=dict()
        self._connected_pipes=dict()
        self._calllock=threading.RLock()
        
        rospy.Subscriber(topic, msgadapter.rosmsgtype, self.callback)
        
    def callback(self, data):
        rrmsg=self.msgadapter.ros2rr(data)
        
        with self._calllock:
            for k in list(self._connected_wires.keys()):
                try:
                    w=self._connected_wires[k]
                    w.OutValue=rrmsg
                except:
                    
                    try:
                        del self._connected_wires[k]
                    except: pass
                    def wclose():
                        try:
                            w.Close()
                        except:
                            pass
                    thread.start_new_thread(wclose,())
            for k in list(self._connected_pipes.keys()):
                try:
                    p=self._connected_pipes[k]
                    p.SendPacket(rrmsg)
                except:
                    try: 
                        del self._connected_pipes[k] 
                    except: pass
                    def pclose():
                        try:
                            p.Close()
                        except:
                            pass
                    thread.start_new_thread(pclose,())
        
        #print rrmsg
    
    @property
    def subscriberwire(self):
        return self._subscriberwire
    @subscriberwire.setter
    def subscriberwire(self,value):
        self._subscriberwire=value
        value.WireConnectCallback=self._wire_connected
    
    def _wire_connected(self,wire):
        with self._calllock:
            self._connected_wires[wire.Endpoint]=wire
            wire.WireConnectionClosedCallback=self._wire_closed
            
    def _wire_closed(self,wire):
        with self._calllock:
            try:
                del self._connected_wires[wire.Endpoint]
            except:
                pass
                
    
    @property
    def subscriberpipe(self):
        return self._subscriberpipe
    @subscriberpipe.setter
    def subscriberpipe(self,value):
        self._subscriberpipe=value
        value.PipeConnectCallback=self._pipe_connected
    
    def _pipe_connected(self,pipe):
        with self._calllock:
            self._connected_pipes[(pipe.Endpoint,pipe.Index)]=pipe
            pipe.PipeEndpointClosedCallback=self._pipe_closed
    
    def _pipe_closed(self,pipe):
        with self._calllock:
            try:
                del self._connected_pipes[(pipe.Endpoint,pipe.Index)]
            except:
                pass
    
    def unsubscribe(self):
        pass

class publisher(object):
    def __init__(self, topic, msgadapter):
        
        self.topic=topic
        self.msgadapter=msgadapter
        self.rrtype=msgadapter.rrtopicname + ".publisher"
        self._calllock=threading.RLock()
        
        self.pub=rospy.Publisher(topic,msgadapter.rosmsgtype)

    def publish(self, rrmsg):
        with self._calllock:
            msg=self.msgadapter.rr2ros(rrmsg)
            self.pub.publish(msg)
        
class client(object):
    def __init__(self, service, srvadapter):
        
        self.service=service
        self.srvadapter=srvadapter
        self.rrtype=srvadapter.rrservicename + ".rosclient"
        self._calllock=threading.RLock()
        
        self.rosproxy=rospy.ServiceProxy(service,srvadapter.rossrvtype)

    def call(self, rrreq):
        with self._calllock:
            req=self.srvadapter.reqadapter.rr2ros(rrreq)
            res=self.rosproxy(req)
            return self.srvadapter.resadapter.ros2rr(res)

class service(object):
    def __init__(self, service, srvadapter):
        
        self.service=service
        self.srvadapter=srvadapter
        self.rrtype=srvadapter.rrservicename + ".rosservice"
        self._calllock=threading.RLock()
        
        self.rosproxy=rospy.Service(service,srvadapter.rossrvtype,self.call)
        self.endpoint=RR.ServerEndpoint.GetCurrentEndpoint()

    def call(self, req):
        with self._calllock:
            rrreq=self.srvadapter.reqadapter.ros2rr(req)
            rrres=self.servicefunction.GetClientFunction(self.endpoint)(rrreq)
            return self.srvadapter.resadapter.rr2ros(rrres)
        
        


def main():
    
    RR.RobotRaconteurNode.s.RegisterServiceType(robotraconteurosbridge_def)  # @UndefinedVariable
    
    if (len(sys.argv) > 1):
        if (sys.argv[1]=='msg'):
            a=ROSTypeAdapterManager()
            a.getMsgAdapter(sys.argv[2])
            rrtype=RR.RobotRaconteurNode.s.GetRegisteredServiceTypes()
            for t in rrtype:
                if (t!='RobotRaconteurServiceIndex'):
                    t1=RR.RobotRaconteurNode.s.GetServiceType(t)
                    dat=t1.ToString()
                    f = open(t+".robdef", "w")
                    f.write(dat)
                    f.close()
                
            
            return
        if (sys.argv[1]=='srv'):
            a=ROSTypeAdapterManager()
            a.getSrvAdapter(sys.argv[2])
            rrtype=RR.RobotRaconteurNode.s.GetRegisteredServiceTypes()
            for t in rrtype:
                if (t!='RobotRaconteurServiceIndex'):
                    t1=RR.RobotRaconteurNode.s.GetServiceType(t)
                    dat=t1.ToString()
                    f = open(t+".robdef", "w")
                    f.write(dat)
                    f.close()
            return
        
        print "Invalid command for RobotRaconteurROSBridge\n"
        return
    
    
    rospy.init_node("RobotRaconteurROSBridge")
    
    t=RR.TcpTransport()
    t.StartServer(34572)
    RR.RobotRaconteurNode.s.RegisterTransport(t)  # @UndefinedVariable
    
    
    
    
    o=ROSBridgeManager()
    RR.RobotRaconteurNode.s.RegisterService("ROSBridge","ROSBridge.ROSBridgeManager",o)  # @UndefinedVariable
    
    
    #a=ROSTypeAdapterManager()
    
    
    #a.getMsgAdapter('turtlesim/Pose')
   # a.getMsgAdapter('turtlesim/Pose')
    #a.getMsgAdapter('beginner_tutorials/mymsg2')


    raw_input('Press enter to quit')
    
    RR.RobotRaconteurNode.s.Shutdown()  # @UndefinedVariable

if __name__ == '__main__':
    main()
