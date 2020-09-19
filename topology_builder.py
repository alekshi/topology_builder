import xml.etree.ElementTree as ET
import re
import sys
import ipaddress
import yaml
import argparse


class TheScript():
	def __init__(self, topology_xml_file, working_dir, build_path, is_mpls_supported = False):
		self.topology_xml_file = topology_xml_file
		self.working_dir = working_dir
		self.build_path = build_path
		self.is_mpls_supported = is_mpls_supported
		self.mxcell_list = list()
		self.router_list = list()
		self.link_list = list()

	def object_list_by_name(self, object_list, name):
		return_list = list()
		for object in object_list:
			if re.match('^{}(-|:)\d+?$'.format(name), object.name):
				return_list.append(object)
		return return_list

	def object_by_attribute(self, object_list, attribute_name, attribute_value):
		for object in object_list:
			if getattr(object, attribute_name) == attribute_value:
				return object
		return None

	def cell_by_id(self, cell_list, cell_id):
		for cell in cell_list:
			if cell.id == cell_id:
				return cell
		return None

	def parse_topology_file(self):
		tree = ET.parse(self.topology_xml_file)
		tree_root = tree.getroot()
		for cell in tree_root.iter('mxCell'):
			if 'style' in cell.attrib:
				self.mxcell_list.append(mxCell(cell.attrib))
		if len(self.mxcell_list) > 0:
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
	
	def create_router_list(self, router_shape = 'ellipse'):
		for cell in self.mxcell_list:	
			if cell.type == router_shape:
				self.router_list.append(Router('{}-{}'.format(cell.value.lower(), len(self.object_list_by_name(self.router_list, cell.value.lower()))+1), cell))
		if len(self.router_list) > 0:
			return True
		else:
			return False

	def create_link_list(self):	
		for cell in self.mxcell_list:
			if cell.type == 'edge':
				connection_dict = {'source': None, 'target': None}
				for connection, name in connection_dict.items():
					if getattr(cell, connection) is not None:
						RouterObject = self.object_by_attribute(self.router_list, 'mxCellObject', getattr(cell, connection))
						connection_dict[connection] = re.sub('\s', '_', RouterObject.name)
					else:
						connection_dict[connection] = 'STUB'
				link_name = 'link:{}:{}'.format(connection_dict['source'], connection_dict['target']).lower()
				self.link_list.append(Link('{}:{}'.format(link_name, len(self.object_list_by_name(self.link_list, link_name))+1), cell))
				self.link_list[-1].add_subnet(cell.value)
		if len(self.link_list) > 0:
			return True
		else:
			return False

	def add_links_to_routers(self):
		for router in self.router_list:
			for link in self.link_list:
				if link.mxCellObject.source == router.mxCellObject or link.mxCellObject.target == router.mxCellObject:
					router.add_link(link)


class DockerStartFile():
	def __init__(self, path):
		self.path = path
		self.daemons = ('bgpd',
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
		with open('{}/docker-start'.format(self.path), 'w') as output_file:
			output_file.write('#!/bin/sh\nset -e\n')
			output_file.write("\n#Enable SSH\n")
			output_file.write("sed -i 's/#PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config\n")
			output_file.write("sed -i 's/#PermitEmptyPasswords .*/PermitEmptyPasswords yes/' /etc/ssh/sshd_config\n")
			output_file.write("echo 'root:root' | chpasswd\n")
			output_file.write("echo 'exec /usr/bin/vtysh' >> ~/.bashrc\n")
			output_file.write("/etc/init.d/ssh start\n")
			output_file.write("\n\n\n")
	
	def enable_daemons(self, are_all_enabled = False, daemon_list = list()):
		if are_all_enabled:
			daemon_list = self.daemons
		with open('{}/docker-start'.format(self.path), 'a') as output_file:
			output_file.write('#Enable daemons\n')
			for daemon in daemon_list:
				if daemon in self.daemons:
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

	def launch_continous_process(self):
		with open('{}/docker-start'.format(self.path), 'a') as output_file:
			output_file.write("#Launch continous command\n")
			output_file.write("exec sleep 10000d\n")







class mxCell():
	def __init__(self, cell_details_dict, router_shape = 'ellipse'):
		self.shape_type = {'ellipse': '^ellipse;.+?$', 
						   'rectangle': '^(?!\b(shape=)?hexagon|ellipse|triangle|rhombus\b).?$', 
						   'triangle': '^triangle;.+?$',
						   'hexagon': '^shape=hexagon;.+?$'
						   }
		self.id = cell_details_dict['id']
		if 'style'in cell_details_dict:
			if re.match(self.shape_type[router_shape], cell_details_dict['style']):
				self.type = router_shape
				self.value = cell_details_dict['value']
				self.edge_list = list()
			elif re.match('edgeLabel', cell_details_dict['style']):
				self.type = 'edgeLabel'
				self.value = cell_details_dict['value']
				self.parent = cell_details_dict['parent']
			elif 'source' in cell_details_dict or 'target' in cell_details_dict:
				self.type = 'edge'
				self.value = None
				if 'source' in cell_details_dict:
					self.source = cell_details_dict['source']
				else:
					self.source = None
				if 'target' in cell_details_dict:
					self.target = cell_details_dict['target']
				else:
					self.target = None
			else:
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
	def __init__(self, name, mxCellObject):
		super().__init__(name, mxCellObject)
		self.link_list = list()

	def add_link(self, link):
		self.link_list.append(link)

	def prepare_yaml_dict(self, build_path, expose_ports = None, is_privileged = False):
		yaml_dict = {self.name: {
									"build": build_path,
									"ports": ['{}:{}'.format(ports_tuple[0], ports_tuple[1]) for ports_tuple in expose_ports],
									"privileged": is_privileged,
									"networks": [str(link.name) for link in self.link_list]
								}
					}
		return yaml_dict


class Link(NetworkObject):
	def __init__(self, name, mxCellObject):
		super().__init__(name, mxCellObject)
		self.subnet = None

	def add_subnet(self, subnet):
		try:
			self.subnet = ipaddress.ip_network(subnet)
		except:
			self.subnet = None
	def prepare_yaml_dict(self):
		yaml_dict = {self.name: {
									"driver": "bridge"
								}
					}
		if self.subnet:
			yaml_dict[self.name]["ipam"] = {"driver": "default", 
										    "config": [{'subnet': str(self.subnet)}]
										   }
		return yaml_dict

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

	def create_yaml_dict(self, router_list, link_list):
		counter = 0
		for router in router_list:
			self.add_router(router, [(self.start_port+counter, 22)])
			counter += 1
		for link in link_list:
			self.add_network(link)
	
	def write_to_file(self):
		with open('{}/docker-compose.yml'.format(self.path), 'w') as self.output_file:
			for key, value in self.yaml_dict.items():
				self.output_file.write(yaml.dump({key: value}))


def main():
	#Parsing arguments and create objects
	sys.stdout.write("Parsing arguments... ")

	parser = argparse.ArgumentParser()
	parser.add_argument("-f", "--file", required=True, help="draw.io XML topology file")
	parser.add_argument("-d", "--dir", default=None, help="Directory to put final docker-compose.yml file (current dir by default)")
	parser.add_argument("-p", "--path", default=None, help="Path to dir with Dockerfile (./frr default)")
	parser.add_argument("-m", "--mpls", default=False, help="Boolean. Is MPLS enabled (False by default)")
	parser.add_argument("-D", "--daemons", default=None, help="Daemons to enable in FRR (e.g: proto1,proto2,proto3 All daemons enabled by default)")

	args = parser.parse_args()

	topology_xml_file = args.file
	if args.dir:
		working_dir = args.dir
	else:
		working_dir = sys.path[0]
	if args.path:
		build_path = args.path
	else:
		build_path = '{}/frr'.format(working_dir)

	is_mpls_enabled = args.mpls
	if args.daemons:
		daemon_list = args.daemons.split(',')
	else:
		daemon_list = args.daemons



	TopologyBuilder = TheScript(topology_xml_file, working_dir, build_path, is_mpls_enabled)
	DockerComposeFileObject = DockerComposeFile(working_dir, build_path)
	DockerStartFileObject = DockerStartFile(build_path)

	sys.stdout.write("DONE\n")
	sys.stdout.write("Parsing draw.io XML file... ")
	if TopologyBuilder.parse_topology_file():
		sys.stdout.write("DONE\n")
		sys.stdout.write("Creating router list... ")
		if TopologyBuilder.create_router_list():
			sys.stdout.write("DONE\n")
			sys.stdout.write("Creating link list... ")
			if TopologyBuilder.create_link_list():
				sys.stdout.write("DONE\n")
				sys.stdout.write("Creating docker compose file... ")
				TopologyBuilder.add_links_to_routers()
				DockerComposeFileObject.create_yaml_dict(TopologyBuilder.router_list, TopologyBuilder.link_list)
				DockerComposeFileObject.write_to_file()
				sys.stdout.write("DONE\n")
			else:
				sys.stdout.write("FAILED\n")
				sys.stderr.write('Something goes wrong creating link list. Bye.\n')
				sys.exit(1)
		else:
			sys.stdout.write("FAILED\n")
			sys.stderr.write('Something goes wrong creating router list. Bye.\n')
			sys.exit(1)
	else:
		sys.stdout.write("FAILED\n")
		sys.stderr.write('Something goes wrong parsing draw io XML file. Bye.\n')
		sys.exit(1)

	sys.stdout.write("Creating container configuration file... ")
	
	if daemon_list:
		DockerStartFileObject.enable_daemons(False, daemon_list)
	else:
		DockerStartFileObject.enable_daemons(True)

	if TopologyBuilder.is_mpls_supported:
		DockerStartFileObject.enable_mpls()
	DockerStartFileObject.launch_continous_process()
	sys.stdout.write("DONE\n")


if __name__ == '__main__':
	main()