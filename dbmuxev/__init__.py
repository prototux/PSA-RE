import os
import glob
import yaml

class dbmuxev:
    def __init__(self, rootdir='.', lang='en'):
        self.rootdir = rootdir
        self.lang = lang

        # Define objects we're going to have
        self.archs = None
        self.cars = None

    def load_all(self):
        self.load_archs()
        self.load_nodes()
        self.load_cars()

    def load_archs(self, file='architectures.yml'):
        # Load architectures
        self.archs = None
        with open(f'{self.rootdir}/{file}', 'r') as archfile:
            try:
                self.archs = yaml.load(archfile, Loader=yaml.SafeLoader)
            except:
                print('cannot read architectures file')

    def load_nodes(self, dir='nodes'):
        if not self.archs:
            return None
        # Load nodes for architectures
        for arch, data in self.archs.items():
            for variant, data in data.items():
                if not 'networks' in self.archs[arch][variant]:
                    print(f'WARN: no networks defined in {arch}.{variant}')
                    continue

                filename = f'{self.rootdir}/{dir}/{arch}.{variant}.yml'
                if not os.path.isfile(filename):
                    continue
                with open(filename) as varfile:
                    try:
                        nodes = yaml.load(varfile, Loader=yaml.SafeLoader)
                    except:
                        continue

                    for node, data in nodes.items():
                        if not 'bus' in data:
                            print(f'WARN: no bus for node {node} in {arch}.{variant}')
                            continue
                        for netbus in data['bus']:
                            network, bus = netbus.split('.')
                            if not network in self.archs[arch][variant]['networks']:
                                print(f'WARN: network {network} not found in {arch}.{variant}')
                                continue
                            if not 'nodes' in self.archs[arch][variant]['networks'][network][bus]:
                                self.archs[arch][variant]['networks'][network][bus]['nodes'] = {}
                            self.archs[arch][variant]['networks'][network][bus]['nodes'][node] = data

    def load_frames(self, dir='buses'):
        pass

    def load_cars(self, dir='cars'):
        files = glob.glob(f'{dir}/*.yml')
        self.cars = {}
        for yfile in files:
            carname = os.path.basename(yfile).split('.')[0]
            with open(yfile, 'r') as ystream:
                try:
                    print(f'loading yaml for {carname}')
                    self.cars[carname] = yaml.load(ystream, Loader=yaml.SafeLoader)
                except:
                    print(f'cannot read yaml for car {carname}')

    def list_arch_variants(self):
        if not self.archs:
            return None

        list = []
        for arch, data in self.archs.items():
            for variant, _ in data.items():
                list.append(f'{arch}.{variant}')
        return list
