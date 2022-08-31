import xml.etree.ElementTree as ET
import re
import sys
import ipaddress
import yaml
import argparse
import os
import shutil

class TheScript():
	def __init__(self):
		self.mxcell_list = list()
		self.router_list = list()
		self.link_list = list()
		self.network_list = list()
		self.frr_daemons = ('bgpd',
							'ospfd',
							'ospf6d',
							'ripd',
							'ripngd',
							'isisd',
							'pimd',
							'ldpd',
							'nhrpd',
							'eigrpd',
							'babeld',
							'sharpd',
							'pbrd',
							'bfdd',
							'fabricd'
							)
		self.shape_type = {'ellipse': '^ellipse;.+?$', 
				   		   'rectangle': '^(?!.*(hexagon|ellipse|triangle|rhombus)).+?$', 
				   		   'triangle': '^triangle;.+?$',
				   		   'hexagon': '^shape=hexagon;.+?$'
				   		  }

	def parsing_arguments(self):
		parser = argparse.ArgumentParser()
		parser.add_argument("-f", "--file", required=True, help="draw.io XML topology file")
		parser.add_argument("-d", "--dir", default=None, help="Directory to put final docker-compose.yml file (current dir by default)")
		parser.add_argument("-p", "--path", default=None, help="Path to dir with Dockerfile (./frr default)")
		parser.add_argument("-m", "--mpls", action='store_true', help="Boolean. Is MPLS enabled (False by default)")
		parser.add_argument("-6", "--ipv6", action='store_true', help="Boolean. Is IPv6 (False by default)")
		parser.add_argument("-D", "--daemons", default=None, help="Daemons to enable in FRR (e.g: proto1,proto2,proto3 All daemons enabled by default)")
		parser.add_argument("-P", "--pwd", default='root', help="A password to use for a container SSH connection")
		parser.add_argument("-k", "--key", default=None, help="A public key to use for a container SSH connection")
		parser.add_argument("-r", "--router_shape", default='ellipse', help="A shape what represents router  on diagram (ellipse by default). Use: ellipse, rectangle, triangle, hexagon")
		parser.add_argument("-n", "--network_shape", default='rectangle', help="A shape what represents broadcast network on diagram (rectangle by default). Use: ellipse, rectangle, triangle, hexagon")
		args = parser.parse_args()
	
		self.topology_xml_file = args.file
		
		if args.dir:
			self.working_dir = args.dir
		else:
			self.working_dir = sys.path[0]
		
		if args.path:
			self.build_path = args.path
		else:
			self.build_path = '{}/frr'.format(self.working_dir)

		self.container_pwd = args.pwd

		if args.key:
			if os.path.exists(args.key):
				self.container_key = args.key
			else:
				self.container_key = None
		else:
			self.container_key = None
		self.is_mpls_enabled = args.mpls
		self.is_ipv6_enabled = args.ipv6

		self.daemon_list = list()
		if args.daemons:
			for daemon in args.daemons.split(','):
				if daemon in self.frr_daemons:
					self.daemon_list.append(daemon)
		else:
			self.daemon_list = self.frr_daemons
	
		self.router_shape = args.router_shape
		self.network_shape = args.network_shape
	
		if self.router_shape == self.network_shape:
			sys.stdout.write(f"Router and broadcast network should be represented by different shapes. Now they are same {router_shape}\n")
			sys.stderr.write(f"Router and broadcast network should be represented by different shapes. Now they are same {router_shape}\n")
			sys.exit(1)


	def object_list_by_name(self, object_list, name, name_type = 'name'):
		return_list = list()
		for object in object_list:
			if getattr(object, name_type):
				if re.match('^{}(-|:)\d+?$'.format(name), getattr(object, name_type)):
					return_list.append(object)
		return return_list

	def object_by_attribute(self, object_list, attribute_name, attribute_value):
		for object in object_list:
			if getattr(object, attribute_name) == attribute_value:
				return object
		return None

	def object_by_type(self, object_list, attribute_type):
		return_list = list()
		for object in object_list:
			if object.type == attribute_type:
				return_list.append(object)
		return return_list

	def parse_topology_file(self):
		tree = ET.parse(self.topology_xml_file)
		tree_root = tree.getroot()
		for cell in tree_root.iter('mxCell'):
			if 'style' in cell.attrib:
				self.mxcell_list.append(mxCell(self.shape_type, cell.attrib))
		if len(self.mxcell_list) > 0:
			for cell in self.mxcell_list:
				if len(self.object_list_by_name(self.mxcell_list, cell.value, 'value')) > 1 and not re.match('(\d{1,3}\.){3}\d{1,3}', cell.value):
					counter = 1
					for cell in self.object_list_by_name(self.mxcell_list, cell.value.lower()):
						cell.value = '{}-{}'.format(cell.value, counter)
						counter += 1
			for cell in self.mxcell_list:
				if cell.type == 'edge':
					for connection in ('source', 'target'):
						if getattr(cell, connection) is not None:
							ConnectionObject = self.object_by_attribute(self.mxcell_list, 'id', getattr(cell, connection))
							ConnectionObject.add_connection('edge', cell)
							cell.add_connection(connection, ConnectionObject)
				if cell.type == 'edgeLabel':
					ConnectionObject = self.object_by_attribute(self.mxcell_list, 'id', cell.parent)
					ConnectionObject.value = cell.value
					cell.parent = ConnectionObject
			return True
		else:
			return False
	
	def __parse_router_name(self, raw_name):
		result_dict = {'name': str(), 'vrf_list': list()}
		pattern_router_name = re.compile('^<div>(.+?)<\/div>')
		pattern_vrf_list = re.compile('VRF:\s*?\[(.+?)\]')
		router_name_result = pattern_router_name.search(raw_name)
		if router_name_result:
			result_dict['name'] = router_name_result.group(1)
			vrf_result = pattern_vrf_list.search(raw_name)
			if vrf_result:
				result_dict['vrf_list'] = vrf_result.group(1).replace(' ', '').split(',')
		else:
			result_dict['name'] = raw_name

		return result_dict

	def create_router_list(self, router_shape):
		for cell in self.object_by_type(self.mxcell_list, router_shape):
			router_name = '{}-{}'.format(self.__parse_router_name(cell.value)['name'].lower(), len(self.object_list_by_name(self.router_list, self.__parse_router_name(cell.value)['name'].lower()))+1)
			vrf_list = self.__parse_router_name(cell.value)['vrf_list']
			self.router_list.append(Router(router_name, cell, vrf_list))
		if len(self.router_list) > 0:
			return True
		else:
			return False

	def create_network_list(self, network_shape):
		for cell in self.object_by_type(self.mxcell_list, network_shape):
			net_name = 'net:{}'.format(re.sub('[,./\s]', '_', cell.value))
			self.network_list.append(Network(net_name, cell, self.is_ipv6_enabled))
			self.network_list[-1].add_subnet_to_list(cell.value)
		return True

	def create_link_list(self):	
		for cell in self.object_by_type(self.mxcell_list, 'edge'):
			connection_dict = {'source': None, 'target': None}
			for connection, name in connection_dict.items():

				try:
					connection_dict[connection] = getattr(cell, connection)
				except:
					pass
			if all(connection_dict.values()):
				if connection_dict['source'].type == self.router_shape and connection_dict['target'].type == self.router_shape:
					link_name = 'link:{}:{}'.format(self.__parse_router_name(connection_dict['source'].value)['name'], 
													self.__parse_router_name(connection_dict['target'].value)['name']).lower()
					self.link_list.append(Link('{}:{}'.format(link_name, len(self.object_list_by_name(self.link_list, link_name))+1), cell, self.is_ipv6_enabled))
					self.link_list[-1].add_subnet_to_list(cell.value)
				if connection_dict['source'].type == self.network_shape:
					net_name = 'net:{}'.format(re.sub('[,./\s]', '_', connection_dict['source'].value))
					network_object = self.object_by_attribute(self.network_list, 'name', net_name)
					if network_object:
						network_object.add_host(connection_dict['target'])
				if connection_dict['target'].type == self.network_shape:
					net_name = 'net:{}'.format(re.sub('[,./\s]', '_', connection_dict['target'].value))
					network_object = self.object_by_attribute(self.network_list, 'name', net_name)
					if network_object:
						network_object.add_host(connection_dict['source'])
			else:
				for connection, name in connection_dict.items():
					if name:
						link_name = 'link:STUB:{}'.format(name.value).lower()
						self.link_list.append(Link('{}:{}'.format(link_name, len(self.object_list_by_name(self.link_list, link_name))+1), cell, self.is_ipv6_enabled))
						self.link_list[-1].add_subnet_to_list(cell.value)


		if len(self.link_list) > 0:
			return True
		else:
			return False

	def add_links_to_routers(self):
		for router in self.router_list:
			for link in self.link_list:
				if link.mxCellObject.source == router.mxCellObject or link.mxCellObject.target == router.mxCellObject:
					router.add_link(link)
			for network in self.network_list:
				for mxCellObject in network.host_list:
					if mxCellObject == router.mxCellObject:
						router.add_link(network)


class DockerStartFile():
	def __init__(self, path, TheScriptObject):
		self.path = path
		with open('{}/docker-start'.format(self.path), 'w') as output_file:
			output_file.write('#!/bin/sh\nset -e\n')
			output_file.write("\n#Enable SSH\n")
			output_file.write("sed -i 's/#PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config\n")
			output_file.write("echo 'root:{}' | chpasswd\n".format(TheScriptObject.container_pwd))
			if TheScriptObject.container_key:
				try:
					with open(TheScriptObject.container_key, 'r') as key_file:
						key_string = key_file.read()
				except:
					key_string = str()
				if key_string:
					output_file.write("sed -i 's|#AuthorizedKeysFile.*|AuthorizedKeysFile /etc/ssh/authorized_keys|' /etc/ssh/sshd_config\n")
					output_file.write("touch /etc/ssh/authorized_keys\n")
					output_file.write("echo '{}' > /etc/ssh/authorized_keys\n".format(key_string))
			output_file.write("echo 'exec /usr/bin/vtysh' >> ~/.bashrc\n")
			output_file.write("/etc/init.d/ssh start\n")
			output_file.write("\n\n\n")
	
	def enable_daemons(self, daemon_list = list()):
		with open('{}/docker-start'.format(self.path), 'a') as output_file:
			output_file.write('#Enable daemons\n')
			for daemon in daemon_list:
				output_file.write(f'sed -i "s/{daemon}=no/{daemon}=yes/g" /etc/frr/daemons\n')
			output_file.write('chown -R frr:frr /etc/frr\n')
			output_file.write('/etc/init.d/frr start\n')
			output_file.write("\n\n\n")

	def enable_mpls(self):
		with open('{}/docker-start'.format(self.path), 'a') as output_file:
			output_file.write("#Enable MPLS\n")
			output_file.write("sysctl -w net.mpls.platform_labels=1000\n")
			output_file.write("for iface in $(ls /proc/sys/net/mpls/conf/); do sysctl -w net.mpls.conf.$iface.input=1; done\n")
			output_file.write("/etc/init.d/frr start\n")
			output_file.write("\n\n\n")
	def enable_vrf(self, vrf_list):
		index = 1
		with open('{}/docker-start'.format(self.path), 'a') as output_file:
			output_file.write("#Enable VRF\n")
			for vrf in vrf_list:
				output_file.write(f"ip link add {vrf} type vrf table {index}\n")
				output_file.write(f"ip link set dev {vrf} up\n")
				output_file.write(f"ip rule add oif {vrf} table {index}\n")
				output_file.write(f"ip rule add iif {vrf} table {index}\n")
				output_file.write(f"ip route add table {index} unreachable default metric 4278198272\n\n")
				index+=1
			output_file.write("\n\n\n")		

	def launch_continous_process(self):
		with open('{}/docker-start'.format(self.path), 'a') as output_file:
			output_file.write("#Launch continous command\n")
			output_file.write("exec sleep 10000d\n")


class mxCell():
	def __init__(self, shape_types, cell_details_dict):
		self.id = cell_details_dict['id']
		self.type = None
		if 'style'in cell_details_dict:
			for shape, pattern in shape_types.items():
				if re.match(pattern, cell_details_dict['style']):
					self.type = shape
					self.value = cell_details_dict['value']
					self.edge_list = list()
				elif re.match('edgeLabel', cell_details_dict['style']):
					self.type = 'edgeLabel'
					self.value = cell_details_dict['value']
					self.parent = cell_details_dict['parent']
				elif 'source' in cell_details_dict or 'target' in cell_details_dict:
					self.type = 'edge'
					if 'value' in cell_details_dict:
						self.value = cell_details_dict['value']
					else:
						self.value = None
					if 'source' in cell_details_dict:
						self.source = cell_details_dict['source']
					else:
						self.source = None
					if 'target' in cell_details_dict:
						self.target = cell_details_dict['target']
					else:
						self.target = None
			if not self.type:
				self.type = 'other'

	def add_connection(self, connection_type, ConnectionObject):
		if connection_type == 'source':
			self.source = ConnectionObject
		elif connection_type == 'target':
			self.target = ConnectionObject
		elif connection_type == 'edge':
			self.edge_list.append(ConnectionObject)


class NetworkObject():
	def __init__(self, name, mxCellObject):
		self.name = name
		self.mxCellObject = mxCellObject

class Router(NetworkObject):
	def __init__(self, name, mxCellObject, vrf_list = list()):
		super().__init__(name, mxCellObject)
		self.link_list = list()
		self.vrf_list = vrf_list

	def add_link(self, link):
		self.link_list.append(link)

	def prepare_yaml_dict(self, build_path, expose_ports = None, is_privileged = False):
		yaml_dict = {self.name: {
									"build": '{}/{}'.format(build_path, self.name),
									"ports": ['{}:{}'.format(ports_tuple[0], ports_tuple[1]) for ports_tuple in expose_ports],
									"privileged": is_privileged,
									"networks": [str(link.name) for link in self.link_list]
								}
					}
		return yaml_dict


class Link(NetworkObject):
	def __init__(self, name, mxCellObject, is_ipv6_enabled = False):
		super().__init__(name, mxCellObject)
		self.subnet_list = list()
		self.is_ipv6_enabled = is_ipv6_enabled

	def add_subnet_to_list(self, raw_string):
		for subnet in raw_string.replace(' ','').split(','):
			try:
				self.subnet_list.append(ipaddress.ip_network(subnet))
			except:
				self.subnet_list.append(None)
		return True

	def prepare_yaml_dict(self):
		if self.is_ipv6_enabled:
			yaml_dict = {self.name: {
										"enable_ipv6": True,
										"driver": "bridge",
										"driver_opts": {"com.docker.network.enable_ipv6": True}
									}
						}
		else:
			yaml_dict = {self.name: {
							"driver": "bridge"
									}
						}
		if self.subnet_list:
			yaml_dict[self.name]["ipam"] = {"driver": "default", 
										    "config": list()
										   }
			for subnet in self.subnet_list:
				if subnet:
					yaml_dict[self.name]["ipam"]["config"].append({'subnet': str(subnet)})
		return yaml_dict

class Network(Link):
	def __init__(self, name, mxCellObject, is_ipv6_enabled = False):
		super().__init__(name, mxCellObject, is_ipv6_enabled = False)
		self.host_list = list()
		self.is_ipv6_enabled = is_ipv6_enabled

	def add_host(self, RouterObject):
		self.host_list.append(RouterObject)
		

class DockerComposeFile():
	def __init__(self, path, build_path, start_port = 2000):
		self.start_port = start_port
		self.path = path
		self.build_path = build_path
		self.yaml_dict = {'version': '3', 'services': dict(), 'networks': dict()}

	def add_router(self, RouterObject, expose_ports = None):
		self.yaml_dict['services'].update(RouterObject.prepare_yaml_dict(self.build_path, expose_ports, True))

	def add_network(self, LinkObject):
		self.yaml_dict['networks'].update(LinkObject.prepare_yaml_dict())

	def create_yaml_dict(self, router_list, link_list, network_list):
		counter = 0
		for router in router_list:
			self.add_router(router, [(self.start_port+counter, 22)])
			counter += 1
		for link in link_list:
			self.add_network(link)
		for network in network_list:
			self.add_network(network)
	
	def write_to_file(self):
		with open('{}/docker-compose.yml'.format(self.path), 'w') as self.output_file:
			for key, value in self.yaml_dict.items():
				self.output_file.write(yaml.dump({key: value}))


def main():
	#Parsing arguments and create objects
	sys.stdout.write("Parsing arguments... ")
	TopologyBuilder = TheScript()
	TopologyBuilder.parsing_arguments()
	DockerComposeFileObject = DockerComposeFile(TopologyBuilder.working_dir, TopologyBuilder.build_path)

	sys.stdout.write("DONE\n")
	sys.stdout.write("Parsing draw.io XML file... ")
	if TopologyBuilder.parse_topology_file():
		sys.stdout.write("DONE\n")
		sys.stdout.write("Creating router list... ")
		if TopologyBuilder.create_router_list(TopologyBuilder.router_shape):
			sys.stdout.write("DONE\n")
			sys.stdout.write("Creating network list... ")
			if TopologyBuilder.create_network_list(TopologyBuilder.network_shape):
				sys.stdout.write("DONE\n")
				sys.stdout.write("Creating link list... ")	
				if TopologyBuilder.create_link_list():
					sys.stdout.write("DONE\n")
					sys.stdout.write("Creating docker compose file... ")
					TopologyBuilder.add_links_to_routers()
					DockerComposeFileObject.create_yaml_dict(TopologyBuilder.router_list, TopologyBuilder.link_list, TopologyBuilder.network_list)
					DockerComposeFileObject.write_to_file()
					sys.stdout.write("DONE\n")
				else:
					sys.stdout.write("FAILED\n")
					sys.stderr.write('Something goes wrong creating link list. Bye.\n')
					sys.exit(1)
			else:
				sys.stdout.write("FAILED\n")
				sys.stderr.write('Something goes wrong creating network list. Bye.\n')
				sys.exit(1)
		else:
			sys.stdout.write("FAILED\n")
			sys.stderr.write('Something goes wrong creating router list. Bye.\n')
			sys.exit(1)
	else:
		sys.stdout.write("FAILED\n")
		sys.stderr.write('Something goes wrong parsing draw io XML file. Bye.\n')
		sys.exit(1)

	sys.stdout.write("Creating container configuration files.. ")

	for router in TopologyBuilder.router_list:
		container_build_dir = os.path.join(TopologyBuilder.build_path, router.name)
		if not os.path.exists(container_build_dir):
			os.mkdir(container_build_dir)
		shutil.copyfile(os.path.join(TopologyBuilder.build_path, 'Dockerfile'),
				 		os.path.join(container_build_dir, 'Dockerfile'))
		DockerStartFileObject = DockerStartFile(container_build_dir, TopologyBuilder)
		DockerStartFileObject.enable_daemons(TopologyBuilder.daemon_list)
		if TopologyBuilder.is_mpls_enabled:
			DockerStartFileObject.enable_mpls()
		if router.vrf_list:
			DockerStartFileObject.enable_vrf(router.vrf_list)
		DockerStartFileObject.launch_continous_process()
	sys.stdout.write("DONE\n")
	if TopologyBuilder.is_mpls_enabled:
		sys.stdout.write("\n*** WARNING: Since MPLS is going to be used, pls load the modules first ***\n")
		sys.stdout.write("   - modprobe mpls_router\n   - modprobe mpls_gso\n   - modprobe mpls_iptunnel\n\n")


if __name__ == '__main__':
	main()
