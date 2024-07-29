import os
import re
import glob
import socket
from charmhelpers import fetch
from charmhelpers.core import host, hookenv, unitdata
from charmhelpers.core.templating import render
from charms.reactive import when, when_not, remove_state, set_state
from charms.reactive.helpers import any_file_changed, data_changed
from charms.reactive import hook
import urllib.parse as urlparse


@when_not('collectd.started')
@when_not('collectd.stopped')
def setup_collectd():
    hookenv.status_set('maintenance', 'Configuring collectd')
    install_packages()
    if not validate_settings():
        return
    config = resolve_config()
    install_conf_d(get_plugins())
    settings = {'config': config,
                'plugins': get_plugins(),
                }

    render(source='collectd.conf.j2',
           target='/etc/collectd/collectd.conf',
           context=settings,
           )

    set_state('collectd.start')
    hookenv.status_set('active', 'Ready')


@when('collectd.started')
def check_config():
    if data_changed('collectd.config', hookenv.config()):
        if validate_settings():
            setup_collectd()  # reconfigure and restart


@when('nrpe-external-master.available')
def setup_nrpe_checks(nagios):
    config = hookenv.config()
    options = {'check_name': 'check_collectd',
               'description': 'Verify that collectd process is running',
               'servicegroups': config['nagios_servicegroups'],
               'command': '/usr/lib/nagios/plugins/check_procs -C collectd -c 1:1'
               }
    options['hostname'] = '{}-{}'.format(config['nagios_context'],
                                         hookenv.local_unit()).replace('/', '-')

    render(source='nagios-export.jinja2',
           target='/var/lib/nagios/export/service__{}_collectd.cfg'.format(options['hostname']),
           context=options
           )
    render(source='nrpe-config.jinja2',
           target='/etc/nagios/nrpe.d/check_collectd.cfg',
           context=options
           )
    if any_file_changed(['/etc/nagios/nrpe.d/check_collectd.cfg']):
        host.service_reload('nagios-nrpe-server')


@when_not('nrpe-external-master.available')
def wipe_nrpe_checks():
    checks = ['/etc/nagios/nrpe.d/check_collectd.cfg',
              '/var/lib/nagios/export/service__*_collectd.cfg']
    for check in checks:
        for f in glob.glob(check):
            if os.path.isfile(f):
                os.unlink(f)


def validate_settings():
    required = set(('interval', 'plugins'))
    config = resolve_config()
    missing = required.difference(config.keys())
    if missing:
        hookenv.status_set('waiting', 'Missing configuration options: {}'.format(missing))
        return False
    if 'graphite_protocol' in config and config['graphite_protocol'].upper() not in ('TCP', 'UDP'):
        hookenv.status_set('waiting', 'Bad value for "graphite_protocol" option')
        return False
    if 'graphite_port' in config and (config['graphite_port'] < 1 or config['graphite_port'] > 65535):
        hookenv.status_set('waiting', '"graphite_port" outside of allowed range')
        return False
    if 'network_port' in config and (config['network_port'] < 1 or config['network_port'] > 65535):
        hookenv.status_set('waiting', '"network_port" outside of allowed range')
        return False
    return True


def install_packages():
    config = hookenv.config()
    packages = []
    if config.get('default_package', False):
        packages.append('collectd')
    else:
        packages.append(os.path.abspath('files/collectd.deb'))
        packages.append(os.path.abspath('files/collectd-core.deb'))

    fetch.configure_sources()
    fetch.apt_update()
    fetch.apt_install(packages)


@hook('stop')
def remove_collectd():
    """
    Remove installed collectd packages when the principal charm relation revoked
    """
    if host.service_running('collectd'):
        hookenv.log('Stopping collectd...')
        set_state('collectd.stopped')
    if not host.service_running('collectd'):
        set_state('collectd.stopped')


@when('collectd.stopped')
def uninstall_packages():
    packages = ['collectd-core', 'collectd']
    hookenv.log('Uninstalling collectd packages...')
    fetch.apt_purge(packages)


def get_plugins():
    default_plugins = [
        'syslog', 'battery', 'cpu', 'df', 'disk', 'entropy', 'interface',
        'irq', 'load', 'memory', 'processes', 'rrdtool', 'swap', 'users', 'write_prometheus'
    ]
    config = resolve_config()
    if config['plugins'] == 'default':
        plugins = default_plugins
    else:
        plugins = [p.strip() for p in config['plugins'].split(',')]

    if config.get('graphite_endpoint', False):
        plugins.append('write_graphite')
    if config.get('network_target', False):
        plugins.append('network')
    if 'write_prometheus' in plugins:
        plugins.remove('write_prometheus')          # 'write_prometheus' enabled by default

    for p in plugins:
        if not os.path.isfile(os.path.join('/usr/lib/collectd', p + '.so')):
            hookenv.log('Invalid plugin {}'.format(p), hookenv.ERROR)
            hookenv.status_set('waiting', 'Invalid plugin {}'.format(p))
            return
    hookenv.log('Plugins to enable: {}'.format(plugins))
    return plugins


def install_conf_d(plugins):
    config = resolve_config()
    if not os.path.isdir('/etc/collectd/collectd.conf.d'):
        os.mkdir('/etc/collectd/collectd.conf.d')

    for plugin in plugins:
        template = 'collectd.conf.d/{}.conf.j2'.format(plugin)
        if os.path.isfile(os.path.join('templates', template)):
            hookenv.log('Installing configuration file for "{}" plugin'.format(plugin))

            render(source=template,
                   target='/etc/collectd/collectd.conf.d/juju_{}.conf'.format(plugin),
                   context={'config': config}
                   )
    extra_config_template = 'collectd.conf.d/extra_config.conf.j2'
    extra_config_target = '/etc/collectd/collectd.conf.d/juju_extra_config.conf'

    if config.get('extra_config', False) and os.path.isfile(os.path.join('templates', extra_config_template)):
        hookenv.log('Installing additional configuration to {}'.format(extra_config_target))
        render(source=extra_config_template,
               target=extra_config_target,
               context={'config': config}
               )
    elif not config.get('extra_config', False) and os.path.isfile(extra_config_target):
        hookenv.log('Clearing unused configuration file: {}'.format(extra_config_target))
        os.unlink(extra_config_target)


def get_prometheus_port():
    config = hookenv.config()
    prometheus_output_port = 9104
    if not config.get("prometheus_output_port", False):
        return prometheus_output_port
    if config.get("prometheus_output_port") == "default":
        return prometheus_output_port
    return int(config.get("prometheus_output_port"))


def resolve_config():
    config = hookenv.config()
    config['prometheus_output_port'] = get_prometheus_port()

    if config.get('graphite_endpoint', False):
        config['graphite_host'], config['graphite_port'] = config['graphite_endpoint'].split(':')
        config['graphite_port'] = int(config['graphite_port'])
    if config.get('network_target', False):
        config['network_host'], config['network_port'] = config['network_target'].split(':')
        config['network_port'] = int(config['network_port'])
    if config.get('hostname_type', False).lower() == 'hostname':
        config['hostname'] = socket.gethostname()
    elif not config.get('hostname_type', '') or config.get('hostname_type', '').lower() == 'fqdn':
        config['hostname'] = 'fqdn'
    else:
        hookenv.status_set('waiting', 'unsupported value for "hostname_type" option')
        raise Exception('Invalid value for "hostname_type" option')
    return config


@when('collectd.start')
def start_collectd():
    if not host.service_running('collectd'):
        hookenv.log('Starting collectd...')
        host.service_start('collectd')
        set_state('collectd.started')
    if any_file_changed(['/etc/collectd/collectd.conf']):
        handle_config_changes()
    if any_file_changed(['/etc/collectd/collectd.conf.d/juju_extra_config.conf']):
        handle_config_changes()
    remove_state('collectd.start')


# @when("config.changed")
def handle_config_changes():
    if host.service_running('collectd'):
        hookenv.log('Restarting collectd config...')
        host.service_restart('collectd')    # Job type reload is not applicable for unit collectd.service


@when('target.available')
def configure_prometheus_relation(target):
    target.configure(get_prometheus_port())
