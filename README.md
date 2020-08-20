---
### FOR SUPPORT, DISCUSSION, GETTING INVOLVED ###

Please join the DVSwitch group at groups.io for online forum support, discussion, and to become part of the development team.

DVSwitch@groups.io

---

**Socket-Based Reporting for DMRlink**

## update VK2PSF (sgtsmall)
- fixes the downloads of subscriber and peers from csv to json (inline with other parts of project)

- Adds new field WEBSERVICE_PORT to config.
 This enables a port other than the default 9000 to be used for the ws. (was causing clashes in docker implementation)

- Change logging to include timestamp and add config element LOG_LEVEL
  - Can be DEBUG, INFO, ERROR    I recommend INFO

- requirements.txt now have some fixed versions (for continued operation with python2)
- needs libffi-dev libssl-dev

## INSTALL
This is still python2 version
(DEBIAN)
apt-get install -y libffi-dev libssl-dev
pip install -r requirements.txt

copy/create dmrmonitor.cfg

## USAGE

python dmrmonitor.py -l [LOG_LEVEL] -c configfile.cfg


-l overrides the LOG_LEVEL [DEBUG, INFO, ERROR] in the config file
-c override default config file (dmrmonitor.cfg)


Over the years, the biggest request recevied for DMRlink (other than call-routing/bridging tools) has been web-based diagnostics and/or statistics for the program.

I strongly disagree with including the amount of overhead this would require inside DMRlink -- which still runs nicely on very modest resources. That it does this, and is in Python is a point of pride for me... Just let me have this one, ok? What I have done is added some hooks to DMRlink, which will be expanded over time, whereby it listens on a TCP socket and provides the raw data necessary for a "web dashboard", or really any external logging or statisitcs gathering program.

DMRmonitor is my take on a "web dashboard" for DMRlink.

***THIS SOFTWARE IS VERY, VERY NEW***

Right now, I'm just getting into how this should work, what does work well, what does not... and I am NOT a web applications programmer, so yeah, that javascript stuff is gonna look bad. Know what you're doing? Help me!

It has now reached a point where folks who know what they're doing can probably make it work reasonably well, so I'm opening up the project to the public.

***GOALS OF THE PROJECT***

Some things I'm going to stick to pretty closely. Here they are:

+ DMRmonitor be one process that includes a webserver
+ Websockets are used for pushing data to the browser - no long-polling, etc.
+ Does not provide data that's easily misunderstood
+ Incorporates RCM with with repeaters to display their state


# testing
 docker run -it -p 80:8085 -p 9005:9005 -v /Users/AlexS/Github/DMRmonitor:/opt/dmrlink/DMRmonitor -v ~/etc/timezone:/etc/localtime:ro --entrypoint /bin/sh dmrhblinkpy2:latest


***0x49 DE N0MJS***

Copyright (C) 2013-2017  Cortney T. Buffington, N0MJS <n0mjs@me.com>

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
