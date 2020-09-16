import xml.etree.ElementTree as ET
import re
import sys
import ipaddress
import yaml


class mxCell():
	def __init__(self, cell_details_dict):
		self.id = cell_details_dict['id']
		if 'style'in cell_details_dict:
			if re.match('ellipse', cell_details_dict['style']):
				self.type = 'ellipse'
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

	def cell_by_id(self, cell_list, cell_id):
		for cell in cell_list:
			if cell.id == cell_id:
				return cell
		return None

	def cell_list_by_type(self, cell_list, cell_type):
		return_list = list()
		for cell in cell_list:
			if cell.type == cell_type:
				return_list.append(cell)
		return return_list

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
	def __init__(self, path, build_path):
		self.path = path
		self.build_path = build_path
		self.yaml_dict = {'version': '3', 'services': dict(), 'networks': dict()}

	def add_router(self, RouterObject, expose_ports = None):
		self.yaml_dict['services'].update(RouterObject.prepare_yaml_dict(self.build_path, expose_ports, True))

	def add_network(self, LinkObject):
		self.yaml_dict['networks'].update(LinkObject.prepare_yaml_dict())

	def write_to_file(self):
		with open('{}/docker-compose.yml'.format(self.path), 'w') as self.output_file:
			for key, value in self.yaml_dict.items():
				self.output_file.write(yaml.dump({key: value}))


def object_list_by_name(object_list, name):
	return_list = list()
	for object in object_list:
		if re.match('^{}(-|:)\d+?$'.format(name), object.name):
			return_list.append(object)
	return return_list

def object_by_attribute(object_list, attribute_name, attribute_value):
	for object in object_list:
		if getattr(object, attribute_name) == attribute_value:
			return object
	return None


def main():
	topology_xml_file = sys.argv[1]
	if len(sys.argv) >= 3:
		working_dir = sys.argv[2]
	else:
		working_dir = sys.path[0]

	if len(sys.argv) >= 4:
		build_path = sys.argv[3]
	else:
		build_path = '{}/frr'.format(working_dir)

	DockerComposeFileObject = DockerComposeFile(working_dir, build_path)

	tree = ET.parse(topology_xml_file)
	tree_root = tree.getroot()

	mxcell_list = list()
	for cell in tree_root.iter('mxCell'):
		if 'style' in cell.attrib:
			mxcell_list.append(mxCell(cell.attrib))

	router_list = list()
	for cell in mxcell_list:
		if cell.type == 'edge':
			for connection in ('source', 'target'):
				if getattr(cell, connection) is not None:
					ConnectionObject = cell.cell_by_id(mxcell_list, getattr(cell, connection))
					ConnectionObject.add_connection('edge', cell)
					cell.add_connection(connection, ConnectionObject)
		if cell.type == 'edgeLabel':
			ConnectionObject = cell.cell_by_id(mxcell_list, cell.parent)
			ConnectionObject.value = cell.value
			cell.parent = ConnectionObject
		if cell.type == 'ellipse':
			router_list.append(Router('{}-{}'.format(cell.value.lower(), len(object_list_by_name(router_list, cell.value.lower()))+1), cell))

	link_list = list()
	for cell in mxcell_list:
		if cell.type == 'edge':
			connection_dict = {'source': None, 'target': None}
			for connection, name in connection_dict.items():
				if getattr(cell, connection) is not None:
					RouterObject = object_by_attribute(router_list, 'mxCellObject', getattr(cell, connection))
					connection_dict[connection] = re.sub('\s', '_', RouterObject.name)
				else:
					connection_dict[connection] = 'STUB'
			link_name = 'link:{}:{}'.format(connection_dict['source'], connection_dict['target']).lower()
			link_list.append(Link('{}:{}'.format(link_name, len(object_list_by_name(link_list, link_name))+1), cell))
			link_list[-1].add_subnet(cell.value)

	for router in router_list:
		for link in link_list:
			if link.mxCellObject.source == router.mxCellObject or link.mxCellObject.target == router.mxCellObject:
				router.add_link(link)

	counter = 0
	for router in router_list:
		DockerComposeFileObject.add_router(router, [(2000+counter, 22)])
		counter += 1
	for link in link_list:
		DockerComposeFileObject.add_network(link)

	DockerComposeFileObject.write_to_file()


if __name__ == '__main__':
	main()