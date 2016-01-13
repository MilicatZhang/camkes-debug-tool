#!/usr/bin/env python

import sys
import os
import getopt
import re
import shutil

import camkes_strings
import paths

fault_slots = dict()
used_components = dict()
debug_component_types = dict()
debug_component_paths = dict()
debug_component_instances = dict()
camkes_file_text = []
capdl_text = []
### Cleanup functions ###

# Initiates cleanup
def clean_debug(project_name):
	print "Cleaning"
	clean_debug_components(project_name)
	clean_debug_camkes(project_name)
	clean_makefile(project_name)
	os.system("make clean")

# Removes any component camkes debug files
def clean_debug_components(project_name):
	# Regex used to find debug files
	regex1 = re.compile(r'.*\.camkes\.dbg')

	for component_folder_name in os.listdir(paths.components_folder % project_name):
		for file_name in os.listdir(paths.component_path % (project_name, component_folder_name)):
			if regex1.match(file_name):
				debug_file_path = paths.component_files % (project_name, component_folder_name, file_name)
				os.remove(debug_file_path)

# Removes any debug camkes files
def clean_debug_camkes(project_name):
	if os.path.isfile(paths.new_camkes):
		os.remove(paths.new_camkes)
	if os.path.exists(paths.debug_folder % project_name):
		shutil.rmtree(paths.debug_folder % project_name)

def clean_makefile(project_name):
	makefile_path = paths.makefile % project_name
	backup_path = paths.makefile_backup % project_name
	if os.path.isfile(backup_path):
		os.remove(makefile_path)
		os.rename(backup_path, makefile_path)

	
### Code gen functions ###

def add_templates(project_name):
	os.symlink(os.path.abspath(paths.templates_from), paths.templates_to % project_name)

# Finds the types of components used in this project and adds them to the used_components dict
def find_used_components(project_name):
	# Regex used to find used components
	regex1 = re.compile(r'component (\w*)')

	with open(paths.old_camkes % (project_name, project_name), "r+") as f:
		for line in f:
			component_search = regex1.search(line)
			if component_search:
				component = component_search.group(1)
				used_components[component] = 0

# Searches used components for debug keywords, 
# and adds the path to the debug_component_paths dict,
# and the name of the type to debug_component_types
# Creates a new camkes file for each one found
# Returns true if any debug components found, false otherwise
def parse_debug_components(project_name):
	debug_found = False

	regex1 = re.compile(r'\s*debug_component\s*(\w*) .*;')
	with open(paths.old_camkes % (project_name, project_name)) as f:
		for line in f.readlines():
			m = regex1.match(line)
			if m:
				debug_found = True
				component_type = m.group(1)
				debug_component_types[component_type] = 0
				debug_component_paths[paths.component_files_rel % (m.group(1), m.group(1))] = 0
				create_debug_camkes(project_name, component_type)
	return debug_found

# Creates a new camkes file for a debug component. 
# The new file is created with a .dbg extension
def create_debug_camkes(project_name, component_type):
	# Regex used to find debug keyword
	regex1 = re.compile(r'component %s {\s*' % component_type)

	with open(paths.original_component % (project_name, component_type, component_type))  as f:
		component_file_text = f.readlines()

	with open(paths.debugged_component % (project_name, component_type, component_type), 'w+') as f:
		for line in component_file_text:
			f.write(line)
			if regex1.match(line):
				f.write("  uses %s_debug debug;\n" % project_name)
				f.write("  provides %s_debug internal;\n" % project_name)
# Finds the names of all debug component instances 
# and adds them to the debug_component_instances dict

# Creates a new camkes file that points to the newly
# generated debug component camkes files
def parse_camkes(project_name):
	# Regex used to find component types and names
	regex1 = re.compile(r'debug_component (\w*)\s*(\w*);')
	# Regex used to find component imports
	regex2 = re.compile(r'import \"(.*)\";')

	global camkes_file_text
	with open(paths.old_camkes % (project_name, project_name), "r+") as f:
		camkes_file_text = f.readlines()
	for index, line in enumerate(camkes_file_text):
		component_search = regex1.search(line)
		if component_search:
			component_type = component_search.group(1)
			component_instance_name = component_search.group(2)
			if component_type in debug_component_types:
				debug_component_instances[component_instance_name] = 0
			camkes_file_text[index] = line.replace("debug_component", "component")
					
	for index, line in enumerate(camkes_file_text):
		import_match = regex2.match(line)
		if import_match:
			component_path = import_match.group(1)
			if component_path in debug_component_paths.keys():
				camkes_file_text[index] = "import \"%s.dbg\";\n" % component_path

# Modifies the makefile to build the debug camkes file instead
def modify_makefile(project_name):
	# Regex to find camkes file reference
	regex1 = re.compile(r'ADL := (.*)\.camkes')
	# If a backup exists it means it has already been modified, no need to do anything
	if not os.path.isfile(paths.makefile_backup % project_name):
		with open(paths.makefile % project_name, 'r+') as f:
			makefile_text = f.readlines()
			# Create a backup
			with open(paths.makefile_backup % project_name, 'w+') as f2:
				for line in makefile_text:
					f2.write(line)
			# Modify the makefile and write to it
			for line_index in range(0, len(makefile_text)):
				camkes_match = regex1.match(makefile_text[line_index])
				if camkes_match:
					makefile_text[line_index] = "ADL := %s.camkes.dbg\n" % camkes_match.group(1)
			makefile_text.insert(line_index, "debug_server_HFILES = debug/include/EthType.h\n")
			makefile_text.insert(line_index, "TEMPLATES := debug/templates\n")
			f.seek(0)
			for line in makefile_text:
				f.write(line)

# Modify the camkes text to include the new component, and add dummy connections
# Also add the serial port and connections
# TODO: Change this to make sure we insert in the composition section
def modify_camkes(project_name):
	# Regex to find camkes composition start
	regex1 = re.compile(r'\s*}')
	global camkes_file_text
	# Insert the debug component import
	camkes_file_text.insert(0 , "import \"debug/debug.camkes\";\n");
	for index, line in enumerate(camkes_file_text):
		if regex1.match(line):
			camkes_file_text.insert(index, "    component debug_server debug;\n" )
			index += 1
			conn_num = 1
			for component_instance in debug_component_instances.keys():
				camkes_file_text.insert(index, "    connection seL4GDB debug%s(from %s.debug, to debug.%s_debug);\n" % 
			    (conn_num, component_instance, component_instance))
				camkes_file_text.insert(index, "    connection seL4Debug debug%s_internal(from debug.%s_internal, to %s.internal);\n" % 
			    (conn_num, component_instance, component_instance))
				index += 1
				conn_num += 1
			index += 1
			camkes_file_text.insert(index , camkes_strings.debug_server_decls);
			break
	for index, line in enumerate(camkes_file_text):
		if regex1.match(line):
			camkes_file_text.insert(index + 1, camkes_strings.debug_server_config)

def add_debug_files(project_name):
	os.mkdir(paths.debug_folder % project_name)
	if not os.path.exists(paths.debug_include % project_name):
		os.mkdir(paths.debug_include  % project_name)
	os.symlink(os.path.abspath(paths.ethtype_from), paths.ethtype_to % project_name)
	with open(paths.debug_camkes % (project_name), "w+") as f:
		new_line =  camkes_strings.debug_camkes_common % project_name
		for component_instance in debug_component_instances.keys():
			new_line += camkes_strings.debug_camkes_component_connection.format(component_instance, project_name)
		new_line += "}\n\n"	
		f.write(new_line)

# Write a new project camkes file
def write_camkes(project_name):
	with open(paths.new_camkes % (project_name, project_name), "w+") as f:
		for line in camkes_file_text:
			f.write(line)

# Find fault ep slots
def find_fault_eps(project_name):
	global debug_component_instances
	global capdl_text

	with open("build/x86/pc99/%s/%s.cdl" % (project_name, project_name)) as f:
		capdl_text = f.readlines();

	for component_instance in debug_component_instances.keys():
		regex1 = re.compile(r'cnode_%s {' % component_instance)
		regex2 = re.compile(r'(0x\w*): conn\d*_%s_debug \(RWX\)' % component_instance)
		for index, line in enumerate(capdl_text):
			cnode_match = regex1.match(line)
			if cnode_match:
				while capdl_text[index] != "}\n":
					fault_slot_match = regex2.match(capdl_text[index])
					if fault_slot_match:
						debug_component_instances[component_instance] = int(fault_slot_match.group(1), 16)
						break
					index += 1
				break

# Register fault eps
def register_fault_eps():
	global debug_component_instances
	global capdl_text

	for component_instance, fault_ep in debug_component_instances.iteritems():
		regex1 = re.compile(r'(%s_tcb_.*) = tcb \((.*)\)' % component_instance)
		for index, line in enumerate(capdl_text):
			tcb_decl_match = regex1.match(line)
			if tcb_decl_match:
				tcb_name = tcb_decl_match.group(1)
				tcb_params = tcb_decl_match.group(2) 
				capdl_text[index] = "%s = tcb (%s, fault_ep: %s)\n" % (tcb_name, tcb_params, hex(fault_ep))

# Write out the capdl file
def write_capdl(project_name):
	with open("build/x86/pc99/%s/%s.cdl" % (project_name, project_name), 'w+') as f:
		for line in capdl_text:
			f.write(line)

def main(argv):
	os.chdir("../..")
	project_name = "gdb_test"	
	try:
		opts, args = getopt.getopt(argv, "c")
	except getopt.GetoptError as err:
		print str(err)
		sys.exit(1)
	# Check for clean flag
	for o, a in opts:
		if o == "-c":
			clean_debug(project_name)
			sys.exit(0)
	# Find components used in this project
	find_used_components(project_name)
	# Parse debug components
	debug_found = parse_debug_components(project_name)
	# Check if debug components found
	if not debug_found:
		print "No debug components were found in %s" % project_name
		sys.exit(0)
	# Parse project camkes
	parse_camkes(project_name)
	# Modify camkes to include debug code
	modify_camkes(project_name)
	add_debug_files(project_name)
	# Write new camkes
	write_camkes(project_name)
	# Modify makefile to build new camkes
	modify_makefile(project_name)
	# Add custom templates
	add_templates(project_name)
	os.system("make -j8 libmuslc")
	os.system("make")
	os.system("make")
	# Find the slots that fault eps are placed
	find_fault_eps(project_name)
	register_fault_eps()
	write_capdl(project_name)
	os.system("make")

if __name__ == "__main__":
	main(sys.argv[1:])