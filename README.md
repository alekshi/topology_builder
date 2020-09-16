# topology_builder
A script to deploy containerized FRR based on draw.io topology.

How to use
0. Clone the repo
1. Draw a network a diagram using draw.io. Use ellipse to draw a router, line to draw a link;
2. Double click on ellipse to add router name. Double on link to add network address (d.d.d.d/dd);
3. Save the network diagram as XML and put to a dir where the repo was cloned to;
4. Launch topology_builder.py as:
      topology_builder.py <diagram.xml>
5. docker-compose file will be created
6. Load MPLS kernel module:
   modprobe mpls_router
   modprobe mpls_gso
   modprobe mpls_iptunnel
6. Launch the docker-compose file to create FRR topology that was depicted in draw.io file

