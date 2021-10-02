# Juju collectd subordinate charm

This subordinate charm will deploy collectd daemon

Supports: Trusty, Bionic, Focal


### Prometheus Output

By default, write_prometheus plugin enabled and can be used for metrics scraping without using any additional exporter.


## How to deploy the charm

The charm relates with any principal charm using juju-info interface.
Assuming that the principal service is `ubuntu`.

    juju deploy cs:~bt-charmers/collectd collectd
    # and 
    juju add-relation ubuntu collectd

To send metrics to the graphite server listening on 192.168.99.10 port 9001:

    juju set collectd graphite_endpoint=192.168.99.10:9001

To expose metrics for prometheus on port 9104 (enabled by default) under "/metrics" API path:

    juju config collectd prometheus_output_port="9104"

See config.yaml for more details about configuration options