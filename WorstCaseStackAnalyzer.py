import re
import elf
import os
import argparse

class StackAnalyzer:
	# Constants
	rtl_ext = '.c.249r.dfinish'
	su_ext = '.su'
	obj_ext = '.o'

	def __init__(self, directories):
		self.directories = directories
		self.call_graph = {'locals': {}, 'globals': {}}
		self.tu_list = []

		self.find_files()
		for tu in self.tu_list:
			self.read_obj(tu)
			self.read_rtl(tu)
			self.read_su(tu)
		self.resolve_all_calls()
		self.calculate_stack()
		self.print_stack_usage()

	def _demangle_func(self, func):
		return re.sub(r'.constprop(.\d)?', '', func)	# Currently only demangles constant propagated function

	def _find_func(self, tu, func):
		if func in self.call_graph['globals']:
			return self.call_graph['globals'][func]
		elif func in self.call_graph['locals'] and tu in self.call_graph['locals'][func]:
			return self.call_graph['locals'][func][tu]
		else:
			return None

	def find_files(self):
		for directory in self.directories:
			for root, dirs, all_files in os.walk(directory):
				files = [f for f in all_files if '.o' in f]
				for f in files:
					base = re.search(r'(.+)\.o$', f).group(1)
					if base + StackAnalyzer.su_ext in all_files and base + StackAnalyzer.obj_ext in all_files and base + StackAnalyzer.rtl_ext in all_files:
						rootnorm = os.path.join(root, '')
						self.tu_list.append(rootnorm + base)

		if len(self.tu_list) == 0:
			raise Exception("Error No files found in {}!".format(str(self.directories)))

	def read_obj(self, tu):
		parsedElf = elf.ReadElf(tu + StackAnalyzer.obj_ext)
		symbols = parsedElf.get_symbols()

		for s in symbols:
			if s['type'] == 'FUNC':
				s['name'] = self._demangle_func(s['name'])
				if s['binding'] == 'GLOBAL':
					if (s['name'] in self.call_graph['globals'] and self.call_graph['globals'][s['name']]['binding'] != 'WEAK') or (s['name'] in self.call_graph['locals'] and self.call_graph['locals'][s['name']]['binding'] != 'WEAK'):
						raise Exception('{}: Multiple global declarations of {}\r\nPrevious in {}'.format(tu, s['name'], self.call_graph['globals'][s['name']]['tu']))
					self.call_graph['globals'][s['name']] = {'tu': tu, 'name': s['name'], 'binding': 'GLOBAL'}
				elif s['binding'] == 'LOCAL':
					if s['name'] in self.call_graph['locals'] and tu in self.call_graph['locals'][s['name']]:
						raise Exception('Multiple local declarations of {}'.format(s['name']))
					if s['name'] not in self.call_graph['locals']:
						self.call_graph['locals'][s['name']] = {}
					self.call_graph['locals'][s['name']][tu] = {'tu': tu, 'name': s['name'], 'binding': 'LOCAL'}
				elif s['binding'] == 'WEAK':
					if not s['name'] in self.call_graph['globals']:
						self.call_graph['globals'][s['name']] = {'tu': tu, 'name': s['name'], 'binding': 'WEAK'}
				else:
					raise Exception('Error Unknown Binding "{}" for symbol: {}'.format(s['binding'], s['name']))

	def read_rtl(self, tu):
		function = re.compile(r'^;; Function (.*)\s+\((\S+)(,.*)?\).*$')
		static_call = re.compile(r'^.*\(call.*"(.*)".*$')
		other_call = re.compile(r'^.*call .*$')

		with open(tu + StackAnalyzer.rtl_ext) as f:
			for line in f.readlines():
				# Function tree found
				m = function.match(line)
				if m:
					func_name = self._demangle_func(m.group(1))
					func = self._find_func(tu, func_name)
					if not func:
						raise Exception("Error locating function {} in {}".format(func_name, tu))

					func['calls'] = set()
					func['has_ptr_call'] = False
					continue

				# Function call found
				m = static_call.match(line)
				if m:
					func['calls'].add(self._demangle_func(m.group(1)))
					continue

				# Pointer call found
				m = other_call.match(line)
				if m:
					func['has_ptr_call'] = True
					continue

	def read_su(self, tu):
		su_line = re.compile(r'^([^ :]+):([\d]+):([\d]+):([\S]+)\s+(\d+)\s+(\S+)$')

		with open(tu + StackAnalyzer.su_ext) as f:
			for index, line in enumerate(f.readlines()):
				m = su_line.match(line)
				if m:
					func_name = self._demangle_func(m.group(4))
					func = self._find_func(tu, func_name)
					func['local_stack'] = int(m.group(5))
					func['stack_qual'] = m.group(6)
				else:
					raise Exception("Error parsing line {} in file {}".format(index+1, tu))

	def resolve_all_calls(self):
		def resolve_calls(caller):
			caller['r_calls'] = []
			caller['unresolved_calls'] = set()

			if caller['binding'] == 'WEAK':
				return
			for call in caller['calls']:
				call_dict = self._find_func(caller['tu'], call)
				if call_dict:
					caller['r_calls'].append(call_dict)
				else:
					caller['unresolved_calls'].add(call)

		# Iterate through all global symbols
		for func in self.call_graph['globals'].values():
			resolve_calls(func)

		# Iterate through all local symbols
		for l in self.call_graph['locals'].values():
			for func in l.values():
				resolve_calls(func) 


	def calculate_stack(self):
		def calc_wcs(func_dict2, parents):
			# If the wcs is already known, then nothing to do
			if 'wcs' in func_dict2:
				return

			# Check for weak binding
			if func_dict2['binding'] == 'WEAK' and not 'has_ptr_call' in func_dict2:
				return

			# Check for pointer calls
			if func_dict2['has_ptr_call']:
				func_dict2['wcs'] = 'unbounded'
				return

			# Check for recursion
			if func_dict2 in parents:
				func_dict2['wcs'] = 'unbounded'
				return

			# Calculate WCS
			call_max = 0
			for call_dict in func_dict2['r_calls']:

				# Calculate the WCS for the called function
				parents.append(func_dict2)
				calc_wcs(call_dict, parents)
				parents.pop()

				# If the called function is unbounded, so is this function
				if call_dict['wcs'] == 'unbounded':
					func_dict2['wcs'] = 'unbounded'
					return

				# Keep track of the call with the largest stack use
				call_max = max(call_max, call_dict['wcs'])

				# Propagate Unresolved Calls
				for unresolved_call in call_dict['unresolved_calls']:
					func_dict2['unresolved_calls'].add(unresolved_call)

			if 'local_stack' in func_dict2:
				func_dict2['wcs'] = call_max + func_dict2['local_stack']
			else:
				func_dict2['wcs'] = 'unbounded'

		# Loop through every global and local function
		# and resolve each call, save results in r_calls
		for func in self.call_graph['globals'].values():
			calc_wcs(func, [])

		for l in self.call_graph['locals'].values():
			for func in l.values():
				calc_wcs(func, [])

	def print_stack_usage(self):
		print("\r\n{:<32} {:<48} {:<9} {:<16}\r\n".format('Tranlation Unit', 'Function Name', 'Stack ', 'Unresolved Dependencies'))

		def print_func(func_dict2):
			unresolved = func_dict2['unresolved_calls']
			if unresolved:
				unresolved_str = '({})'.format(', '.join(unresolved))
			else:
				unresolved_str = ''

			print("{:<32} {:<48} {:>9} {:<16}".format(func_dict2['tu'].rsplit('/',1)[1], func_dict2['name'], func_dict2['wcs'], unresolved_str))

		def get_order(val):
			if val == 'unbounded':
				return 1
			else:
				return -val

		# Loop through every global and local function
		# and resolve each call, save results in r_calls
		d_list = []
		for func_dict in self.call_graph['globals'].values():
			if func_dict['binding'] != 'WEAK':
				d_list.append(func_dict)

		for l_dict in self.call_graph['locals'].values():
			for func_dict in l_dict.values():
				d_list.append(func_dict)

		d_list.sort(key=lambda item: get_order(item['wcs']))
		for d in d_list:
			print_func(d)

parser = argparse.ArgumentParser()
parser.add_argument('dirs', nargs='*')
StackAnalyzer(parser.parse_args().dirs)
