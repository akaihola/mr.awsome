from ConfigParser import RawConfigParser
import os


class Config(dict):
    def massage_instance_fabfile(self, value):
        if not os.path.isabs(value):
            value = os.path.join(self.path, value)
        return value

    def massage_instance_startup_script(self, value):
        result = dict()
        if value.startswith('gzip:'):
            value = value[5:]
            result['gzip'] = True
        if not os.path.isabs(value):
            value = os.path.join(self.path, value)
        result['path'] = value
        return result

    def massage_instance_securitygroups(self, value):
        securitygroups = []
        for securitygroup in value.split(','):
            securitygroups.append(securitygroup.strip())
        return set(securitygroups)

    def massage_instance_volumes(self, value):
        volumes = []
        for line in value.split('\n'):
            volume = line.split()
            if not len(volume):
                continue
            volumes.append((volume[0], volume[1]))
        return tuple(volumes)

    def massage_instance_snapshots(self, value):
        snapshots = []
        for line in value.split('\n'):
            snapshot = line.split()
            if not len(snapshot):
                continue
            snapshots.append((snapshot[0], snapshot[1]))
        return tuple(snapshots)

    def massage_instance_delete_volumes_on_terminate(self, value):
        if value.lower() in ('true', 'yes', 'on'):
            return True
        elif value.lower() in ('false', 'no', 'off'):
            return False
        raise ValueError("Unknown value %s for delete-volumes-on-terminate." % value)

    def massage_securitygroup_connections(self, value):
        connections = []
        for line in value.split('\n'):
            connection = line.split()
            if not len(connection):
                continue
            connections.append((connection[0], int(connection[1]),
                                int(connection[2]), connection[3]))
        return tuple(connections)

    massage_server_fabfile = massage_instance_fabfile

    def massage_server_user(self, value):
        if value == "*":
            import pwd
            value = pwd.getpwuid(os.getuid())[0]
        return value

    def _expand(self, sectiongroupname, sectionname, section, seen):
        if (sectiongroupname, sectionname) in seen:
            raise ValueError("Circular macro expansion.")
        macrogroupname = sectiongroupname
        macroname = section['<']
        seen.add((sectiongroupname, sectionname))
        if ':' in macroname:
            macrogroupname, macroname = macroname.split(':')
        macro = self[macrogroupname][macroname]
        if '<' in macro:
            self._expand(macrogroupname, macroname, macro, seen)
        # this needs to be after the recursive _expand call, so circles are
        # properly detected
        del section['<']
        for key in macro:
            if sectiongroupname in ('instance',):
                if key in ('ip', 'volumes'):
                    continue
            if key not in section:
                section[key] = macro[key]

    def __init__(self, config, path=None):
        _config = RawConfigParser()
        _config.optionxform = lambda s: s
        if getattr(config, 'read', None) is not None:
            _config.readfp(config)
            self.path = path
        else:
            _config.read(config)
            self.path = os.path.dirname(config)
        for section in _config.sections():
            if ':' in section:
                sectiongroupname, sectionname = section.split(':')
            else:
                sectiongroupname, sectionname = 'global', section
            items = dict(_config.items(section))
            sectiongroup = self.setdefault(sectiongroupname, {})
            sectiongroup.setdefault(sectionname, {}).update(items)
        seen = set()
        for sectiongroupname in self:
            sectiongroup = self[sectiongroupname]
            for sectionname in sectiongroup:
                section = sectiongroup[sectionname]
                if '<' in section:
                    self._expand(sectiongroupname, sectionname, section, seen)
                for key in section:
                    fname = 'massage_%s_%s' % (sectiongroupname, key.replace('-', '_'))
                    massage = getattr(self, fname, None)
                    if callable(massage):
                        section[key] = massage(section[key])
