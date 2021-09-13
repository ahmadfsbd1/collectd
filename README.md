# Juju collectd subordinate charm

This subordinate charm will deploy collectd daemon

Supports: Trusty, Bionic, Focals

### Available features (enhanced)
- Added support for bionic.
- "write_prometheus" plugin support enabled by default.
- Option "prometheus_output_port" to publish metrics in a custom port.
- Added support for collectd and Prometheus Juju relation.
- Support extra plugin configuration via charm option.
- Fix clean-up logic when the unit removes

### Prometheus Output

By default, write_prometheus plugin is enabled and can be used for metrics scraping without using any additional exporter.

Optionally by installing `prometheus-collectd-exporter` package, 
metrics are exposed for prometheus scraping (not recommended).

## How to deploy the charm

The charm relates with any principal charm using juju-info interface.
Assuming that the principal service is called `ubuntu`.

    juju deploy cs:~open-charmers/collectd collectd
    # and 
    juju add-relation ubuntu collectd

To send metrics to the graphite server listening on 192.168.99.10 port 2003:

    juju set collectd graphite_endpoint=192.168.99.10:2003

To expose metrics for prometheus on port 9103 (prometheus-exporter) under "/metrics" URL:

    juju set collectd prometheus_export=http://127.0.0.1:9103/metrics


(New) To expose metrics for prometheus on port 9104 (inbuilt Collectd plugin) under "/metrics" URL:

    juju config collectd prometheus_output_port="9104"

See config.yaml for more details about configuration options

## Build and publish to charm store
 
To install the Charm Tools on Ubuntu:
    ```sudo snap install charm --classic```

Make sure you have logined using Ubuntu SSO ```charm login```

    git clone $COLLECTD_REPO_URL collectd
    charm build collectd

    charm push $PATH_TO_COLLECTD_BUILD/collectd cs:~open-charmers/collectd
    # By default, charm build to /tmp/charm-builds

    #Charm not yet released to any channel, to release,
    charm release cs:~open-charmers/collectd-2
    #mention the revision number for publishing to any release channel, ('stable' by default)

    
### For local testing,
    juju deploy $PATH_TO_COLLECTD_PKG

