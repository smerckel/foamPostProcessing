import os
import numpy as np
import struct
import glob

CACHE = {}

FIELD_TYPES=dict(U='vector', T='vector', phi='scalar', p='scalar', 
                 nut='scalar', omega='scalar')
                
class InternalFieldAverage(object):
    BS = 8
    def __init__(self, name, time):
        self.path = os.path.join(time, name)
        self.header_text = []
        self.footer_text = []
        self.name = name

        
    def read(self):
        with open(self.path, 'rb') as fp:
            while True:
                line = fp.readline()
                self.header_text.append(line)
                if line.startswith(b"internalField"):
                    break
            line = fp.readline()
            number_points = int(line.decode().strip())
            self.file_format = self.get_file_format()
            self.read_bytefield(fp, number_points)
            assert fp.read(2) == b');'
            for line in fp:
                self.footer_text.append(line)

                
    def add_to_cache(self, field):
        key = self.name
        key_int = f"n_{self.name}"
        try:
            CACHE[key]+=field
        except KeyError:
            CACHE[key] = field
            CACHE[key_int] = 1
        else:
            CACHE[key_int] += 1

            
    def write_mean(self):
        key = self.name
        key_int = f"n_{self.name}"
        field = CACHE[key]
        field /= CACHE[key_int]
        outfilename = f"{self.name}Mean"
        with open(outfilename, 'wb') as fp:
            fp.writelines(self.header_text)
            fp.writelines([b"%d\n"%(field.shape[0])])
            fp.write(b'(')
            self.write_bytefield(fp, field)
            fp.write(b');')
            fp.writelines(self.footer_text)

            
    def get_file_format(self):
        s_format = None
        for line in self.header_text:
            s = line.decode().strip()
            if s.startswith("format"):
                _, s_format = s.replace(";","").split()
                break
        if not s_format:
            raise ValueError("No format string found.")
        return s_format

    
    def read_bytefield(self, fp, number_points):
        assert fp.read(1)==b'('
        if self.file_format=="binary":
            field = self.read_bytefield_binary(number_points, fp)
        else:
            field = self.read_bytefield_ascii(number_points, fp)
        self.add_to_cache(field.copy())

        
    def write_bytefield(self, fp, field):
        if self.file_format=="binary":
            self.write_bytefield_binary(fp, field)
        else:
            self.write_bytefield_ascii(fp, field)

            
    def read_bytefield_binary(self, number_points, fp, field):
        raise NotImplementedError

    
    def read_bytefield_ascii(self, number_points, fp, field):
        raise NotImplementedError

    
    def write_bytefield_binary(self, fp, field):
        for x in field.ravel():
            fp.write(struct.pack('d', x))

            
    def write_bytefield_ascii(self, fp, field):
        raise NotImplementedError


    
class VectorInternalFieldAverage(InternalFieldAverage):
    def __init__(self, name, time):
        super().__init__(name, time)

        
    def read_bytefield_binary(self, number_points, fp):
        field = np.zeros((number_points,3), float)
        for i in range(number_points):
            vector = struct.unpack("ddd",fp.read(3*InternalFieldAverage.BS))
            field[i,:] = vector
        return field



class ScalarInternalFieldAverage(InternalFieldAverage):
    def __init__(self, name, time):
        super().__init__(name, time)
        
    def read_bytefield_binary(self, number_points, fp):
        field = np.zeros(number_points, float)
        for i in range(number_points):
            scalar = struct.unpack("d",fp.read(InternalFieldAverage.BS))
            field[i] = scalar[0]
        return field



class CaseStructure(object):

    def __init__(self):
        self.sanity_check()

        
    def sanity_check(self):
        if not (os.path.exists('system') and os.path.exists('constant')):
            raise ValueError('We seem not to be called in a FOAM case.')

    def get_all_time_directories(self):
        directories = glob.glob("[0-9]*[.0-9]*")
        directories.sort(key=lambda x: float(x))
        return directories

    def filter_time(self, directories, *, t_start=None, t_end=None):
        selected_directories = []
        for d in directories:
            if t_start is None or float(d)>=t_start:
                if t_end is None or float(d)<=t_end:
                    selected_directories.append(d)
        return selected_directories
    
                
def clear_cache(name):
    key = name
    key_int = f"n_{name}"
    CACHE.pop(key)
    CACHE.pop(key_int)
                         
def averageField(name, *, t_start=None, t_end=None):
    CS = CaseStructure()
    directories = CS.get_all_time_directories()
    directories = CS.filter_time(directories, t_start=t_start, t_end=t_end)
    for d in directories:
        print(f"Processing {d} for {name} ...")
        if FIELD_TYPES[name]=='vector':
            IFA = VectorInternalFieldAverage(name, d)
        else:
            IFA = ScalarInternalFieldAverage(name, d)
        IFA.read()
    IFA.write_mean()

    
#averageField("U", t_start=300, t_end=350)
            
