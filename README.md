# topology_builder
The script is proposed to deploy a network topology drawn in [draw.io](https://app.diagrams.net/) using containerized [FRR](https://frrouting.org/) as routers. The script uses [Docker file](https://github.com/alekshi/topology_builder/blob/master/frr/Dockerfile) creates docker-compose file and container configuration file (frr/docker-start). 

##Draw.io diagram defenitions
A mapping between draw.io and docker objects is depicted on the figure below:
![image](https://github.com/alekshi/topology_builder/blob/master/diagram-definition.png "Mapping between draw.io and docker")

How to use:

0. Clone the repo
1. Draw a network a diagram using draw.io. Use ellipse to draw a router, line to draw a link;
2. Double click on ellipse to add router name. Double on link to add network address (d.d.d.d/dd);
3. Save the network diagram as XML and put to a dir where the repo was cloned to;
4. Launch topology_builder.py as:
      topology_builder.py -f <diagram.xml>
5. docker-compose file will be created
6. Load MPLS kernel module (optionally, if MPLS used):
   modprobe mpls_router;
   modprobe mpls_gso;
   modprobe mpls_iptunnel
6. Launch the docker-compose file to create FRR topology that was depicted in draw.io file

