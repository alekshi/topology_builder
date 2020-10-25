# Topology builder
The script is proposed to deploy a network topology drawn in [draw.io](https://app.diagrams.net/) using containerized [FRR](https://frrouting.org/) as routers. The script uses [Docker file](https://github.com/alekshi/topology_builder/blob/master/frr/Dockerfile) creates docker-compose file and container configuration file (frr/docker-start). 

## Draw.io diagram defenitions
A mapping between draw.io and docker objects is depicted on the figure below:
![image](https://github.com/alekshi/topology_builder/blob/master/diagram-definition.png "Mapping between draw.io and docker")
You can use any shapes for router and broadcast networks. IPv4 subnets are supported right now only. You can use prefix length <= /29 since docker host use one address from each subnet.

## How to use
1. Clone the repo
```
git clone https://github.com/alekshi/topology_builder.git
cd topology_builder/
```
2. Draw a network diagram using [draw.io](https://app.diagrams.net/) and export to xml (without compressing)
3. To use MPLS with Linux kernel, load additional modules:
```  
   modprobe mpls_router
   modprobe mpls_gso
   modprobe mpls_iptunnel
 ```
4. Lanuch [topology_builder.py](https://github.com/alekshi/topology_builder/blob/master/topology_builder.py) to create docker-compose file and frr/docker-start file
``` 
./topology_builder.py -f <XML topology file path>
``` 
Default settings include:
*Ellipse as router
*Rectangle as broadcast network
*All FRR daemons are enable
*MPLS is disable
Use ``` --help ```  to see all options
5. Launch docker-compose file to create topology
``` 
docker-compose up -d
``` 
6. Check ports what are exposed for ssh connection using ```docker container ls```  By default 2000+ ports are used for ssh and root/root credentials. 
