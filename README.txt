-------------------------------------------------------------------------------
RobotRaconteurROSBridge
-------------------------------------------------------------------------------
Version 0.1.2
Release date: 4/2/2014
-------------------------------------------------------------------------------
Project state:
 expermental 
-------------------------------------------------------------------------------
Credits
	John Wason (wason@wasontech.com)
-------------------------------------------------------------------------------
Project description

RobotRaconteurROSBridge allows ROS topics and services to be provided
and consumed through Robot Raconteur(R)
-------------------------------------------------------------------------------
Dependencies:

RobotRaconteurROSBridge requires a ROS installation, Python 2.7, and the
Robot Raconteur(R) Python runtime which can be found at http://robotraconteur.com .

-------------------------------------------------------------------------------
Documentation

To start RobotRaconteurROSNode, start 'roscore' and a terminal with the
ROS environment activated.  All msg and srv that are to be used with 
the bridge must be generated using catkin_ws so that the Python
serialization implementation is available.  If you have listed your
msg and srv files in CMakeLists.txt in your catkin build this should
already be done.

To start, run:

>>> python RobotRaconteurROSBridge.py

The following Robot Raconteur(TM) url can be used to connect to the bridge:

'tcp://localhost:34572/{0}/ROSBridge'

The returned object is a manager that can be used to subscribe to a topic,
publish a topic, call a service, or provide a service. See the examples
of how to use the bridge.

Messages and services are converted to a corresponding Robot
Raconteur(R) types.  For messages, these types are:

rosmsg_<package>__<messagename>
rostopic_<package>__<messagename>

For services, the following are generated:

rosservice_<package>__<servicename>

The *.robdef files can be retrieved from the command line:

>>> python RobotRaconteurROSBridge.py msg <messagetype>
>>> python RobotRaconteurROSBridge.py srv <servicetype>

When using Python it is not necessary to generate out these
*.robdef files, however it is helpful for reference.  Other
 languages may need these files for use with RobotRaconteurGen
 
 When using ROS arrays of type 'string', 'time', 'duration', or
 another message type, Robot Raconteur(R) 'list' types are used.
 This is because Robot Raconteur(R) arrays are only used
 for primitive numeric arrays that are contiguous in memory.
 
 This file has only been tested on Ubuntu 12.04 but should
 run on any other platform with ROS, Python, and Robot Raconteur(R).

