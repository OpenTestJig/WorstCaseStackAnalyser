import struct


class ReadElf:
	_bind_names = {0: 'LOCAL', 1: 'GLOBAL', 2: 'WEAK'}
	_type_names = {0: 'NOTYPE', 1: 'OBJECT', 2: 'FUNC', 3: 'SECTION', 4: 'FILE'}
	_section_types = {'SHT_SYMTAB': 0x02}

	def __init__(self, file_name):
		self.file = file_name
		self.content = []		# File content
		self.bit32 = None		# TRUE=32bit | FALSE=64bit
		self.littleEndian = None	# TRUE=LittleEndian | FALSE=BigEndian
		self.header = dict()
		self.sections = []
		self.symbols = []

		self._read_file()
		self._read_header()
		self._read_sections()
		self._read_symbol_table()

	def _read_file(self):
		with open(self.file, 'rb') as fid:
			self.content = fid.read()

	def _read_header(self):
		# Check ELF magic
		if self.content[:4] != b'\x7fELF':
			raise Exception("{} not an ELF file!".format(self.file))

		self.bit32 = True if self.content[4] == 1 else False
		self.littleEndian = True if self.content[5] == 1 else False
		self.header['ident'], self.header['type'], self.header['machine'], self.header['version'], self.header['entry'], self.header['phoff'] \
			, self.header['shoff'], self.header['flags'], self.header['ehsize'], self.header['phentsize'], self.header['phnum'], self.header['shentsize'] \
			, self.header['shnum'], self.header['shstrndx'] \
			= struct.unpack(('<' if self.littleEndian else '>') + ("16sHHIIIIIHHHHHH" if self.bit32 else "16sHHIQQQIHHHHHH"), self.content[:(52 if self.bit32 else 64)])

	def _read_sections(self):
		for i in range(self.header['shnum']):
			offset = self.header['shoff'] + i * self.header['shentsize']
			section = dict()
			section['name'], section['type'], section['flags'], section['addr'], section['offset'] \
				, section['size'], section['link'], section['info'], section['addralign'], section['entsize'] \
				= struct.unpack(('<' if self.littleEndian else '>') + ("IIIIIIIIII" if self.bit32 else 'IIQQQQIIQQ'), self.content[offset:offset + (0x28 if self.bit32 else 0x40)])
			self.sections.append(section)

	def _read_symbol_table(self):
		# Find symbol table
		matches = [x for x in self.sections if x['type'] == ReadElf._section_types['SHT_SYMTAB']]
		if len(matches) > 1:
			raise Exception("Multiple symbol tables in ELF!")
		elif len(matches) == 0:
			raise Exception("No symbol tables in ELF!")
		symtab = matches[0]

		num = symtab['size'] // symtab['entsize']
		for i in range(num):
			offset = symtab['offset'] + i * symtab['entsize']
			s = dict()
			if self.bit32:
				s['name'], s['value'], s['size'], s['info'], s['other'], s['shnxdx'] = struct.unpack(('<' if self.littleEndian else '>') + 'IIIbbH', self.content[offset:offset+16])
			else:
				s['name'], s['info'], s['other'], s['shnxdx'], s['value'], s['size'] = struct.unpack(('<' if self.littleEndian else '>') + 'IbbHQQ', self.content[offset:offset+24])

			start = self.sections[symtab['link']]['offset'] + s['name']
			end = start
			while self.content[end]:
				end += 1
			s['name'] = self.content[start:end].decode('utf-8')
			s['type'] = ReadElf._type_names[(s['info'] & 0xf)]
			s['binding'] = ReadElf._bind_names[(s['info'] >> 4)]

			self.symbols.append(s)

	def get_symbols(self):
		return self.symbols
