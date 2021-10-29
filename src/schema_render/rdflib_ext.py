from rdflib import Namespace

def namespace(uri_ref, graph=None):
    '''Return a prefix, namespace tuple of the passed URIRef.

    If a Graph is passed, use the namespace manager of that graph to
    resolve the namespace.
    '''
    from rdflib import Graph, URIRef
    if not graph:
        graph = Graph()

    if isinstance(uri_ref, URIRef):
        for prefix, namespace in graph.namespaces():
            if str(namespace) in str(uri_ref):
                return prefix, namespace
    else:
        raise TypeError('Can only identify the namespace of a URIRef')



class FileData:
    def __init__(self, path=None, rec=False):
        if path.exists(path):
            if path.isfile(path):
                self.load_file(path)
            elif path.isdir(path):
                if rec:
                    self.rec_load_dir(path)
                else:
                    self.load_dir(path)
            else:
                print('what?')


    def load_file(self, file_path):
        meta = music_tag.load_file(file_path)

        with open(file_path, "rb") as f:
            hasher = blake3()
            while True:
                some_bytes = f.read()
                if not some_bytes:
                    break
                hasher.update(some_bytes)
        self._metadata = {k: str(meta[k])
                          for k in meta._TAG_MAP.keys() if meta[k]}
        self.hash = hasher.hexdigest()
        self.url = url.quote(file_path)
        self.path = file_path


    def load_dir(self, dir_path):
        self.children = {}
        self.common = {}
        with scandir(dirpath) as dir_entries:
            for entry in dir_entries:
                if entry.is_file():
                    file_data = FileData(entry.path)
                    self.children[entry.path] = file_data


    def rec_load_dir(self, base_path):
        #dirs = {}
        for dirpath, _, _ in walk(base_path, topdown=False, onerror=print):
            #dirs[dirpath] = None
            #print(dirpath)
            #not_music = []
            #dict of each file in this path
            #files_here = {}

            for filename in filenames:
                abspath = path.join(dirpath, filename)
                try:
                    filedata = FileData(abspath)
                except:
                    self._not_music
                    if (filedata := file_data(filepath)):
                        files_here[filename] = filedata
                        #print(f'\t{filename}: {filedata["_hash"]}')
                    else:
                        not_music += [filename]
            files_here['_not_music'] = not_music

            path_dict[dirpath] = files_here
        return path_dict
    #def intersection(self, *others):
    #    for

#def owl_unpack(b_node):
#    '''Return members of an OWL container class'''
